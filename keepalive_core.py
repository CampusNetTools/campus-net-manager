# -*- coding: utf-8 -*-
"""
校园网连接管家 - 核心模块 (KeepAlive Core)
- 多档案: 每个 WiFi/接入环境一套配置, 按 SSID 自动匹配
- 环境识别: 认证服务器可达 = 校园网环境; 不可达 = 非校园网, 自动休眠不误登
- 接入方式无关: 有线直连 / WiFi 直连 / 经路由器中继 均可工作
- 检测: 认证页标题 + 外网连通 双重检测; 掉线自动重登 (Dr.COM drcom/login)
CLI 和桌面 App 共用本模块
"""
import json
import os
import re
import copy
import socket
import subprocess
import sys
import threading
import time
import datetime
import concurrent.futures
import ipaddress
import plistlib
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import uuid

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"
_MAC_APP_SUPPORT = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "CampusNetManager")

# 打包成 exe 后, 配置/日志跟随 exe 所在目录 (否则会写到临时解压目录导致丢失)
if getattr(sys, "frozen", False) and IS_MACOS:
    # .app 的 Contents/MacOS 目录不是用户数据目录，不能把配置写进应用包。
    BASE_DIR = _MAC_APP_SUPPORT
elif getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "keepalive.log")
LOCK_PATH = os.path.join(BASE_DIR, "keepalive.lock")
HISTORY_PATH = os.path.join(BASE_DIR, "network_history.jsonl")
KEYCHAIN_SERVICE = "com.campusnettools.campusnetmanager"

DEFAULT_AUTH_URL = "http://192.168.16.3/"
LIDA_PROFILE_ID = "lida-campus"
LIDA_PROFILE_NAME = "立达校园网"
LIDA_SSID = "LIDA-UNIVERSITY"

SUFFIX = {"unicom": "@unicom", "cmcc": "@cmcc", "teacher": ""}
METHOD_NAME = {"unicom": "联通", "cmcc": "移动", "teacher": "教师"}


# ---------- 配置 ----------
def default_profile(name="校园网"):
    return {
        "name": name,
        "ssid": "",            # 绑定的 WiFi 名, 留空=默认档案(任意网络)
        "username": "",
        "password": "",
        "login_type": "cmcc",  # cmcc / unicom / teacher
        "auth_url": DEFAULT_AUTH_URL,
        "interval": 60,
    }


def default_preferences():
    return {
        "history_enabled": False,
        "kick_guard": True,   # 防踢: 周期性刷新登录, 让本机/路由器会话保持最新不被挤掉
        "notifications": {
            "enabled": True,
            "disconnect": True,
            "recovery": True,
            "failure": True,
            "device": True,
        },
    }


def ensure_preferences(cfg):
    changed = False
    defaults = default_preferences()
    if "history_enabled" not in cfg:
        cfg["history_enabled"] = defaults["history_enabled"]
        changed = True
    notifications = cfg.setdefault("notifications", {})
    for key, value in defaults["notifications"].items():
        if key not in notifications:
            notifications[key] = value
            changed = True
    return changed


def _profile_secret_id(profile):
    secret_id = profile.get("secret_id")
    if not secret_id:
        secret_id = "profile-" + uuid.uuid4().hex
        profile["secret_id"] = secret_id
    return secret_id


def keychain_set(secret_id, password):
    """把密码写入当前用户的 macOS 钥匙串。"""
    if not IS_MACOS or not secret_id:
        return False
    result = subprocess.run(
        ["/usr/bin/security", "add-generic-password", "-U", "-s", KEYCHAIN_SERVICE,
         "-a", secret_id, "-w", password], capture_output=True, timeout=10)
    return result.returncode == 0


def keychain_get(secret_id):
    if not IS_MACOS or not secret_id:
        return ""
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-w", "-s", KEYCHAIN_SERVICE,
         "-a", secret_id], capture_output=True, timeout=10)
    return result.stdout.decode("utf-8", errors="replace").rstrip("\r\n") if result.returncode == 0 else ""


def keychain_delete(secret_id):
    if not IS_MACOS or not secret_id:
        return False
    result = subprocess.run(
        ["/usr/bin/security", "delete-generic-password", "-s", KEYCHAIN_SERVICE,
         "-a", secret_id], capture_output=True, timeout=10)
    return result.returncode == 0


def lida_profile():
    """立达学校内置档案；账号密码保持空白，由用户本人填写。"""
    profile = default_profile(LIDA_PROFILE_NAME)
    profile.update({
        "preset": LIDA_PROFILE_ID,
        "ssid": LIDA_SSID,
        "gateway": "",
        "auth_url": DEFAULT_AUTH_URL,
        "login_type": "cmcc",
        "interval": 60,
    })
    return profile


def ensure_lida_profile(cfg):
    """无损补齐立达专属档案，保留已有账号、密码和用户自定义档案。"""
    profiles = cfg.setdefault("profiles", [])
    for profile in profiles:
        if (profile.get("preset") == LIDA_PROFILE_ID
                or (profile.get("ssid") or "").strip().upper() == LIDA_SSID):
            if profile.get("preset") != LIDA_PROFILE_ID:
                profile["preset"] = LIDA_PROFILE_ID
                return True
            return False

    # 将早期默认“校园网”档案原位升级，避免复制账号密码或制造重复档案。
    for profile in profiles:
        if (profile.get("name") in ("校园网", "立达校园网WiFi")
                and profile.get("auth_url", DEFAULT_AUTH_URL) == DEFAULT_AUTH_URL
                and not profile.get("ssid")):
            old_name = profile.get("name")
            profile.update({"name": LIDA_PROFILE_NAME, "ssid": LIDA_SSID,
                            "gateway": profile.get("gateway", ""), "preset": LIDA_PROFILE_ID})
            if cfg.get("active_profile") == old_name:
                cfg["active_profile"] = LIDA_PROFILE_NAME
            return True

    profiles.insert(0, lida_profile())
    if not cfg.get("active_profile"):
        cfg["active_profile"] = LIDA_PROFILE_NAME
    return True


def load_config():
    if not os.path.exists(CONFIG_PATH):
        cfg = {"profiles": [lida_profile()], "active_profile": LIDA_PROFILE_NAME,
               "auth_history": [DEFAULT_AUTH_URL]}
        ensure_preferences(cfg)
        return cfg
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    changed = False
    # 兼容旧版单档案结构
    if "profiles" not in cfg:
        p = default_profile("校园网")
        p.update({k: cfg.get(k) for k in ("username", "password", "login_type", "interval") if cfg.get(k) is not None})
        cfg = {"profiles": [p], "active_profile": p["name"]}
        changed = True
    if ensure_lida_profile(cfg):
        changed = True
    if ensure_preferences(cfg):
        changed = True
    # 首次升级时把旧版明文密码迁移进钥匙串；配置文件只保留引用。
    if IS_MACOS:
        for profile in cfg.get("profiles", []):
            password = profile.get("password", "")
            secret_id = _profile_secret_id(profile)
            if password and keychain_set(secret_id, password):
                profile["password_store"] = "keychain"
                changed = True
            elif profile.get("password_store") == "keychain":
                profile["password"] = keychain_get(secret_id)
    if changed:
        save_config(cfg)
    return cfg


def save_config(cfg, sync_secrets=False):
    ensure_preferences(cfg)
    disk_cfg = copy.deepcopy(cfg)
    if IS_MACOS:
        for profile, disk_profile in zip(cfg.get("profiles", []), disk_cfg.get("profiles", [])):
            secret_id = _profile_secret_id(profile)
            disk_profile["secret_id"] = secret_id
            password = profile.get("password", "")
            if password and (sync_secrets or profile.get("password_store") != "keychain"):
                if not keychain_set(secret_id, password):
                    raise RuntimeError("无法把密码保存到 macOS 钥匙串")
                profile["password_store"] = "keychain"
            if profile.get("password_store") == "keychain":
                disk_profile["password"] = ""
                disk_profile["password_store"] = "keychain"
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(disk_cfg, f, ensure_ascii=False, indent=2)


def config_for_export(cfg):
    """导出可迁移但不含密码的安全配置。"""
    exported = copy.deepcopy(cfg)
    for profile in exported.get("profiles", []):
        profile["password"] = ""
        profile.pop("secret_id", None)
        profile.pop("password_store", None)
    return exported


def notification_enabled(cfg, category):
    settings = cfg.get("notifications", {})
    return settings.get("enabled", True) and settings.get(category, True)


