# -*- coding: utf-8 -*-
"""NAS(alist) 客户端 —— 文件浏览/上传/下载 + 经工作台 CGI 的服务控制 (v5.5.0)。

设计取舍:
  * 文件面直连 alist 的 HTTP API / WebDAV (http://<host>:5244)。登录口令由 GUI 用
    Windows DPAPI 加密后存 config.json, 仓库里绝不出现明文(仓库是 public)。
  * 服务状态/启停走路由器工作台的令牌转发端点 ``/cgi-bin/nas-api.sh``
    (与 proxy-api.sh 同一套令牌), 不需要 SSH、不暴露 alist 凭据。
  * 纯函数(大小格式化/条目解析/路径拼接/主机拆分)独立出来便于单测;
    网络调用集中在本模块, GUI 只 import 本模块并 mock 网络层。
"""
from __future__ import annotations

import base64
import http.client
import json
import os
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import quote

DEFAULT_ALIST_PORT = 5244
CGI_PATH = "/cgi-bin/nas-api.sh"
LOGIN_TIMEOUT = 15
LIST_TIMEOUT = 30
TRANSFER_TIMEOUT = 1800        # 大文件传输墙钟上限(USB 盘写 ~3MB/s, 1GB ≈ 6 分钟)
CHUNK = 256 * 1024


class NasApiError(RuntimeError):
    """NAS 调用失败。

    ``kind`` 区分失败层级, GUI 据此给不同措辞:

      * ``network``  —— NAS/路由器不可达(超时、连接被拒), 不是凭据问题。
      * ``auth``     —— 登录被拒(用户名/口令不对, 或 alist 被重置过)。
      * ``notfound`` —— 路径不存在。
      * ``rejected`` —— 路由器工作台明确拒绝(令牌错/脚本未部署)。
      * ``badjson``  —— 返回了非 JSON(被门户劫持的页面)。
    """

    def __init__(self, message, kind="unknown"):
        super().__init__(message)
        self.kind = kind


def error_hint(exc):
    """把 NasApiError 的 kind 翻译成可执行的排查建议(给界面用)。"""
    kind = getattr(exc, "kind", "unknown")
    if kind == "network":
        return ("连不上 NAS。检查: ① 电脑是否连着路由器的网络(或 Tailscale 已连接); "
                "② 服务器地址端口是否正确; ③ 在「NAS 管家」里点一次「启动服务」。")
    if kind == "auth":
        return ("NAS 拒绝了登录: 用户名或密码不对, 或 alist 被重置过(重启后第一次"
                "启动会自动从快照恢复, 稍等再试)。")
    if kind == "notfound":
        return "NAS 上没有这个路径(可能已被删除、改名, 或对应 USB 盘没插)。"
    if kind == "rejected":
        return ("路由器拒绝了服务控制请求: 工作台令牌不一致, 或路由器上的 "
                "nas-api.sh 未部署。")
    return ""


# --------------------------------------------------------------------- 纯函数
def human_size(n):
    """字节数 -> 人类可读大小。非法输入返回 "-"。"""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return "-"
    if n < 0:
        return "-"
    if n < 1024:
        return "%d B" % n
    value = float(n)
    for unit in ("KB", "MB", "GB", "TB", "PB"):
        value /= 1024.0
        if value < 1024 or unit == "PB":
            return "%.1f %s" % (value, unit)
    return "-"


def join_path(*parts):
    """拼接 NAS 路径: 规范成以 / 开头、无重复斜杠、无尾斜杠(根除外)。"""
    raw = "/".join(str(p or "").strip() for p in parts if str(p or "").strip())
    raw = "/" + raw.lstrip("/")
    while "//" in raw:
        raw = raw.replace("//", "/")
    if len(raw) > 1 and raw.endswith("/"):
        raw = raw.rstrip("/")
    return raw or "/"


def parent_path(path):
    """/nas/volume3/x -> /nas/volume3; 任何一层路径的上级(根的上级仍是根)。"""
    path = join_path(path)
    if path == "/":
        return "/"
    cut = path.rfind("/")
    return path[:cut] or "/"


