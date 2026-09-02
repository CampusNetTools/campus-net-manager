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
import socket
import subprocess
import sys
import threading
import time
import datetime
import urllib.request
import urllib.parse

# 打包成 exe 后, 配置/日志跟随 exe 所在目录 (否则会写到临时解压目录导致丢失)
if getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "keepalive.log")
LOCK_PATH = os.path.join(BASE_DIR, "keepalive.lock")

DEFAULT_AUTH_URL = "http://192.168.16.3/"

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


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {"profiles": [default_profile()], "active_profile": "校园网"}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    # 兼容旧版单档案结构
    if "profiles" not in cfg:
        p = default_profile("校园网")
        p.update({k: cfg.get(k) for k in ("username", "password", "login_type", "interval") if cfg.get(k) is not None})
        cfg = {"profiles": [p], "active_profile": p["name"]}
        save_config(cfg)
    return cfg


def save_config(cfg):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


# ---------- 环境识别 ----------
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


def _run_decode(cmd, timeout=10):
    """运行命令并智能解码输出。
    netsh/reg/tasklist 等输出编码随代码页变化 (GBK 或 UTF-8),
    先按 UTF-8 严格解码, 失败再回退 GBK, 避免中文 SSID 乱码。"""
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout,
                           creationflags=_NO_WINDOW)
        out = r.stdout or b""
        try:
            return out.decode("utf-8")
        except UnicodeDecodeError:
            return out.decode("gbk", errors="replace")
    except Exception:
        return ""


def get_ssid():
    """返回当前连接的 WiFi SSID; 无线未连接/有线接入返回 None"""
    out = _run_decode(["netsh", "wlan", "show", "interfaces"])
    for line in out.splitlines():
        if "SSID" in line and "BSSID" not in line and ":" in line:
            val = line.split(":", 1)[-1].strip()
            return val or None
    return None


def get_gateway():
    """返回当前默认网关 IP (路由器管理地址通常就是它)"""
    out = _run_decode(["route", "print", "-4"])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 3 and parts[0] == "0.0.0.0" and parts[1] == "0.0.0.0":
            return parts[2]
    return None


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


def get_gateway_mac():
    """通过 arp 表查默认网关的 MAC 地址"""
    gw = get_gateway()
    if not gw:
        return None
    out = _run_decode(["arp", "-a"])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == gw:
            return parts[1].replace("-", ":")
    return None


def get_router_admin_url():
    """探测路由器管理页地址(中继/桥接后原 192.168.x.1 可能失效)。
    NAT 模式: 管理地址=默认网关;
    桥接/中继模式: 网关是校园网, 从 ARP 表逐个试 HTTP, 找到开管理页的路由器 IP。"""
    import urllib.request
    gw = get_gateway()
    candidates = []
    if gw:
        candidates.append(gw)
    out = _run_decode(["arp", "-a"])
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 1 and len(parts[0].split(".")) == 4:
            ip = parts[0]
            if ip != gw and not ip.startswith(("224.", "239.", "255.", "127.")):
                candidates.append(ip)
    seen, uniq = set(), []
    for ip in candidates:
        if ip not in seen:
            seen.add(ip)
            uniq.append(ip)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))  # 不走代理
    for ip in uniq:
        try:
            req = urllib.request.Request("http://%s/" % ip,
                                         headers={"User-Agent": "Mozilla/5.0"}, method="GET")
            resp = opener.open(req, timeout=2)
            body = resp.read(2000)
            if len(body) > 200 and b"<" in body:
                return "http://%s/" % ip
        except Exception:
            continue
    return "http://%s/" % gw if gw else None


def hotspot_on():
    """检测 Windows 移动热点是否已开启 (热点默认网段 192.168.137.x)"""
    out = _run_decode(["powershell", "-NoProfile", "-Command",
                       "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                       "Where-Object { $_.IPAddress -like '192.168.137.*' } | "
                       "Select-Object -First 1 -ExpandProperty IPAddress"], timeout=15)
    return "192.168.137" in out


def open_hotspot_settings():
    """打开 Windows 移动热点设置页"""
    try:
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