def normalized_notification_settings(enabled, categories):
    """总开关关闭时，所有子通知同步关闭。"""
    result = {"enabled": bool(enabled)}
    result.update({key: bool(value) if enabled else False for key, value in categories.items()})
    return result


def record_network_history(cfg, event, message, **details):
    if not cfg.get("history_enabled", False):
        return False
    item = {"time": now_str(), "event": event, "message": message, "details": details}
    try:
        with open(HISTORY_PATH, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
        if os.path.getsize(HISTORY_PATH) > 2 * 1024 * 1024:
            with open(HISTORY_PATH, "r", encoding="utf-8", errors="replace") as handle:
                lines = handle.readlines()[-5000:]
            with open(HISTORY_PATH, "w", encoding="utf-8") as handle:
                handle.writelines(lines)
        return True
    except Exception:
        return False


def summarize_network_history(days=7):
    """将技术事件汇总成普通用户可以理解的稳定性报告。"""
    cutoff = datetime.datetime.now() - datetime.timedelta(days=days)
    events = []
    try:
        with open(HISTORY_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                try:
                    item = json.loads(line)
                    when = datetime.datetime.strptime(item["time"], "%Y-%m-%d %H:%M:%S")
                    if when >= cutoff:
                        events.append(item)
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    counts = {key: 0 for key in ("online", "disconnect", "recovery", "failure", "vpn_issue")}
    for item in events:
        if item.get("event") in counts:
            counts[item["event"]] += 1
    checks = counts["online"] + counts["disconnect"] + counts["vpn_issue"]
    stable = (counts["online"] * 100.0 / checks) if checks else None
    if not events:
        summary = "还没有可汇总的网络记录。开启保存后，软件会在这里解释最近的稳定情况。"
    elif counts["failure"]:
        summary = "网络近期不太稳定，有自动恢复失败的情况，建议检查账号、路由器或校园出口。"
    elif counts["disconnect"] or counts["vpn_issue"]:
        summary = "网络偶尔出现波动，大多数时候软件能够继续检测或自动恢复。"
    else:
        summary = "网络整体稳定，最近没有记录到明显掉线。"
    return {"days": days, "events": len(events), "counts": counts, "stable_percent": stable,
            "summary": summary}


# ---------- 环境识别 ----------
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def _run_decode(cmd, timeout=10):
    """运行命令并智能解码输出。
    netsh/reg/tasklist 等输出编码随代码页变化 (GBK 或 UTF-8),
    先按 UTF-8 严格解码, 失败再回退 GBK, 避免中文 SSID 乱码。"""
    try:
        kwargs = {"capture_output": True, "timeout": timeout}
        if IS_WINDOWS:
            kwargs["creationflags"] = _NO_WINDOW
        r = subprocess.run(cmd, **kwargs)
        out = r.stdout or b""
        try:
            return out.decode("utf-8")
        except UnicodeDecodeError:
            return out.decode("gbk", errors="replace")
    except Exception:
        return ""


def get_ssid():
    """返回当前连接的 WiFi SSID; 无线未连接/有线接入返回 None"""
    if IS_MACOS:
        device = None
        ports = _run_decode(["networksetup", "-listallhardwareports"])
        for block in ports.split("\n\n"):
            if "Hardware Port: Wi-Fi" in block:
                m = re.search(r"Device:\s*(\S+)", block)
                if m:
                    device = m.group(1)
                    break
        if not device:
            return None
        out = _run_decode(["networksetup", "-getairportnetwork", device]).strip()
        # 英文/中文系统均取最后一个冒号后的 SSID；未连接时 networksetup 会给出说明。
        if not out or "not associated" in out.lower() or "没有关联" in out:
            return None
        return out.rsplit(":", 1)[-1].strip() or None
    out = _run_decode(["netsh", "wlan", "show", "interfaces"])
    for line in out.splitlines():
        if "SSID" in line and "BSSID" not in line and ":" in line:
            val = line.split(":", 1)[-1].strip()
            return val or None
    return None


def get_gateway():
    """返回当前默认网关 IP (路由器管理地址通常就是它)"""
    if IS_MACOS:
        gateway, _ = get_physical_route()
        return gateway
    out = _run_decode(["route", "print", "-4"])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            return parts[2]
    return None


def get_physical_route():
    """返回 macOS 实际局域网的 (网关, 网卡)，忽略 utun 等 VPN 默认路由。"""
    if not IS_MACOS:
        return get_gateway(), None
    out = _run_decode(["netstat", "-rn", "-f", "inet"])
    for line in out.splitlines():
        parts = line.split()
        if (len(parts) >= 4 and parts[0] == "default"
                and re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", parts[1])
                and not parts[3].startswith("utun")):
            return parts[1], parts[3]
    return None, None


def get_physical_interface():
    """返回当前承载校园网的物理网卡名称，例如 en0。"""
    _, interface = get_physical_route()
    return interface


def vpn_active():
    """检测是否存在活跃 VPN 隧道；仅用于提示测速路径。"""
    if IS_MACOS:
        out = _run_decode(["netstat", "-rn", "-f", "inet"])
        return any(len(line.split()) >= 4 and line.split()[0] == "default"
                   and line.split()[3].startswith("utun") for line in out.splitlines())
    out = _run_decode(["route", "print", "-4"])
    return any(mark in out.lower() for mark in ("wireguard", "wintun", "tap-windows", "vpn"))


def automatic_speed_test_plan():
    """按当前 VPN 状态决定测速路径；界面无需让用户理解或选择底层网卡。"""
    active = vpn_active()
    compare = bool(active and IS_MACOS)
    return {
        "vpn_active": active,
        "compare": compare,
        "paths": ("current", "physical") if compare else ("current",),
    }


def _curl_speed_request(url, method="GET", upload_bytes=0, physical=False, timeout=20,
                        allow_timed_sample=False):
    """执行一次有限流量的 curl 测量，返回 curl 的结构化计时字段。"""
    curl = "/usr/bin/curl" if IS_MACOS else "curl.exe"
    command = [curl, "--silent", "--show-error", "--location", "--max-time", str(timeout),
               "--output", os.devnull,
               "--write-out", "%{http_code}\t%{time_namelookup}\t%{time_connect}\t%{time_appconnect}\t%{time_pretransfer}\t%{time_starttransfer}\t%{time_total}\t%{size_download}\t%{size_upload}\t%{remote_ip}"]
    if physical and IS_MACOS:
        interface = get_physical_interface()
        if not interface:
            raise RuntimeError("未找到可用的物理网卡")
        command.extend(["--noproxy", "*", "--interface", interface])
    payload = None
    if method == "POST":
        command.extend(["--request", "POST", "--header", "Content-Type: application/octet-stream",
                        "--data-binary", "@-"])
        payload = b"\0" * upload_bytes
    command.append(url)
    kwargs = {"input": payload, "capture_output": True, "timeout": timeout + 3}
    if IS_WINDOWS:
        kwargs["creationflags"] = _NO_WINDOW
    result = subprocess.run(command, **kwargs)
    parts = result.stdout.decode("ascii", errors="replace").strip().split("\t")
    timed_sample = False
    if result.returncode != 0:
        # curl 在 --max-time 到期时仍会输出完整计时数据。测速流量较慢但已经
        # 持续传输时，这本身就是有效的限时测速样本，不应误报为断网。
        try:
            transferred = float(parts[7]) + float(parts[8])
            elapsed = float(parts[6])
            timed_sample = (allow_timed_sample and result.returncode == 28
                            and len(parts) == 10 and parts[0].startswith("2")
                            and transferred >= 65536 and elapsed >= 5.0)
        except (ValueError, IndexError):
            timed_sample = False
        if not timed_sample:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "测速请求失败")
    if len(parts) != 10 or not parts[0].startswith("2"):
        raise RuntimeError("测速服务器返回异常（HTTP %s）" % (parts[0] if parts else "?"))
    return {
        "status": int(parts[0]), "lookup": float(parts[1]), "connect": float(parts[2]),
        "appconnect": float(parts[3]), "pretransfer": float(parts[4]), "ttfb": float(parts[5]),
        "total": float(parts[6]), "downloaded": float(parts[7]), "uploaded": float(parts[8]),
        "remote_ip": parts[9], "timed_sample": timed_sample,
    }


def _latency_from_timing(sample):
    """优先使用 TCP 建连往返，避免把服务端首字节等待误当网络延迟。"""
    connect = sample.get("connect", 0.0)
    lookup = sample.get("lookup", 0.0)
    appconnect = sample.get("appconnect", 0.0)
    tcp_latency = max(0.0, connect - lookup)
    tls_time = max(0.0, appconnect - connect)
    # TUN/本地代理可能在本机立即接收 TCP，使 connect 接近 0；此时用 TLS 握手
    # 的半程时间估算 RTT，比直接使用服务端 TTFB 更接近真实链路延迟。
    if tcp_latency < 0.005 and tls_time > 0.020:
        return tls_time * 500.0
    if tcp_latency > 0:
        return tcp_latency * 1000.0
    if appconnect > connect:
        return (appconnect - connect) * 500.0
    return sample.get("ttfb", 0.0) * 1000.0


def score_speed_quality(latency_ms, jitter_ms, download_mbps, upload_mbps, success_rate):
    """给出可解释的 0-100 网络质量分，不替代专业 SLA 测试。"""
    score = 100.0
    score -= max(0.0, latency_ms - 30.0) * 0.22
    score -= max(0.0, jitter_ms - 5.0) * 0.8
    score -= max(0.0, 30.0 - download_mbps) * 0.55
    score -= max(0.0, 8.0 - upload_mbps) * 1.0
    score -= max(0.0, 100.0 - success_rate) * 0.8
    score = max(0, min(100, int(round(score))))
    grade = "优秀" if score >= 90 else "流畅" if score >= 75 else "一般" if score >= 60 else "较差"
    return score, grade


def run_speed_test(path="current", download_bytes=10000000, upload_bytes=2000000, progress=None):
    """限流量测速。path=current 测当前/VPN路径，physical 在 macOS 上绑定物理网卡绕过 VPN。"""
    if path not in ("current", "physical"):
        raise ValueError("未知测速路径")
    physical = path == "physical"
    if physical and not IS_MACOS:
        raise RuntimeError("绕过 VPN 的物理路径测速当前仅支持 macOS")
    notify = progress or (lambda _text: None)
    base = "https://speed.cloudflare.com"
    latency = []
    remote_ip = ""
    sample_count = 6
    notify("正在测量延迟、抖动和请求成功率…")
    def latency_probe(index):
        try:
            return _curl_speed_request("%s/__down?bytes=0&r=%d" % (base, index),
                                       physical=physical, timeout=8)
        except Exception:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        samples = list(pool.map(latency_probe, range(sample_count)))
    for sample in samples:
        if sample:
            latency.append(_latency_from_timing(sample))
            remote_ip = sample["remote_ip"] or remote_ip
    if len(latency) < 2:
        raise RuntimeError("延迟探测成功次数不足")
    notify("正在测量下载速度（约 %.0f MB）…" % (download_bytes / 1000000.0))
    down = _curl_speed_request("%s/__down?bytes=%d" % (base, download_bytes),
                               physical=physical, timeout=25, allow_timed_sample=True)
    notify("正在测量上传速度（约 %.0f MB）…" % (upload_bytes / 1000000.0))
    up = _curl_speed_request("%s/__up" % base, method="POST", upload_bytes=upload_bytes,
                             physical=physical, timeout=25, allow_timed_sample=True)
    down_mbps = (down["downloaded"] * 8.0 / 1000000.0) / max(down["total"], 0.001)
    up_mbps = (up["uploaded"] * 8.0 / 1000000.0) / max(up["total"], 0.001)
    latency_median = sorted(latency)[len(latency) // 2]
    jitter = sum(abs(latency[i] - latency[i - 1]) for i in range(1, len(latency))) / (len(latency) - 1)
    success_rate = len(latency) * 100.0 / sample_count
    score, grade = score_speed_quality(latency_median, jitter, down_mbps, up_mbps, success_rate)
    return {
        "path": path,
        "path_label": ("未经过 VPN（直连网络）" if physical else
                       "当前系统路径（%s）" % ("经过 VPN" if vpn_active() else "未检测到 VPN")),
        "interface": get_physical_interface() if physical else "",
        "latency_ms": latency_median,
        "jitter_ms": jitter,
        "success_rate": success_rate,
        "download_mbps": down_mbps,
        "upload_mbps": up_mbps,
        "quality_score": score,
        "quality_grade": grade,
        "remote_ip": down["remote_ip"] or remote_ip,
        "traffic_mb": (down["downloaded"] + up["uploaded"]) / 1000000.0,
    }


# 常见路由器品牌 OUI (MAC 前 3 字节) 库, 用于识别路由器品牌给对应操作指引
OUI_BRANDS = {
    "D4:02:BC": "华为", "88:6B:0F": "华为", "90:9A:4A": "华为", "C0:25:06": "华为",
    "44:8A:5B": "华为", "4C:0F:6E": "华为", "28:C5:D2": "华为", "A8:0C:63": "华为",
    "64:09:80": "小米", "8C:DE:F9": "小米", "2C:B2:1A": "小米", "78:11:DC": "小米",
    "28:6C:07": "小米", "DC:D2:FC": "小米", "84:18:88": "小米", "02:0C:51": "小米",
    "50:FA:84": "TP-LINK", "C0:4A:00": "TP-LINK", "3C:84:6A": "TP-LINK",
    "34:96:72": "TP-LINK", "18:A6:F7": "TP-LINK", "08:10:76": "TP-LINK",
    "00:26:5A": "水星", "04:9F:CA": "水星", "00:B0:0C": "腾达", "C8:3A:35": "腾达",
    "00:0D:88": "迅捷(FAST)", "28:00:11": "迅捷(FAST)", "E8:48:B7": "迅捷(FAST)",
    "5C:96:9D": "迅捷(FAST)", "D4:EE:07": "迅捷(FAST)",
    "04:21:E1": "华硕", "10:BF:48": "华硕", "20:4E:7F": "网件", "30:46:9A": "网件",
    "44:37:E6": "中兴", "00:19:C0": "中兴", "00:E0:4C": "360", "00:0C:E7": "联想",
    "D4:46:3A": "华为", "74:7D:24": "斐讯", "00:1A:A9": "D-Link", "28:10:7B": "D-Link",
}


def _arp_entries():
    """返回 ARP 表中的 (IPv4, MAC)；兼容 Windows 与 macOS 输出。"""
    entries = []
    # -n 禁止反向 DNS；校园网 ARP 项很多时可避免几十秒阻塞。
    for line in _run_decode(["arp", "-an"], timeout=3).splitlines():
        mac_style = re.search(r"\((\d{1,3}(?:\.\d{1,3}){3})\)\s+at\s+([0-9a-fA-F:-]+)", line)
        if mac_style:
            entries.append((mac_style.group(1), mac_style.group(2).replace("-", ":")))
            continue
        parts = line.split()
        if len(parts) >= 2 and re.match(r"^\d{1,3}(?:\.\d{1,3}){3}$", parts[0]):
            entries.append((parts[0], parts[1].replace("-", ":")))
    return entries


def get_gateway_mac():
    """通过 arp 表查默认网关的 MAC 地址"""
    gw = get_gateway()
    if not gw:
        return None
    for ip, mac in _arp_entries():
        if ip == gw:
            return mac
    return None


def get_router_admin_url():
    """探测路由器管理页地址(中继/桥接后原 192.168.x.1 可能失效)。
    NAT 模式: 管理地址=默认网关;
    桥接/中继模式: 网关是校园网, 从 ARP 表逐个试 HTTP, 找到开管理页的路由器 IP。"""
    import urllib.request
    gw = get_gateway()
    candidates = []
    if gw:
        candidates.append((gw, get_gateway_mac() or ""))
    for ip, mac in _arp_entries():
        if ip != gw and not ip.startswith(("224.", "239.", "255.", "127.")):
            candidates.append((ip, mac))
    seen, uniq = set(), []
    for ip, mac in candidates:
        if ip not in seen:
            seen.add(ip)
            uniq.append((ip, mac))
    router_words = (b"router", b"openwrt", b"luci", b"tp-link", b"tplink", b"xiaomi",
                    b"huawei", b"tenda", b"mercury", b"asus", b"netgear", b"d-link")

    def probe(item):
        ip, mac = item
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            req = urllib.request.Request("http://%s/" % ip,
                                         headers={"User-Agent": "Mozilla/5.0"}, method="GET")
            resp = opener.open(req, timeout=0.8)
            body = resp.read(32768).lower()
            known_oui = bool(mac and mac[:8].upper() in OUI_BRANDS)
            # 默认网关可以是家用路由器；其他 ARP 主机必须有路由器品牌/OUI 证据，
            # 防止把校园网内任意 Web 服务误判成管理页。
            if len(body) > 200 and b"<" in body and (
                    ip == gw or known_oui or any(word in body for word in router_words)):
                return "http://%s/" % ip
        except Exception:
            pass
        return None

    candidates = uniq[:12]
    if candidates:
        with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(candidates))) as pool:
            for found in pool.map(probe, candidates):
                if found:
                    return found
    return "http://%s/" % gw if gw else None


