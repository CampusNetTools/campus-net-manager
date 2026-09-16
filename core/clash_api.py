# -*- coding: utf-8 -*-
"""mihomo (Clash Meta) 控制 API 客户端 —— 经路由器工作台 CGI 转发 (v5.4.2)。

设计取舍:
  * 路由器上 mihomo 的控制端口带一个随机面板密钥, 且每次部署订阅都会重新生成。
    电脑端不保存该密钥, 而是走路由器上的令牌鉴权转发端点 ``/cgi-bin/proxy-api.sh``;
    密钥只在路由器本地 127.0.0.1 使用, 与工作台共用同一个令牌, 全程不需要 SSH。
  * 解析逻辑(节点过滤/协议归一/排序)是纯函数, 便于单元测试; 网络调用集中在
    ``relay_request`` 一处, 便于 mock。

路径编码约定: 节点名可能含中文/emoji, 不能直接进 HTTP 请求行。电脑端先把它百分号
编码成纯 ASCII, 作为 ``path`` 字段(同样是纯 ASCII)放进 POST 正文; 路由器上的 CGI
用 sed 取出这段 ASCII 后原样拼进 ``http://127.0.0.1:9091/<path>``, 不做二次解码
(busybox 的 printf 无法安全还原百分号转义)。因此 ``_encode_path`` 只做单层 quote,
切片节点名则走 base64 —— 两条通道都保证全程纯 ASCII。
"""
from __future__ import annotations

import base64
import json
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError
from urllib.parse import quote

# 路由器工作台 / 代理接口默认参数
CGI_PATH = "/cgi-bin/proxy-api.sh"
DEFAULT_CONSOLE_PORT = 8088
SELECT_GROUP = "节点选择"
TEST_URL = "https://www.gstatic.com/generate_204"
RELAY_TIMEOUT = 30

# 组内伪节点(不是真实出口, 不能用来测速/切换)
PSEUDO_NODES = {"DIRECT", "REJECT", "PASS", "COMPATIBLE", "GLOBAL", "自动选择", "故障转移"}
# 订阅商夹带的「信息行」, 解析器会把它们当节点, 但实际不可用
INFO_MARKERS = ("剩余流量", "重置剩余", "套餐到期", "过期时间", "距离下次", "官网", "订阅")

PROTO_LABEL = {
    "vless": "VLESS",
    "vmess": "VMess",
    "hysteria2": "Hysteria2",
    "hysteria": "Hysteria",
    "trojan": "Trojan",
    "ss": "Shadowsocks",
    "ssr": "ShadowsocksR",
}


class ClashApiError(RuntimeError):
    """路由器代理接口调用失败(网络、令牌或路由器侧拒绝)。

    ``kind`` 用来区分失败层级, 调用方据此给用户不同措辞的提示:

      * ``network``  —— 工作台/路由器根本不可达(超时、连接被拒)。**不是**节点的问题,
        不能当成业务失败吞掉, 否则界面上会显示成「所有节点都超时」, 把用户引向
        完全错误的方向(实测踩到: 路由器重启期间批量测速显示 0/N 可用)。
      * ``rejected`` —— 路由器明确拒绝(令牌错、接口不在白名单、mihomo 没在运行)。
      * ``badjson``  —— 路由器返回了非 JSON(通常是被中间设备劫持的页面)。
    """

    def __init__(self, message, kind="unknown"):
        super().__init__(message)
        self.kind = kind


# --------------------------------------------------------------------- 纯函数
def is_pseudo_node(name):
    return (name or "").strip() in PSEUDO_NODES


def is_info_node(name):
    text = name or ""
    return any(marker in text for marker in INFO_MARKERS)


def is_real_node(name):
    return bool((name or "").strip()) and not is_pseudo_node(name) and not is_info_node(name)


def protocol_label(raw_type):
    """mihomo 的 proxies 类型 -> 展示名。"""
    key = str(raw_type or "").strip().lower()
    return PROTO_LABEL.get(key, key.upper() if key else "未知")


def selection_now(group_json):
    """读取选择组当前选中的节点名。"""
    return str((group_json or {}).get("now") or "")