def detect_auth_server():
    """
    自动探测当前网络的认证服务器地址。
    原理: 未认证时访问 http 站点会被 portal 重定向, 从 Location 提取服务器 host。
    返回形如 http://192.168.16.3/ 的地址; 无法探测返回 None。
    """
    probes = ["http://www.baidu.com/", "http://www.qq.com/", "http://www.163.com/"]
    for url in probes:
        probe_host = url.split("/")[2]
        try:
            opener = urllib.request.build_opener(_NoRedirect)
            req = urllib.request.Request(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36"})
            try:
                opener.open(req, timeout=8)
                continue  # 200 = 已认证或非 portal 网络, 换下一个
            except urllib.error.HTTPError as e:
                loc = e.headers.get("Location", "")
            except Exception:
                continue
            if not loc:
                continue
            # 提取 scheme://host (去掉路径参数)
            if loc.startswith("http://") or loc.startswith("https://"):
                scheme, rest = loc.split("://", 1)
                host = rest.split("/", 1)[0]
                if host == probe_host:
                    continue  # 网站自身跳转 (如 http→https), 不是 portal
                return "%s://%s/" % (scheme, host)
            # 相对路径: 用探测地址的 host (网站自身相对跳转, 视为非 portal)
            continue
        except Exception:
            continue
    return None


def get_connection_mode():
    """返回 (模式, ssid): wifi=无线连接, ethernet=有线连接, none=无网络"""
    ssid = get_ssid()
    if ssid:
        return "wifi", ssid
    gw = get_gateway()
    if gw and not gw.startswith("127."):
        return "ethernet", None
    return "none", None


def match_profile(cfg, ssid, gateway=None):
    """匹配档案: SSID 精确匹配 > 网关精确匹配(有线) > 默认档案(ssid/gateway都空) > 第一个"""
    profiles = cfg.get("profiles", [])
    if ssid:
        for p in profiles:
            if p.get("ssid") and p["ssid"] == ssid:
                return p
    if gateway:
        for p in profiles:
            if p.get("gateway") and p["gateway"] == gateway:
                return p
    for p in profiles:
        if not p.get("ssid") and not p.get("gateway"):
            return p
    return profiles[0] if profiles else None


def auth_reachable(auth_url):
    """认证服务器是否可达 (判定是否校园网环境)"""
    try:
        status, _ = http_get(auth_url, timeout=5)
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


# 开机自启: 注册表 Run 键控制
_AUTOSTART_NAME = "CampusNetManager"
AUTOSTART_CMD = '"%s" "%s"' % (
    sys.executable if not getattr(sys, "frozen", False) else sys.executable,
    os.path.abspath(__file__) if not getattr(sys, "frozen", False) else os.path.join(BASE_DIR, "校园网连接管家.exe"),
)


def autostart_enabled():
    out = _run_decode(["reg", "query", r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
                       "/v", _AUTOSTART_NAME])
    return "CampusNetManager" in out


def set_autostart(enabled):
    """开启/关闭开机自启 (注册表 Run 键)"""
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


def http_get(url, timeout=6):
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
        status, body = http_get(auth_url, timeout=6)
        if status != 200:
            return False
        text = decode_gbk(body)
        m = re.search(r"<title>([^<]+)</title>", text, re.I)
        return bool(m and m.group(1).strip() == "注销页")
    except Exception:
        return False


def check_internet():
    for t in ("http://www.baidu.com/", "http://www.qq.com/"):
        try:
            socket.setdefaulttimeout(6)
            status, _ = http_get(t, timeout=6)
            if status in (200, 301, 302):
                return True
        except Exception:
            continue
    return False


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
        status, body = http_get(url, timeout=15)
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

    def _alert(self, text):
        if self.on_alert:
            try:
                self.on_alert(text)
            except Exception:
                pass

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
                profile = match_profile(self.cfg, ssid, gw)
                auth_url = profile.get("auth_url", DEFAULT_AUTH_URL) if profile else DEFAULT_AUTH_URL

                # 环境判定: 认证服务器可达?
                in_campus = auth_reachable(auth_url)
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
                authed = check_auth(auth_url)
                internet = check_internet()
                self.last_check = now_str()
                if self.on_status:
                    self.on_status(internet and authed, authed, self.last_check)

                if authed and internet:
                    self._log("在线正常 (%s / 认证页OK+外网OK)" % profile["name"])
                elif authed and not internet:
                    self._log("警告: 认证页在线但外网不通 (假在线), 尝试重登...")
                    self._alert("⚠️ 网络异常: 认证在线但外网不通, 尝试重登")
                    if ensure_login(profile, on_log=self._log):
                        self._log("重登完成")
                        self._alert("✅ 网络已恢复")
                    else:
                        self._log("重登失败!")
                        self._alert("❌ 自动重登失败, 请检查账号或网络")
                elif not authed:
                    self._log("检测到掉线 (%s), 自动登录中..." % profile["name"])
                    self._alert("⚠️ 检测到校园网掉线, 自动登录中...")
                    if ensure_login(profile, on_log=self._log):
                        self._log("自动登录成功")
                        self._alert("✅ 已自动恢复连接")
                    else:
                        self._log("自动登录失败 (稍后重试)")
                        self._alert("❌ 自动登录失败, 请检查账号密码或网络")
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


# ---------- 版本与诊断 ----------
APP_VERSION = "2.0.0"
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
    return "\n".join(lines)


# ---------- 锁 ----------
def acquire_lock():
    try:
        if os.path.exists(LOCK_PATH):
            with open(LOCK_PATH) as f:
                old_pid = f.read().strip()
            if old_pid and old_pid != str(os.getpid()):
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