def _private_http_url(url):
    """只允许读取局域网 HTTP(S) 地址，避免把发现结果带到公网或任意协议。"""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return False
        addr = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        return addr.is_private or addr.is_link_local or addr.is_loopback
    except Exception:
        return False


def parse_upnp_device_description(payload):
    """解析 UPnP 设备描述。独立函数便于测试，不执行任何写操作。"""
    result = {}
    try:
        root = ET.fromstring(payload)
        for elem in root.iter():
            key = elem.tag.rsplit("}", 1)[-1]
            if key in ("friendlyName", "manufacturer", "modelName", "modelNumber",
                       "serialNumber", "presentationURL") and elem.text:
                result[key] = elem.text.strip()
    except (ET.ParseError, TypeError, ValueError):
        pass
    return result


def discover_router_upnp(timeout=1.2):
    """通过 SSDP/UPnP 只读发现路由器公开的厂商和型号信息。"""
    message = ("M-SEARCH * HTTP/1.1\r\n"
               "HOST: 239.255.255.250:1900\r\n"
               "MAN: \"ssdp:discover\"\r\n"
               "MX: 1\r\n"
               "ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n\r\n")
    locations = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.settimeout(timeout)
        sock.sendto(message.encode("ascii"), ("239.255.255.250", 1900))
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                break
            text = data.decode("iso-8859-1", errors="replace")
            found = re.search(r"^location:\s*(\S+)", text, re.I | re.M)
            if found and found.group(1) not in locations and _private_http_url(found.group(1)):
                locations.append(found.group(1))
    except OSError:
        pass
    finally:
        sock.close()

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    for location in locations[:8]:
        try:
            req = urllib.request.Request(location, headers={"User-Agent": "CampusNetManager"})
            with opener.open(req, timeout=2) as response:
                info = parse_upnp_device_description(response.read(262144))
            if info:
                info["descriptionURL"] = location
                return info
        except Exception:
            continue
    return {}


