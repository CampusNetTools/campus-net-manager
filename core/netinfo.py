# -*- coding: utf-8 -*-
"""系统网络信息探测 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401

__all__ = ['_run_decode', 'get_ssid', 'get_gateway', 'get_physical_route', 'get_physical_interface', 'vpn_active', 'automatic_speed_test_plan', 'get_connection_mode']

def _run_decode(cmd, timeout=10):
    """运行命令并智能解码输出。
    netsh/reg/tasklist 等输出编码随代码页变化 (GBK 或 UTF-8),
    先按 UTF-8 严格解码, 失败再回退 GBK, 避免中文 SSID 乱码。"""
    try:
        kwargs = {"capture_output": True, "timeout": timeout}
        if common.IS_WINDOWS:
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
    if common.IS_MACOS:
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
    if common.IS_MACOS:
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
    if not common.IS_MACOS:
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
    if common.IS_MACOS:
        out = _run_decode(["netstat", "-rn", "-f", "inet"])
        return any(len(line.split()) >= 4 and line.split()[0] == "default"
                   and line.split()[3].startswith("utun") for line in out.splitlines())
    out = _run_decode(["route", "print", "-4"])
    return any(mark in out.lower() for mark in ("wireguard", "wintun", "tap-windows", "vpn"))


def automatic_speed_test_plan():
    """按当前 VPN 状态决定测速路径；界面无需让用户理解或选择底层网卡。"""
    active = vpn_active()
    compare = bool(active and common.IS_MACOS)
    return {
        "vpn_active": active,
        "compare": compare,
        "paths": ("current", "physical") if compare else ("current",),
    }


def get_connection_mode():
    """返回 (模式, ssid): wifi=无线连接, ethernet=有线连接, none=无网络"""
    ssid = get_ssid()
    if ssid:
        return "wifi", ssid
    gw = get_gateway()
    if gw and not gw.startswith("127."):
        return "ethernet", None
    return "none", None