def group_members(group_json):
    """选择组的候选列表(含伪节点与信息行, 由调用方过滤)。"""
    return [str(x) for x in ((group_json or {}).get("all") or [])]


def last_delay(proxy_entry):
    """从 /proxies 的 history 里取最近一次延迟(毫秒); 0 或缺失表示未测/失败。"""
    history = (proxy_entry or {}).get("history") or []
    if not isinstance(history, list) or not history:
        return None
    last = history[-1]
    if not isinstance(last, dict):
        return None
    try:
        delay = int(last.get("delay"))
    except (TypeError, ValueError):
        return None
    return delay if delay > 0 else None


def build_nodes(proxies, group_json):
    """把 /proxies 全量数据 + 选择组数据合成界面需要的节点列表。"""
    proxies = proxies or {}
    current = selection_now(group_json)
    nodes = []
    for name in group_members(group_json):
        if not is_real_node(name):
            continue
        entry = proxies.get(name)
        if not isinstance(entry, dict):
            continue
        raw_type = entry.get("type") or ""
        nodes.append({
            "name": name,
            "type": str(raw_type).lower(),
            "proto": protocol_label(raw_type),
            "delay": last_delay(entry),
            "alive": bool(entry.get("alive", True)),
            "current": name == current,
        })
    return nodes


def sort_nodes(nodes, by="delay", desc=False):
    """排序节点。

    ``by``: ``delay``(默认) / ``name`` / ``proto``。
    未测过或测速失败的节点**永远排在最后**, 即使开降序也一样 —— 否则点一下
    「延迟」列头, 一堆「—」就会跑到最上面挡住真正可用的节点。
    """
    nodes = list(nodes or [])
    if by == "name":
        return sorted(nodes, key=lambda n: n.get("name", ""), reverse=bool(desc))
    if by == "proto":
        return sorted(nodes, key=lambda n: (n.get("proto", ""), n.get("name", "")),
                      reverse=bool(desc))
    if desc:
        # 不用 reverse=True: 那样 "未测" 会被翻到最前面
        return sorted(nodes, key=lambda n: (n.get("delay") is None,
                                            -(n.get("delay") or 0),
                                            n.get("name", "")))
    return sorted(nodes, key=lambda n: (n.get("delay") is None, n.get("delay") or 0,
                                        n.get("name", "")))


def format_delay(delay):
    if delay is None:
        return "—"
    if delay <= 0:
        return "超时"
    if delay < 1000:
        return "%d ms" % delay
    return "%.1f s" % (delay / 1000.0)


def fastest_node(nodes):
    """挑出当前可用节点里延迟最低的一个; 没有测速结果则返回 None。"""
    alive = [n for n in nodes if n.get("delay") is not None and n.get("alive", True)]
    if not alive:
        return None
    return sort_nodes(alive)[0]


def throughput_mbps(byte_count, seconds):
    """字节数 / 秒 -> Mbps(用于下载测速结果展示)。"""
    if not seconds or seconds <= 0 or not byte_count:
        return 0.0
    return round(byte_count * 8 / seconds / 1_000_000.0, 2)


def protocol_choices(nodes, include_all=True):
    """从实际节点派生协议筛选项。

    之前界面上是硬编码 ``["全部","VLESS","Hysteria2"]``, 一旦订阅里出现 VMess/
    Trojan, 那些节点就只能靠「全部」看, 没法单独筛出来。
    """
    labels = sorted({n.get("proto") for n in (nodes or []) if n.get("proto")})
    return (["全部"] + labels) if include_all else labels


def error_hint(exc):
    """把 ClashApiError 的 kind 翻译成可执行的排查建议(给界面用)。"""
    kind = getattr(exc, "kind", "unknown")
    if kind == "network":
        return ("连不上路由器工作台。检查: ① 路由器是否在线、电脑有没有接到它的网络; "
                "② 连接参数里的主机与端口是否填对。")
    if kind == "rejected":
        return ("路由器拒绝了请求。常见原因: ① 工作台令牌与路由器不一致"
                "(默认 20050927); ② 路由器上 mihomo 没在运行; "
                "③ 代理接口脚本 proxy-api.sh 没部署。")
    if kind == "badjson":
        return ("路由器返回的是网页而不是 JSON, 通常是被校园网门户劫持了: "
                "确认当前连的是校园网、且本机没有挂其它代理。")
    return ""