def inspect_router_admin(url):
    """只读检查管理页标题/服务标识；不会登录、改配置或提交表单。"""
    result = {"url": url or "", "title": "", "server": "", "openwrt": False}
    if not url or not _private_http_url(url):
        return result
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CampusNetManager"})
        with opener.open(req, timeout=2) as response:
            raw = response.read(131072)
            result["url"] = response.geturl()
            result["server"] = response.headers.get("Server", "")[:120]
        text = raw.decode("utf-8", errors="replace")
        title = re.search(r"<title[^>]*>(.*?)</title>", text, re.I | re.S)
        if title:
            result["title"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", title.group(1))).strip()[:160]
        signals = " ".join((result["title"], result["server"], text[:32768])).lower()
        result["openwrt"] = any(mark in signals for mark in ("openwrt", "luci", "/cgi-bin/luci"))
    except Exception:
        pass
    return result


def router_fingerprint(gateway=None, mac=None):
    """生成不含凭据的路由器标识；优先用 MAC，退化为网关地址。"""
    gateway = get_gateway() if gateway is None else gateway
    mac = get_gateway_mac() if mac is None else mac
    return (mac or gateway or "unknown").lower()


def detect_router_hardware():
    """只读路由器体检。返回证据与保守结论，绝不执行刷机。"""
    gateway = get_gateway()
    mac = get_gateway_mac()
    brand, _ = get_router_brand()
    admin_url = get_router_admin_url()
    upnp = discover_router_upnp()
    page = inspect_router_admin(admin_url)
    manufacturer = upnp.get("manufacturer", "")
    model = upnp.get("modelName", "") or upnp.get("modelNumber", "")
    if not brand and manufacturer:
        brand = manufacturer
    openwrt = bool(page.get("openwrt") or "openwrt" in " ".join(upnp.values()).lower())
    return {
        "fingerprint": router_fingerprint(gateway, mac),
        "gateway": gateway or "",
        "mac": mac or "",
        "brand": brand or "",
        "model": model,
        "revision": "",
        "admin_url": admin_url or "",
        "page_title": page.get("title", ""),
        "server": page.get("server", ""),
        "openwrt": openwrt,
        "wisp_status": ("OpenWrt 已识别：系统可配置无线客户端 + AP；仍需核验无线芯片/驱动和频段。"
                        if openwrt else "尚不能仅凭网关/MAC确认 WISP；需结合精确型号、硬件版本和厂商说明。"),
        "flash_allowed": False,
        "flash_status": "未授权刷机：缺少精确型号/硬件版本与官方镜像匹配，程序不会自动写入固件。",
        "evidence": upnp,
    }


def evaluate_flash_readiness(model, revision, official_match=False, checksum_verified=False,
                             backup_ready=False, recovery_ready=False):
    """生成刷机前置检查结论。所有条件满足也只表示可进入人工确认，不会自动刷。"""
    checks = {
        "已确认精确型号": bool((model or "").strip()),
        "已确认硬件版本": bool((revision or "").strip()),
        "OpenWrt 官方适配完全匹配": bool(official_match),
        "镜像 SHA256 校验通过": bool(checksum_verified),
        "原配置已备份": bool(backup_ready),
        "已确认可用恢复方式": bool(recovery_ready),
    }
    missing = [name for name, ok in checks.items() if not ok]
    return {
        "ready_for_confirmation": not missing,
        "automatic_flash_allowed": False,
        "checks": checks,
        "missing": missing,
        "message": ("检查通过，可进入最终人工确认；仍不能保证零影响。"
                    if not missing else "暂不可刷机，缺少：" + "、".join(missing)),
    }


def hotspot_on():
    """检测 Windows 移动热点是否已开启 (热点默认网段 192.168.137.x)"""
    if IS_MACOS:
        # macOS 没有稳定的无权限命令读取 Internet Sharing 状态，由界面提示用户确认。
        return None
    out = _run_decode(["powershell", "-NoProfile", "-Command",
                       "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                       "Where-Object { $_.IPAddress -like '192.168.137.*' } | "
                       "Select-Object -First 1 -ExpandProperty IPAddress"], timeout=15)
    return "192.168.137" in out


def open_wifi_settings():
    """打开当前平台的 Wi-Fi 设置页。"""
    try:
        if IS_MACOS:
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.wifi-settings-extension"])
        else:
            os.startfile("ms-settings:network-wifi")
        return True
    except Exception:
        return False


def open_hotspot_settings():
    """打开 Windows 移动热点设置页"""
    try:
        if IS_MACOS:
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.Sharing-Settings.extension"])
        else:
            os.startfile("ms-settings:network-mobilehotspot")
        return True
    except Exception:
        return False


def get_router_brand():
    """返回 (品牌, 管理地址); 识别不到返回 (None, 网关)"""
    gw = get_gateway()
    mac = get_gateway_mac()
    brand = None
    if mac:
        oui = mac[:8].upper()
        brand = OUI_BRANDS.get(oui)
    return brand, gw


# 各品牌"无线中继"设置路径指引
BRAND_GUIDE = {
    "华为": "华为路由器：\n  打开管理页 → 点「更多功能」→「网络设置」→「无线中继」\n  → 开启无线中继 → 扫描 WiFi → 选择校园网 (LIDA-UNIVERSITY)\n  → 输入校园网账号密码 → 保存\n  (也可用「智慧生活 App」远程设置)",
    "小米": "小米路由器：\n  打开管理页 →「常用设置」→「上网设置」→ 工作模式选「无线中继」\n  → 扫描 WiFi → 选择校园网 (LIDA-UNIVERSITY) → 输入密码 → 保存\n  (也可用「米家 App」远程设置)",
    "TP-LINK": "TP-LINK 路由器：\n  打开管理页 →「应用管理」→「无线桥接」→ 开始设置\n  → 扫描 → 选择校园网 (LIDA-UNIVERSITY) → 输入校园网账号密码 → 保存",
    "水星": "水星路由器：\n  打开管理页 →「无线设置」→「无线桥接」→ 扫描 → 选择校园网\n  → 输入账号密码 → 保存",
    "腾达": "腾达路由器：\n  打开管理页 →「无线设置」→「无线中继」→ 扫描 → 选择校园网 → 保存",
    "迅捷(FAST)": "迅捷 FAST 路由器：\n  打开管理页 → 点顶部「高级设置」→「无线设置」→「无线中继 / WISP」\n  → 开启无线中继 → 扫描 WiFi → 选择校园网 (LIDA-UNIVERSITY)\n  → 输入校园网账号密码 → 保存\n  (FAC1200R 等型号的中继在「高级设置」里, 不在 WAN口设置)",
    "华硕": "华硕路由器：\n  打开管理页 →「无线网络」→「无线中继」/ 或「外部网络」WISP 模式\n  → 扫描 → 选择校园网 → 输入账号密码 → 保存",
    "网件": "网件路由器：\n  打开管理页 →「高级」→「无线设置」→「中继」/「桥接」→ 扫描 → 选择校园网 → 保存",
    "中兴": "中兴路由器：\n  打开管理页 →「网络」→「无线中继」→ 扫描 → 选择校园网 → 保存",
    "360": "360 路由器：\n  打开管理页 →「路由设置」→「无线中继」→ 扫描 → 选择校园网 → 保存",
    "D-Link": "D-Link 路由器：\n  打开管理页 →「设置」→「无线设置」→「中继模式」→ 扫描 → 选择校园网 → 保存",
}
GENERIC_GUIDE = ("通用步骤（大部分路由器适用）：\n"
                 "  1. 打开管理页（浏览器输入上面的地址）\n"
                 "  2. 登录（账号密码在路由器底部标签，常见 admin/admin）\n"
                 "  3. 找到「无线中继 / WISP / 桥接 / 无线扩展」功能\n"
                 "  4. 扫描 WiFi → 选择校园网 (LIDA-UNIVERSITY)\n"
                 "  5. 输入校园网账号密码 → 保存\n"
                 "  6. 等路由器重启，完成中继")


def router_guide():
    """返回 (品牌, 管理地址, 操作指引文字)"""
    brand, gw = get_router_brand()
    guide = BRAND_GUIDE.get(brand, GENERIC_GUIDE)
    return brand, gw, guide


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


CAPTIVE_PROBES = (
    {"url": "http://connect.rom.miui.com/generate_204", "status": 204, "body": ""},
    {"url": "http://connectivitycheck.gstatic.com/generate_204", "status": 204, "body": ""},
    {"url": "http://www.msftconnecttest.com/connecttest.txt", "status": 200,
     "body": "Microsoft Connect Test"},
    {"url": "http://captive.apple.com/hotspot-detect.html", "status": 200,
     "body": "Success"},
    {"url": "http://www.baidu.com/", "status": 200, "body": "百度一下"},
)

PORTAL_MARKERS = ("dr.com", "drcom", "eportal", "portal", "webauth", "wlan_user_ip",
                  "wlanac", "user_account", "login_method", "bras", "注销页", "认证")


def _origin_url(url):
    """保留 scheme、主机和非默认端口，去除可能包含会话参数的路径与查询串。"""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = "[%s]" % host
        port = ":%s" % parsed.port if parsed.port else ""
        return "%s://%s%s/" % (parsed.scheme, host, port)
    except (TypeError, ValueError):
        return None


def _same_site(first, second):
    try:
        a = (urllib.parse.urlparse(first).hostname or "").lower()
        b = (urllib.parse.urlparse(second).hostname or "").lower()
        a = a[4:] if a.startswith("www.") else a
        b = b[4:] if b.startswith("www.") else b
        return a == b
    except Exception:
        return False


def _portal_like(text):
    lowered = (text or "").lower()
    return any(marker in lowered for marker in PORTAL_MARKERS)


def _extract_redirect_urls(source_url, headers, body):
    """识别 HTTP Location、HTML meta refresh 和常见 JavaScript 跳转。"""
    found = []
    for match in re.finditer(r"^location:\s*([^\r\n]+)", headers or "", re.I | re.M):
        found.append(urllib.parse.urljoin(source_url, match.group(1).strip()))
    text = body or ""
    patterns = (
        r"http-equiv\s*=\s*['\"]?refresh['\"]?[^>]+content\s*=\s*['\"][^'\"]*url\s*=\s*([^'\";> ]+)",
        r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            found.append(urllib.parse.urljoin(source_url, match.group(1).strip()))
    return list(dict.fromkeys(url for url in found if url.startswith(("http://", "https://"))))


def _run_captive_probe(probe, physical=True):
    """执行一个不跟随跳转的 GET，并返回状态、头和小段正文。"""
    url = probe["url"]
    if IS_MACOS:
        command = ["/usr/bin/curl", "--silent", "--show-error", "--max-time", "6",
                   "--max-redirs", "0", "--include", "--user-agent",
                   "Mozilla/5.0 AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
                   "--write-out", "\n__CNM_STATUS__%{http_code}", url]
        if physical:
            interface = get_physical_interface()
            if not interface:
                return {"probe": probe, "status": 0, "headers": "", "body": "",
                        "error": "未找到物理网卡"}
            command[7:7] = ["--noproxy", "*", "--interface", interface]
        try:
            result = subprocess.run(command, capture_output=True, timeout=8)
        except Exception as error:
            return {"probe": probe, "status": 0, "headers": "", "body": "", "error": str(error)}
        text = result.stdout.decode("utf-8", errors="replace")
        status_match = re.search(r"__CNM_STATUS__(\d{3})\s*$", text)
        status = int(status_match.group(1)) if status_match else 0
        text = text[:status_match.start()] if status_match else text
        head, _, body = text.partition("\r\n\r\n")
        if not body:
            head, _, body = text.partition("\n\n")
        return {"probe": probe, "status": status, "headers": head, "body": body[:65536]}

    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(request, timeout=6) as response:
            return {"probe": probe, "status": response.status,
                    "headers": str(response.headers),
                    "body": response.read(65536).decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as error:
        return {"probe": probe, "status": error.code, "headers": str(error.headers),
                "body": error.read(65536).decode("utf-8", errors="replace")}
    except Exception as error:
        return {"probe": probe, "status": 0, "headers": "", "body": "", "error": str(error)}


def discover_auth_servers(known_urls=None):
    """从多组 204/正文探针和已知地址发现多个认证服务候选。"""
    candidates = {}
    online = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CAPTIVE_PROBES)) as pool:
        results = list(pool.map(lambda probe: _run_captive_probe(probe, physical=True), CAPTIVE_PROBES))

    for result in results:
        probe = result["probe"]
        body = result.get("body", "")
        expected_body = probe.get("body", "")
        if result.get("status") == probe["status"] and (not expected_body or expected_body in body):
            online = True
        combined = "%s\n%s" % (result.get("headers", ""), body)
        redirects = _extract_redirect_urls(probe["url"], result.get("headers", ""), body)
        for redirected in redirects:
            if _same_site(probe["url"], redirected):
                continue
            origin = _origin_url(redirected)
            if not origin:
                continue
            private = False
            try:
                private = ipaddress.ip_address(socket.gethostbyname(urllib.parse.urlparse(origin).hostname)).is_private
            except Exception:
                pass
            if private or _portal_like(redirected + " " + combined):
                candidates[origin] = {
                    "url": origin, "confidence": 100 if private or _portal_like(combined) else 75,
                    "source": "重定向", "probe": probe["url"],
                }

    for known in list(dict.fromkeys(url for url in (known_urls or []) if url)):
        origin = _origin_url(known)
        if not origin or origin in candidates:
            continue
        try:
            status, raw = http_get(origin, timeout=5, physical=True)
            text = decode_gbk(raw[:131072])
            if status == 200 and (_portal_like(origin + " " + text) or origin == DEFAULT_AUTH_URL):
                candidates[origin] = {"url": origin, "confidence": 90,
                                      "source": "已知地址验证", "probe": origin}
        except Exception:
            continue

    ordered = sorted(candidates.values(), key=lambda item: (-item["confidence"], item["url"]))
    return {"candidates": ordered, "online": online, "probes": results}


def detect_auth_server(known_urls=None):
    """兼容旧接口：返回多来源发现结果中可信度最高的认证服务器。"""
    result = discover_auth_servers(known_urls)
    return result["candidates"][0]["url"] if result["candidates"] else None


def get_connection_mode():
    """返回 (模式, ssid): wifi=无线连接, ethernet=有线连接, none=无网络"""
    ssid = get_ssid()
    if ssid:
        return "wifi", ssid
    gw = get_gateway()
    if gw and not gw.startswith("127."):
        return "ethernet", None
    return "none", None


def profile_has_credentials(profile):
    """档案是否已填写账号密码 (具备登录能力)。"""
    return bool(profile and profile.get("username") and profile.get("password"))


def is_campus_locked(profile, ssid, gw, respect_user_choice=False):
    """判断当前连接是否被校园网档案"锁定"。
    命中条件: 匹配到的档案已填账号密码且指向校园网认证地址, 且
      - SSID 精确绑定 (直连 LIDA / 中继路由器 WiFi), 或
      - 网关精确绑定 (有线接指定路由器), 或
      - 无 SSID 但用户未明确选"任意网络"的有线/其他连接。
    用于认证服务器短暂探测不到时, 不误判"非校园网"而静止休眠。

    respect_user_choice=True 时(用户明确选了「任意网络使用」的默认档案),
    绝不锁定 —— 尊重用户不绑定选择, 即使无 SSID 也不按校园网处理, 避免
    在手机热点等非校园网下被硬拉去登录校园网。"""
    profile_bound = bool(profile and profile.get("username") and profile.get("password")
                         and (profile.get("auth_url") or "").strip())
    if respect_user_choice:
        return False
    if not profile_bound:
        return False
    ssid_bound = bool(profile.get("ssid") and profile.get("ssid") == ssid)
    gw_bound = bool(profile.get("gateway") and profile.get("gateway") == gw)
    return bool(ssid_bound or gw_bound or not ssid)


def match_profile(cfg, ssid, gateway=None, respect_user_choice=False):
    """匹配档案: SSID 精确匹配 > 网关精确匹配(有线) > 默认档案 > 首个有账号档案。

    respect_user_choice=True 时(用户明确选了「任意网络使用」的默认档案), 即使该默认档案
    没有账号, 也返回它本身, 绝不回退到其他有账号的校园网档案 —— 尊重用户"不绑定"的选择,
    避免选了任意网络却被硬用立达账号登录并显示校园网环境。
    """
    profiles = cfg.get("profiles", [])
    if ssid:
        for p in profiles:
            if p.get("ssid") and p["ssid"] == ssid:
                return p
    if gateway:
        for p in profiles:
            if p.get("gateway") and p["gateway"] == gateway:
                return p
    # 默认档案: ssid / gateway 均为空
    for p in profiles:
        if not p.get("ssid") and not p.get("gateway"):
            # 尊重用户选择: 选了「任意网络」就用它本身, 不回退
            if respect_user_choice:
                return p
            # 否则: 若该默认档案没有账号, 且存在有账号的校园网档案, 则优先用后者
            if not profile_has_credentials(p):
                with_account = next((x for x in profiles
                                     if profile_has_credentials(x)
                                     and x.get("auth_url") == p.get("auth_url")), None)
                if with_account:
                    return with_account
            return p
    return profiles[0] if profiles else None


def auth_reachable(auth_url):
    """认证服务器是否可达 (判定是否校园网环境)"""
    try:
        status, _ = http_get(auth_url, timeout=5, physical=True)
        return status == 200
    except Exception:
        return False


# ---------- 网络检测 ----------
def now_str():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg):
    line = "[%s] %s" % (now_str(), msg)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        _trim_log()
    except Exception:
        pass
    return line


