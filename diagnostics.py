# -*- coding: utf-8 -*-
"""校园网会话诊断工具 - 独立可复用
用途: 分析当前校园网会话归属、检测被踢状态、辅助防踢功能排查
基于对 Dr.COM E-Portal 4.0 登录响应 (dr1003 JSON) 的实测解码:
  ss1 = 会话 MAC (当前占用校园网名额的设备)
  ss4 = 来源 MAC (当前发起请求的设备)
  ss5 = 会话校园网 IP
  msga = 会话状态提示 (clientip online / 其他)
本模块供诊断、测试和 GUI 设备面板使用; 不修改任何网络状态。
"""
import json
import re
import urllib.request
import urllib.parse

# 尝试导入核心模块做配置读取; 失败时提供最小编码工具
try:
    import keepalive_core as core
except Exception:
    core = None


def build_login_url(profile):
    """按档案构造 Dr.COM drcom/login URL (与 keepalive_core.try_login 同构)"""
    if core:
        suffix = core.SUFFIX.get(profile.get("login_type", "cmcc"), "@cmcc")
        host = profile.get("auth_url", "http://192.168.16.3/").split("/")[2]
    else:
        suffix = {"unicom": "@unicom", "cmcc": "@cmcc", "teacher": ""}.get(
            profile.get("login_type", "cmcc"), "@cmcc")
        host = profile.get("auth_url", "http://192.168.16.3/").split("/")[2]
    params = [
        ("callback", "dr1003"),
        ("DDDDD", profile["username"] + suffix),
        ("upass", profile["password"]),
        ("0MKKey", "123456"),
        ("R1", "0"), ("R2", ""), ("R3", "0"), ("R6", "0"),
        ("para", "00"), ("v6ip", ""),
        ("terminal_type", "1"), ("lang", "zh-cn"),
        ("jsVersion", "4.1.3"), ("v", "2509"),
    ]
    return "http://%s/drcom/login?%s" % (host, urllib.parse.urlencode(params))


def login_probe(profile, timeout=15):
    """执行一次登录探测, 返回解码后的 Dr.COM JSON (不改变会话语义; 同源IP=刷新续期)。
    返回 dict: result/msg/ss1/ss4/ss5/msga/raw
    失败返回 None (网络不可达或账号异常)。"""
    url = build_login_url(profile)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
        "Referer": url.split("/drcom/")[0] + "/"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("gbk", errors="replace")
        m = re.search(r"dr1003\((\{.*\})\)", body)
        if not m:
            return {"raw": body[:200]}
        data = json.loads(m.group(1))
        data["raw"] = body[:200]
        return data
    except Exception as exc:
        return {"error": str(exc)}


def local_macs():
    """本机所有网卡 MAC (小写)。"""
    if core and core.IS_MACOS:
        out = core._run_decode(["ifconfig", "-a"])
    else:
        import subprocess
        out = subprocess.run(["ifconfig", "-a"], capture_output=True, text=True).stdout
    macs = set()
    for m in re.finditer(r"ether\s+([0-9a-f:]{17})", out):
        macs.add(m.group(1).lower())
    return macs


def analyze(profile):
    """完整分析当前会话: 返回可读报告 dict"""
    data = login_probe(profile)
    if not data or "error" in data:
        return {"ok": False, "detail": data.get("error", data.get("raw", "无响应"))}
    macs = local_macs()
    ss1 = data.get("ss1", "")  # 会话MAC
    ss4 = data.get("ss4", "")  # 来源MAC
    def is_local(mac):
        mac = (mac or "").lower()
        return bool(mac) and any(mac == m or mac.startswith(m[:8]) for m in macs)
    return {
        "ok": True,
        "result": data.get("result"),
        "msg": data.get("msg"),
        "uid": data.get("uid"),
        "session_ip": data.get("ss5"),
        "session_mac": ss1,
        "source_mac": ss4,
        "session_is_local": is_local(ss1),
        "source_is_local": is_local(ss4),
        "note": data.get("msga"),
        "raw": data.get("raw", ""),
    }


if __name__ == "__main__":
    import sys, os
    if core:
        core.BASE_DIR = os.path.expanduser("~/Library/Application Support/CampusNetManager")
        core.CONFIG_PATH = os.path.join(core.BASE_DIR, "config.json")
        cfg = core.load_config()
        prof = next((p for p in cfg.get("profiles", []) if p.get("username")), None)
        if prof:
            print(json.dumps(analyze(prof), ensure_ascii=False, indent=2))
        else:
            print("无可用档案")