# --------------------------------------------------------------------- 网络
def _encode_path(path):
    """API 路径 -> 交给 curl 的百分号编码形式(单层)。

    节点名可能含中文/emoji/空格, 必须先编码成 ASCII 再进 URL; CGI 侧不做解码,
    直接把这段 ASCII 拼进 ``http://127.0.0.1:9091/<path>``。
    """
    return quote(str(path).lstrip("/"), safe="/")


def _relay_body(token, path, method="GET", name=None):
    """构造 CGI 需要的纯 ASCII JSON 请求(节点名走 base64, 绕开 busybox 解码限制)。"""
    payload = {
        "token": str(token or ""),
        "path": _encode_path(path),
        "method": str(method or "GET"),
    }
    if name is not None:
        payload["name_b64"] = base64.b64encode(str(name).encode("utf-8")).decode("ascii")
    return json.dumps(payload, ensure_ascii=True).encode("utf-8")


def relay_request(host, port, token, path, method="GET", name=None, timeout=RELAY_TIMEOUT):
    """调用路由器上的 CGI 转发端点并返回解析后的 JSON。"""
    url = "http://%s:%s%s" % (host, port, CGI_PATH)
    req = urlrequest.Request(
        url, data=_relay_body(token, path, method, name), method="POST",
        headers={"Content-Type": "application/json"})
    try:
        opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", "replace")
    except HTTPError as exc:
        # 能连上工作台但 HTTP 出错(404/500...) —— 属于配置/部署问题
        raise ClashApiError("路由器代理接口返回 HTTP %s" % exc.code,
                            kind="rejected") from exc
    except (URLError, OSError) as exc:
        raise ClashApiError("路由器代理接口不可达: %s" % exc, kind="network") from exc
    text = (raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except ValueError as exc:
        raise ClashApiError("路由器返回了非 JSON 响应", kind="badjson") from exc
    if isinstance(payload, dict) and payload.get("ok") is False:
        raise ClashApiError(payload.get("msg") or "路由器拒绝了请求", kind="rejected")
    return payload


def api_version(host, port, token, timeout=12):
    return relay_request(host, port, token, "version", timeout=timeout)


def api_proxies(host, port, token, timeout=RELAY_TIMEOUT):
    return (relay_request(host, port, token, "proxies", timeout=timeout) or {}).get("proxies") or {}


def api_group(host, port, token, group=SELECT_GROUP, timeout=12):
    return relay_request(host, port, token, "proxies/" + group, timeout=timeout)


def api_select(host, port, token, name, group=SELECT_GROUP, timeout=20):
    return relay_request(host, port, token, "proxies/" + group,
                         method="PUT", name=name, timeout=timeout)


def api_delay(host, port, token, node, timeout=25):
    """测试单个节点的延迟(毫秒); 节点握手失败返回 None。

    注意**不吞 ClashApiError**: 节点不通是正常业务结果(mihomo 返回带 ``message``
    的 JSON, 没有 ``delay`` 字段), 走下面 ``int(None)`` 那条路返回 None;
    而抛异常意味着「路由器/工作台/mihomo 本身出问题」, 那是环境故障, 必须让
    调用方看见 —— 否则批量测速会把路由器重启误报成「52 个节点全挂了」。
    """
    path = "proxies/%s/delay" % node
    data = relay_request(host, port, token, path, timeout=timeout)
    try:
        delay = int((data or {}).get("delay"))
    except (TypeError, ValueError):
        return None
    return delay if delay > 0 else None


def sniff_local_proxy(host, proxy_port=7890, timeout=10):
    """从本机经路由器显式代理访问一次 generate_204, 返回 HTTP 状态码(失败 None)。"""
    opener = urlrequest.build_opener(urlrequest.ProxyHandler({
        "http": "http://%s:%s" % (host, proxy_port),
        "https": "http://%s:%s" % (host, proxy_port),
    }))
    try:
        with opener.open(TEST_URL, timeout=timeout) as resp:
            return resp.status
    except HTTPError as exc:
        return exc.code
    except (URLError, OSError):
        return None