def send_system_notification(text, title="校园网连接管家"):
    """发送系统通知；失败时由界面回退到运行日志。"""
    if not IS_MACOS:
        return False
    script = ('on run argv\n'
              'display notification (item 2 of argv) with title (item 1 of argv)\n'
              'end run')
    try:
        result = subprocess.run(["/usr/bin/osascript", "-e", script, "--", title, text],
                                capture_output=True, timeout=8)
        return result.returncode == 0
    except Exception:
        return False


def _trim_log(max_bytes=2 * 1024 * 1024, keep_bytes=300 * 1024):
    """日志超过 2MB 时截断到 300KB, 防止无限增长"""
    try:
        if os.path.getsize(LOG_PATH) > max_bytes:
            with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            with open(LOG_PATH, "w", encoding="utf-8") as f:
                f.write("...日志已自动清理...\n" + content[-keep_bytes:])
    except Exception:
        pass


# 开机自启: Windows 使用注册表 Run 键；macOS 使用当前用户的 LaunchAgent。
_AUTOSTART_NAME = "CampusNetManager"
_MAC_LAUNCH_LABEL = "com.campusnettools.campusnetmanager"
AUTOSTART_CMD = '"%s" "%s"' % (
    sys.executable if not getattr(sys, "frozen", False) else sys.executable,
    os.path.abspath(__file__) if not getattr(sys, "frozen", False) else os.path.join(BASE_DIR, "校园网连接管家.exe"),
)