def split_host(host):
    """"192.168.31.1:5244" / "http://100.x.x.x:5244" -> (ip, port:int)。"""
    text = str(host or "").strip()
    if "://" in text:
        text = text.split("://", 1)[1]
    text = text.rstrip("/")
    if ":" in text:
        ip, _, port = text.rpartition(":")
        try:
            return ip, int(port)
        except ValueError:
            return text, DEFAULT_ALIST_PORT
    return text, DEFAULT_ALIST_PORT


def parse_entries(data):
    """把 /api/fs/list 的响应解析成统一条目列表(纯函数)。"""
    content = ((data or {}).get("data") or {}).get("content") or []
    entries = []
    for item in content:
        if not isinstance(item, dict):
            continue
        entries.append({
            "name": str(item.get("name") or ""),
            "size": item.get("size"),
            "is_dir": bool(item.get("is_dir")),
            "modified": str(item.get("modified") or ""),
        })
    return entries


def _kind_from_message(message):
    text = str(message or "")
    if "password" in text.lower() or "登录" in text or "unauthorized" in text.lower():
        return "auth"
    if "not found" in text.lower() or "object not found" in text.lower() \
            or "failed get storage" in text.lower():
        return "notfound"
    return "unknown"


# --------------------------------------------------------------------- 网络
def _post_json(host, path, body, token="", timeout=LIST_TIMEOUT):
    """向 alist 发一个 JSON POST, 返回解析后的完整响应 dict。"""
    ip, port = split_host(host)
    url = "http://%s:%d%s" % (ip, port, path)
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = token
    req = urlrequest.Request(
        url, data=json.dumps(body, ensure_ascii=True).encode("utf-8"),
        headers=headers, method="POST")
    try:
        opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8", "replace"))
            message = str(payload.get("message") or payload.get("content") or "")
        except Exception:                                  # noqa: BLE001
            message = ""
        if exc.code in (401, 403):
            raise NasApiError(message or "登录已过期或口令错误", kind="auth") from exc
        raise NasApiError(message or "NAS 返回 HTTP %s" % exc.code,
                          kind=_kind_from_message(message)) from exc
    except (URLError, OSError) as exc:
        raise NasApiError("NAS 不可达: %s" % exc, kind="network") from exc
    try:
        payload = json.loads(raw)
    except ValueError as exc:
        raise NasApiError("NAS 返回了非 JSON 响应", kind="badjson") from exc
    if isinstance(payload, dict) and payload.get("code") not in (200, None):
        message = str(payload.get("message") or payload.get("content") or "请求失败")
        raise NasApiError(message, kind=_kind_from_message(message))
    return payload


def login(host, user, password, timeout=LOGIN_TIMEOUT):
    """登录 alist, 返回 token; 失败抛 NasApiError(kind=auth/network)。"""
    payload = _post_json(host, "/api/auth/login",
                         {"username": str(user or ""), "password": str(password or "")},
                         timeout=timeout)
    token = ((payload or {}).get("data") or {}).get("token")
    if not token:
        raise NasApiError("登录成功但没有拿到令牌", kind="badjson")
    return token


def fs_list(host, token, path, refresh=False, timeout=LIST_TIMEOUT):
    """列目录, 返回统一条目列表(见 parse_entries)。"""
    payload = _post_json(host, "/api/fs/list",
                         {"path": path, "page": 1, "per_page": 0,
                          "refresh": bool(refresh)},
                         token=token, timeout=timeout)
    return parse_entries(payload)


def fs_mkdir(host, token, path, timeout=LIST_TIMEOUT):
    return _post_json(host, "/api/fs/mkdir", {"path": path},
                      token=token, timeout=timeout)


def fs_remove(host, token, dir_path, names, timeout=LIST_TIMEOUT):
    return _post_json(host, "/api/fs/remove", {"dir": dir_path, "names": list(names)},
                      token=token, timeout=timeout)


def upload_file(host, token, local_path, remote_path, timeout=TRANSFER_TIMEOUT,
                progress=None):
    """上传本地文件到 alist远端路径 (PUT /api/fs/put, 流式分块, 不占大内存)。

    ``progress(sent_bytes, total_bytes_or_None)`` 会在工作线程里被回调。
    """
    ip, port = split_host(host)
    remote_path = join_path(remote_path)
    total = os.path.getsize(local_path)

    def chunks():
        sent = 0
        with open(local_path, "rb") as handle:
            while True:
                block = handle.read(CHUNK)
                if not block:
                    break
                sent += len(block)
                if progress is not None:
                    progress(sent, total)
                yield block

    headers = {
        "Authorization": token,
        # alist 要求 File-Path 为「百分号编码的绝对路径」(ASCII), As-Task=false
        # 让它同步完成而不是丢进离线任务队列。
        "File-Path": quote(remote_path, safe=""),
        "As-Task": "false",
        "Content-Type": "application/octet-stream",
    }
    try:
        conn = http.client.HTTPConnection(ip, port, timeout=timeout)
        try:
            # body 是生成器 -> http.client 自动走 chunked 传输, 不需要整块读进内存
            conn.request("PUT", "/api/fs/put", body=chunks(), headers=headers)
            resp = conn.getresponse()
            payload = resp.read().decode("utf-8", "replace")
        finally:
            conn.close()
    except (OSError, http.client.HTTPException) as exc:
        raise NasApiError("上传失败: %s" % exc, kind="network") from exc
    try:
        parsed = json.loads(payload)
    except ValueError as exc:
        raise NasApiError("上传时 NAS 返回了非 JSON 响应", kind="badjson") from exc
    if parsed.get("code") != 200:
        raise NasApiError(str(parsed.get("message") or "上传失败"), kind="unknown")
    return parsed


def download_file(host, user, password, remote_path, local_path,
                  timeout=TRANSFER_TIMEOUT, progress=None):
    """从 alist WebDAV (/dav) 下载远端文件到本地(流式)。"""
    ip, port = split_host(host)
    remote_path = join_path(remote_path)
    quoted = "/dav" + quote(remote_path, safe="/")
    auth = base64.b64encode(("%s:%s" % (user, password)).encode("utf-8")).decode("ascii")
    url = "http://%s:%d%s" % (ip, port, quoted)
    req = urlrequest.Request(url, method="GET",
                             headers={"Authorization": "Basic " + auth})
    try:
        opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
        resp = opener.open(req, timeout=timeout)
    except HTTPError as exc:
        if exc.code in (401, 403):
            raise NasApiError("下载被拒绝: 用户名或密码错误", kind="auth") from exc
        if exc.code == 404:
            raise NasApiError("远端文件不存在", kind="notfound") from exc
        raise NasApiError("下载失败: HTTP %s" % exc.code, kind="unknown") from exc
    except (URLError, OSError) as exc:
        raise NasApiError("下载失败: %s" % exc, kind="network") from exc
    try:
        total = resp.headers.get("Content-Length")
        total = int(total) if total else None
        sent = 0
        with open(local_path, "wb") as handle:
            while True:
                block = resp.read(CHUNK)
                if not block:
                    break
                handle.write(block)
                sent += len(block)
                if progress is not None:
                    progress(sent, total)
    except OSError as exc:
        raise NasApiError("写本地文件失败: %s" % exc, kind="unknown") from exc
    finally:
        try:
            resp.close()
        except Exception:                                   # noqa: BLE001
            pass
    return sent


# --------------------------------------------------- 路由器服务控制 (CGI 转发)
def cgi_request(router_host, router_port, token, op, timeout=30):
    """调用路由器工作台上的 /cgi-bin/nas-api.sh (与 proxy-api.sh 同一套令牌)。

    返回解析后的 JSON dict; 失败抛 NasApiError(kind=network/rejected/badjson)。
    """
    url = "http://%s:%s%s" % (router_host, router_port, CGI_PATH)
    payload = json.dumps({"token": str(token or ""), "op": str(op)},
                         ensure_ascii=True).encode("utf-8")
    req = urlrequest.Request(url, data=payload, method="POST",
                             headers={"Content-Type": "application/json"})
    try:
        opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except HTTPError as exc:
        raise NasApiError("路由器 NAS 接口返回 HTTP %s" % exc.code,
                          kind="rejected") from exc
    except (URLError, OSError) as exc:
        raise NasApiError("路由器工作台不可达: %s" % exc, kind="network") from exc
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except ValueError as exc:
        raise NasApiError("路由器返回了非 JSON 响应", kind="badjson") from exc
    if isinstance(parsed, dict) and parsed.get("ok") is False:
        raise NasApiError(parsed.get("msg") or "路由器拒绝了请求", kind="rejected")
    return parsed