def autostart_enabled():
    if IS_MACOS:
        return os.path.exists(os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", _MAC_LAUNCH_LABEL + ".plist"))
    out = _run_decode(["reg", "query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                       "/v", _AUTOSTART_NAME])
    return "CampusNetManager" in out


def set_autostart(enabled):
    """开启/关闭开机自启；macOS 只登记下次登录启动，不立即拉起第二个实例。"""
    if IS_MACOS:
        path = os.path.join(os.path.expanduser("~"), "Library", "LaunchAgents", _MAC_LAUNCH_LABEL + ".plist")
        try:
            if enabled:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                args = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, os.path.join(os.path.dirname(__file__), "app_gui.py")]
                with open(path, "wb") as f:
                    plistlib.dump({"Label": _MAC_LAUNCH_LABEL, "ProgramArguments": args,
                                   "RunAtLoad": True, "ProcessType": "Interactive"}, f)
                return True
            if os.path.exists(path):
                os.remove(path)
            return True
        except Exception:
            return False
    try:
        if enabled:
            # exe 版: 指向 exe 自己; 源码版: 指向 pythonw + app_gui.py
            if getattr(sys, "frozen", False):
                cmd = '"%s"' % os.path.join(BASE_DIR, "校园网连接管家.exe")
            else:
                pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
                cmd = '"%s" "%s"' % (pyw, os.path.join(BASE_DIR, "app_gui.py"))
            r = subprocess.run(["reg", "add", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                                "/v", _AUTOSTART_NAME, "/t", "REG_SZ", "/d", cmd, "/f"],
                               capture_output=True, timeout=10,
                               creationflags=_NO_WINDOW)
            return r.returncode == 0
        else:
            r = subprocess.run(["reg", "delete", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                                "/v", _AUTOSTART_NAME, "/f"],
                               capture_output=True, timeout=10,
                               creationflags=_NO_WINDOW)
            return r.returncode == 0
    except Exception:
        return False


def http_get(url, timeout=6, physical=False):
    """获取 URL；macOS 的校园认证请求可强制走物理网卡，避免被 VPN 路由接管。"""
    if IS_MACOS and physical:
        interface = get_physical_interface()
        if interface:
            try:
                result = subprocess.run(
                    ["/usr/bin/curl", "--silent", "--show-error", "--max-time", str(timeout),
                     "--noproxy", "*",
                     "--interface", interface, "--output", "-", "--write-out", "\n%{http_code}",
                     "--user-agent", "Mozilla/5.0 AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
                     url],
                    capture_output=True, timeout=timeout + 2)
                if result.returncode == 0 and b"\n" in result.stdout:
                    body, raw_status = result.stdout.rsplit(b"\n", 1)
                    return int(raw_status), body
                raise OSError(result.stderr.decode("utf-8", errors="replace") or "物理网卡请求失败")
            except Exception as exc:
                raise urllib.error.URLError(exc)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Referer": url,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def decode_gbk(body):
    try:
        return body.decode("gbk", errors="replace")
    except Exception:
        return body.decode("utf-8", errors="replace")


def check_auth(auth_url=DEFAULT_AUTH_URL):
    """True=已登录(注销页), False=未登录/不可达"""
    try:
        status, body = http_get(auth_url, timeout=6, physical=True)
        if status != 200:
            return False
        text = decode_gbk(body)
        m = re.search(r"<title>([^<]+)</title>", text, re.I)
        return bool(m and m.group(1).strip() == "注销页")
    except Exception:
        return False


def _probe_matches_expected(result):
    probe = result["probe"]
    expected_body = probe.get("body", "")
    return (result.get("status") == probe["status"]
            and (not expected_body or expected_body in result.get("body", "")))


def check_internet(physical=False):
    """严格联网检测：只有 204 或预期正文才算在线，认证页 200/302 不算外网。"""
    probes = CAPTIVE_PROBES[:4]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(probes)) as pool:
        results = list(pool.map(lambda probe: _run_captive_probe(probe, physical=physical), probes))
    return any(_probe_matches_expected(result) for result in results)


def check_network_paths():
    """分别检查当前系统/VPN路径和校园网物理路径，避免把 VPN 异常误报为校园网假在线。"""
    vpn = vpn_active()
    if vpn and IS_MACOS:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            current_future = pool.submit(check_internet, False)
            physical_future = pool.submit(check_internet, True)
            current = current_future.result()
            physical = physical_future.result()
    else:
        current = check_internet(False)
        physical = current
    return {"vpn": vpn, "current": current, "physical": physical}


# ---------- 登录 ----------
def try_login(profile):
    suffix = SUFFIX.get(profile.get("login_type", "cmcc"), "@cmcc")
    auth_url = profile.get("auth_url", DEFAULT_AUTH_URL)
    host = auth_url.split("/")[2] if "//" in auth_url else auth_url
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
    url = "http://%s/drcom/login?%s" % (host, urllib.parse.urlencode(params))
    try:
        status, body = http_get(url, timeout=15, physical=True)
        return status == 200 and b"dr1003" in body
    except Exception:
        return False


def ensure_login(profile, on_log=None):
    for i in range(10):
        if try_login(profile):
            return True
        if on_log:
            on_log("登录重试 %d/10 失败" % (i + 1))
        time.sleep(2)
    return False


# ---------- 守护线程 ----------
class KeepAliveDaemon(threading.Thread):
    def __init__(self, cfg, on_log=None, on_status=None, on_env=None, on_alert=None):
        super().__init__(daemon=True)
        self.cfg = cfg
        self.on_log = on_log
        self.on_status = on_status      # callable(online, authed, last_check)
        self.on_env = on_env            # callable(mode, ssid, gw, profile_name, in_campus)
        self.on_alert = on_alert        # callable(text) 掉线/重登/失败通知
        self._stop = threading.Event()
        self.last_check = ""

    def stop(self):
        self._stop.set()

    def _log(self, msg):
        line = log(msg)
        if self.on_log:
            self.on_log(line)

    def _alert(self, text, category="failure"):
        if self.on_alert:
            try:
                self.on_alert(text, category)
            except Exception:
                pass

    def _check_and_publish_status(self, auth_url):
        """完成一次联网检查，并把结果同步给顶部状态栏。"""
        authed = check_auth(auth_url)
        paths = check_network_paths()
        self.last_check = now_str()
        if self.on_status:
            self.on_status(paths, authed, self.last_check)
        return authed, paths

    def _refresh_after_login(self, mode, ssid, gw, profile, auth_url):
        """自动登录成功后立即复检，避免界面一直显示登录前的掉线状态。"""
        if self.on_env:
            self.on_env(mode, ssid, gw, profile["name"], True)
        authed, paths = self._check_and_publish_status(auth_url)
        if not authed and not self._stop.wait(2):
            authed, paths = self._check_and_publish_status(auth_url)
        return authed, paths

    def _wait_or_break(self, seconds, ref_fp=None):
        """分段等待: 每 60s 醒来检查一次连接指纹(SSID/网关)是否变化,
        网络切换/电脑唤醒后网络恢复时提前结束等待立即检测。
        返回 True = 应退出守护。"""
        waited = 0
        while waited < seconds:
            chunk = min(60, seconds - waited)
            if self._stop.wait(chunk):
                return True
            waited += chunk
            try:
                mode, ssid = get_connection_mode()
                gw = get_gateway()
                if ref_fp and (mode, ssid, gw) != ref_fp:
                    return False  # 网络变化 → 提前进入下一轮完整检测
            except Exception:
                pass
        return False

    def run(self):
        self._log("=" * 56)
        self._log("校园网连接管家守护启动")
        while not self._stop.is_set():
            try:
                mode, ssid = get_connection_mode()
                gw = get_gateway()
                fp = (mode, ssid, gw)
                # 尊重用户"任意网络"选择: 若当前激活档案是空账号的默认档案(SSID/网关留空),
                # 说明用户明确不想绑定特定网络 —— 不自动回退到其他校园网档案, 也不强制锁定为校园网。
                active_name = self.cfg.get("active_profile")
                active_prof = next((p for p in self.cfg.get("profiles", []) if p.get("name") == active_name), None)
                user_any_network = bool(
                    active_prof and not active_prof.get("ssid") and not active_prof.get("gateway")
                    and not profile_has_credentials(active_prof))
                profile = match_profile(self.cfg, ssid, gw,
                                        respect_user_choice=user_any_network)
                auth_url = profile.get("auth_url", DEFAULT_AUTH_URL) if profile else DEFAULT_AUTH_URL

                # 环境判定: 认证服务器可达 = 校园网环境; 不可达 = 非校园网。
                in_campus = auth_reachable(auth_url)
                # --- 增强: 中继/直连校园网场景, 认证服务器可能暂时探测不到(如路由器链路抖动、
                # 交换机短暂隔离、有线接路由器时物理网卡探测超时), 但只要当前连接被"校园网档案
                # 锁定"(用户明确在该网络配过账号), 仍视为校园网环境进入检测并尝试重登。
                # 若用户选了「任意网络使用」, 则不锁定、不自动重登, 保持中立。
                if not in_campus and is_campus_locked(profile, ssid, gw,
                                                      respect_user_choice=user_any_network):
                    self._log("认证服务器暂时不可达, 但处于校园网档案 [%s] 环境 (%s), 按校园网处理 (尝试检测/重登)"
                              % (profile["name"], ssid or ("有线/网关 " + (gw or "?"))))
                    in_campus = True
                if self.on_env:
                    self.on_env(mode, ssid, gw, profile["name"] if profile else None, in_campus)

                if not in_campus:
                    self._log("非校园网环境%s, 守护休眠 (不进行登录)" % (" (" + ssid + ")" if ssid else " (有线/其他)"))
                    if self._wait_or_break(30, fp):
                        break
                    continue

                if profile is None:
                    self._log("校园网环境但未配置档案%s, 请在 App 中添加" % (" (" + ssid + ")" if ssid else ""))
                    if self._wait_or_break(30, fp):
                        break
                    continue

                interval = max(10, int(profile.get("interval", 60)))
                # 防踢: 会话刷新计数器 (每 interval 秒循环一次)
                if not hasattr(self, "_refresh_count"):
                    self._refresh_count = 0
                    self._kickguard = bool(self.cfg.get("kick_guard", True))
                authed, paths = self._check_and_publish_status(auth_url)
                campus_internet = paths["physical"] if paths["vpn"] and IS_MACOS else paths["current"]

                if authed and campus_internet:
                    if paths["vpn"] and not paths["current"]:
                        self._log("校园网物理出口正常，但 VPN/系统路径暂时不通；不重复登录校园网")
                        record_network_history(self.cfg, "vpn_issue", "校园网正常，但 VPN 暂时无法上网",
                                               profile=profile["name"])
                    else:
                        self._log("在线正常 (%s / 认证页OK+外网OK)" % profile["name"])
                        record_network_history(self.cfg, "online", "网络正常", profile=profile["name"])
                        # --- 防踢保活: 周期性刷新登录, 让本会话保持"最新" ---
                        # Dr.COM 名额按会话新鲜度淘汰: 第N+1台登录会挤掉最旧会话。
                        # 定期 try_login (同来源IP=刷新续期, 已实测会话IP不变) 使被保护
                        # 设备始终为最新, 新设备登录时被挤掉的是别人而不是本机/路由器。
                        self._refresh_count += 1
                        if self._kickguard and self._refresh_count >= 3:
                            self._refresh_count = 0
                            self._log("防踢保活: 刷新登录会话, 保持本设备名额最新")
                            if try_login(profile):
                                self._log("会话刷新成功")
                            else:
                                self._log("会话刷新失败(不阻塞, 下轮再试)")
                elif authed and not campus_internet:
                    self._log("警告: 校园网认证在线但物理出口不通, 尝试重登...")
                    record_network_history(self.cfg, "disconnect", "校园网出口异常", profile=profile["name"])
                    self._alert("校园网出口异常，正在尝试恢复", "disconnect")
                    if ensure_login(profile, on_log=self._log):
                        self._log("重登完成")
                        self._refresh_after_login(mode, ssid, gw, profile, auth_url)
                        record_network_history(self.cfg, "recovery", "网络已自动恢复", profile=profile["name"])
                        self._alert("网络已自动恢复", "recovery")
                    else:
                        reachable = auth_reachable(auth_url)
                        if not reachable:
                            self._log("重登失败：认证服务器不可达。中继/路由器模式下校园网链路可能已断开，"
                                      "请重启路由器重新拨号恢复")
                            record_network_history(self.cfg, "failure", "校园网链路断开", profile=profile["name"])
                            self._alert("校园网链路已断开：请重启路由器恢复（电脑无法直接重连）", "failure")
                        else:
                            self._log("重登失败! 提示: 账号可能已被其他设备占用名额(校园网通常限2台), 或被服务器临时限制")
                            record_network_history(self.cfg, "failure", "自动恢复失败", profile=profile["name"])
                            self._alert("自动恢复失败：账号名额可能被其他设备占用，可登录自助系统处理占用设备", "failure")
                elif not authed:
                    self._log("检测到掉线 (%s), 自动登录中..." % profile["name"])
                    record_network_history(self.cfg, "disconnect", "检测到校园网掉线", profile=profile["name"])
                    self._alert("检测到校园网掉线，正在自动登录", "disconnect")
                    if ensure_login(profile, on_log=self._log):
                        self._log("自动登录成功")
                        self._refresh_after_login(mode, ssid, gw, profile, auth_url)
                        record_network_history(self.cfg, "recovery", "已自动恢复连接", profile=profile["name"])
                        self._alert("已自动恢复连接", "recovery")
                    else:
                        # 区分"链路断开"(认证服务器不可达) 与 "账号问题"(可达但登录失败)
                        reachable = auth_reachable(auth_url)
                        if not reachable:
                            self._log("自动登录失败：认证服务器不可达。当前处于中继/路由器模式时，"
                                      "校园网链路可能已断开，需要重启路由器重新拨号才能恢复")
                            record_network_history(self.cfg, "failure", "校园网链路断开", profile=profile["name"])
                            self._alert("校园网链路已断开：请重启路由器恢复（电脑无法直接重连）", "failure")
                        else:
                            self._log("自动登录失败 (稍后重试)")
                            record_network_history(self.cfg, "failure", "自动登录失败", profile=profile["name"])
                            self._alert("自动登录失败：请检查账号密码；若提示名额已满，需在自助系统下线其他设备", "failure")
                else:
                    self._log("异常状态")

                if self._wait_or_break(interval, fp):
                    break
            except Exception as e:
                # 兜底: 任何异常都不让守护线程退出, 记录后短暂恢复
                self._log("守护异常: %s (自动恢复)" % e)
                if self._stop.wait(5):
                    break
        self._log("守护已停止")


# ---------- 合盖/休眠保持运行 ----------
# macOS 笔记本合盖或系统空闲会自动进入睡眠, 守护线程随之暂停, 导致掉线后无法自动重登。
# caffeinate 是 macOS 自带命令, 可通过电源断言阻止系统睡眠/空闲睡眠, 让程序在合盖/休眠
# 状态下继续联网保活。仅 macOS 有效, Windows 用 nvidia/电源计划由系统管理, 此处返回 False。
_keep_awake_proc = None
_keep_awake_lock = threading.Lock()


def keep_awake_start():
    """启动 caffeinate 电源断言, 阻止系统睡眠/空闲睡眠/显示器睡眠。返回 True 表示已启动。
    仅 macOS 生效; 精灵窗口/合盖场景下守护线程可继续运行。"""
    global _keep_awake_proc
    if not IS_MACOS:
        return False
    with _keep_awake_lock:
        if _keep_awake_proc and _keep_awake_proc.poll() is None:
            return True  # 已在运行
        try:
            # -d 阻止显示器睡眠, -i 阻止空闲睡眠, -s 阻止系统睡眠(合盖), -m 阻止磁盘睡眠
            proc = subprocess.Popen(
                ["/usr/bin/caffeinate", "-d", "-i", "-s", "-m",
                 "-w", str(os.getpid())],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            _keep_awake_proc = proc
            return True
        except Exception:
            return False


def keep_awake_stop():
    """停止 caffeinate 电源断言 (可选调用; 进程退出时 caffeinate 的 -w 标志会自动结束)。"""
    global _keep_awake_proc
    with _keep_awake_lock:
        if _keep_awake_proc and _keep_awake_proc.poll() is None:
            try:
                _keep_awake_proc.terminate()
            except Exception:
                pass
        _keep_awake_proc = None


def keep_awake_enabled():
    """查询保持唤醒是否正在生效。"""
    global _keep_awake_proc
    if not IS_MACOS:
        return False
    return bool(_keep_awake_proc and _keep_awake_proc.poll() is None)


# ---------- 版本与诊断 ----------
APP_VERSION = "2.6.3"
APP_NAME = "校园网连接管家"


def collect_diagnostics():
    """收集诊断信息(密码脱敏), 供一键导出求助"""
    lines = []
    lines.append("=" * 46)
    lines.append("%s 诊断报告 v%s" % (APP_NAME, APP_VERSION))
    lines.append("时间: %s" % now_str())
    lines.append("=" * 46)
    try:
        mode, ssid = get_connection_mode()
        lines.append("连接方式: %s%s" % ("WiFi" if mode == "wifi" else "有线" if mode == "ethernet" else "无连接",
                                        " (%s)" % ssid if ssid else ""))
        lines.append("网关: %s" % (get_gateway() or "-"))
        lines.append("网关MAC: %s" % (get_gateway_mac() or "-"))
        cfg = load_config()
        lines.append("档案数: %d" % len(cfg.get("profiles", [])))
        for p in cfg.get("profiles", []):
            lines.append("  档案[%s] ssid=%s 账号=%s 运营商=%s 间隔=%ss 认证=%s"
                         % (p.get("name", "?"),
                            p.get("ssid") or "任意",
                            p.get("username", ""),
                            p.get("login_type", ""),
                            p.get("interval", "?"),
                            p.get("auth_url", "")))
        lines.append("开机自启: %s" % ("开启" if autostart_enabled() else "关闭"))
        lines.append("VPN隧道: %s" % ("已检测到" if vpn_active() else "未检测到"))
        lines.append("热点共享: %s" % ("开启" if hotspot_on() else "关闭"))
    except Exception as e:
        lines.append("环境检测异常: %s" % e)
    lines.append("-" * 46)
    lines.append("最近日志:")
    try:
        if os.path.exists(LOG_PATH):
            with open(LOG_PATH, "r", encoding="utf-8", errors="replace") as f:
                tail = f.readlines()[-40:]
            lines.extend(l.rstrip("\n") for l in tail)
    except Exception:
        pass
    # 会话归属分析 (防踢排查): 用有账号档案探测一次, 看谁占着校园网名额
    lines.append("-" * 46)
    lines.append("会话归属:")
    try:
        import diagnostics
        for p in cfg.get("profiles", []):
            if p.get("username"):
                ana = diagnostics.analyze(p)
                if ana.get("ok"):
                    lines.append("  账号 %s -> 会话IP %s / 会话MAC %s (本机:%s) / 来源MAC %s (本机:%s) / %s"
                                 % (ana.get("uid"), ana.get("session_ip"), ana.get("session_mac"),
                                    "是" if ana.get("session_is_local") else "否",
                                    ana.get("source_mac"),
                                    "是" if ana.get("source_is_local") else "否",
                                    ana.get("note") or ""))
                else:
                    lines.append("  账号 %s -> 探测失败: %s" % (p.get("username"), ana.get("detail")))
                break
    except Exception as exc:
        lines.append("  会话分析异常: %s" % exc)
    return "\n".join(lines)


# ---------- 锁 ----------
def acquire_lock():
    try:
        if os.path.exists(LOCK_PATH):
            with open(LOCK_PATH) as f:
                old_pid = f.read().strip()
            if old_pid and old_pid != str(os.getpid()):
                if IS_MACOS:
                    try:
                        os.kill(int(old_pid), 0)
                        return False
                    except (OSError, ValueError):
                        pass
                else:
                    out = _run_decode(["tasklist", "/FI", "PID eq %s" % old_pid])
                    if old_pid in out:
                        return False
        with open(LOCK_PATH, "w") as f:
            f.write(str(os.getpid()))
        return True
    except Exception:
        return True


def release_lock():
    try:
        if os.path.exists(LOCK_PATH):
            os.remove(LOCK_PATH)
    except Exception:
        pass
