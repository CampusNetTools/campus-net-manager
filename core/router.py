# -*- coding: utf-8 -*-
"""路由器探测/体检/中继指引 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import netinfo  # noqa: F401

__all__ = ['OUI_BRANDS', '_arp_entries', 'get_gateway_mac', 'get_router_admin_url', '_private_http_url', 'parse_upnp_device_description', 'discover_router_upnp', 'inspect_router_admin', 'gen_tunnel_key', 'detect_gateway_mode', 'relay_stealth_check', 'vender_lookup', 'router_fingerprint', 'detect_router_hardware', 'evaluate_flash_readiness', 'hotspot_on', 'open_wifi_settings', 'open_hotspot_settings', 'get_router_brand', '_brand_relay_guide', 'router_guide', 'list_hotspot_clients', 'start_mobile_hotspot', 'fmt_bytes', 'lookup_firmware_urls', 'download_firmware', 'sha256_of_file']

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
    for line in netinfo._run_decode(["arp", "-an"], timeout=3).splitlines():
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
    gw = netinfo.get_gateway()
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
    gw = netinfo.get_gateway()
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
                    b"huawei", b"tenda", b"mercury", b"asus", b"netgear", b"d-link",
                    b"gateway", b"gpon", b"epon", b"\xe5\x85\x89\xe7\x8c\xab", b"onn",
                    b"zte", b"fiberhome", b"\xe7\x83\xbd\xe7\x81\xab", b"\xe8\x81\x94\xe9\x80\x9a",
                    b"unicom", b"telecom", b"chinanet")

    def probe(item):
        ip, mac = item
        try:
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            # 常见管理端口: HTTP 80 / 8080 都要试 (光猫/路由器管理页常在 8080)
            for port in (80, 8080):
                try:
                    req = urllib.request.Request("http://%s:%d/" % (ip, port),
                                                 headers={"User-Agent": "Mozilla/5.0"}, method="GET")
                    resp = opener.open(req, timeout=0.8)
                    body = resp.read(32768).lower()
                    known_oui = bool(mac and mac[:8].upper() in OUI_BRANDS)
                    # 默认网关可以是家用路由器/光猫；其他 ARP 主机必须有路由器/光猫品牌图证据，
                    # 防止把校园网内任意 Web 服务误判成管理页。
                    if len(body) > 200 and b"<" in body and (
                            ip == gw or known_oui or any(word in body for word in router_words)):
                        return "http://%s:%d/" % (ip, port)
                except Exception:
                    continue
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


def gen_tunnel_key(length=16):
    """生成隧道共享的随机防蹭网口令 (字母+数字, 去易混淆字符)。"""
    import secrets
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def detect_gateway_mode():
    """检测当前网关模式: 电脑直连网络(computer) 还是 经路由器(router)。
    判断依据: 网关是否是一台路由器(有管理页/UPnP/对应品牌 MAC), 且本机非网关本身。
    返回 dict: {mode: 'router'|'computer'|'unknown', gateway, gateway_mac, brand,
    description}"""
    gw = netinfo.get_gateway()
    if not gw:
        return {"mode": "unknown", "gateway": "", "gateway_mac": "", "brand": "",
                "description": "未检测到默认网关"}
    gmac = get_gateway_mac()
    brand_val = get_router_brand()
    if isinstance(brand_val, tuple):
        brand = brand_val[0] if brand_val else ""
    elif not isinstance(brand_val, str):
        brand = str(brand_val or "")
    else:
        brand = brand_val
    # 判断是否为路由器: 有品牌MAC + 网关是私有地址(通常是路由器/AP)
    is_router = bool(brand) or (gmac and gmac not in ("", "00:00:00:00:00:00"))
    # 常见路由器网关段: 192.168.x.1 / 10.x.x.1 / 172.16-31.x.1
    gw_is_lan = bool(re.match(r"^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.)", gw or ""))
    if is_router and gw_is_lan:
        mode = "router"
        desc = "经路由器接入（网关 %s）" % gw
    else:
        mode = "computer"
        desc = "电脑直连网络（网关 %s）" % gw
    return {"mode": mode, "gateway": gw, "gateway_mac": gmac or "", "brand": brand,
            "description": desc}


def relay_stealth_check():
    """中继/路由器场景下的"单设备伪装"检测与建议。

    目的: 校园网按出口IP(路由器)判断网络使用。若路由器下挂了多台设备,
    校园网可能通过 ARP 表/设备指纹/并发连接看出"共享", 触发关注。
    本函数检测当前 ARP 表中可见的设备数, 评估"多设备泄露"风险, 并给出
    路由器侧的轻量伪装建议 (改 TTL 统一 / 关闭 WPS 等, 不加密不掉速)。

    返回 dict: {
        gateway, gateway_mac, brand, device_count, visible_devices: [...],
        risk (low/mid/high), advice: [...]
    }"""
    gw = netinfo.get_gateway()
    gmac = get_gateway_mac()
    brand = get_router_brand()
    # get_router_brand 可能返回 字符串 或 (品牌, ip) 元组
    if isinstance(brand, tuple):
        brand = brand[0] if brand else ""
    elif not isinstance(brand, str):
        brand = str(brand or "")
    entries = _arp_entries()
    # 局域网范围: 排除外网/组播/本网关
    local_devices = []
    for ip, mac in entries:
        if mac == gmac:
            continue
        if ip.startswith(("224.", "239.", "255.", "127.")):
            continue
        if mac in ("ff:ff:ff:ff:ff:ff", "00:00:00:00:00:00"):
            continue
        local_devices.append({"ip": ip, "mac": mac, "brand": vender_lookup(mac)})
    # 大多数校园网/路由器网段是私有地址
    count = len(local_devices)
    if count <= 0:
        risk = "low"
    elif count <= 2:
        risk = "mid"
    else:
        risk = "high"

    advice = [
        "在路由器上关闭 WPS / UPnP 的对外广播，避免被扫描到真实设备数",
        "路由器无线设为「仅 2.4G 或 5G 单频段中继」并隐藏 SSID（减少广播泄露）",
        "若路由器支持，可统一修改 NAT/防火墙的 TTL 为固定值（如 64），防止被按跳数判断多设备",
        "关闭路由器上不必要的「远程管理 / 云端」功能，减少对外暴露",
    ]
    if count == 0:
        advice.insert(0, "当前仅检测到本机与路由器，未发现其他局域网设备，共享痕迹较少。")
    return {
        "gateway": gw or "",
        "gateway_mac": gmac or "",
        "brand": brand or "",
        "device_count": count,
        "visible_devices": local_devices[:8],
        "risk": risk,
        "advice": advice,
    }


def vender_lookup(mac):
    """通过 MAC 前缀查厂商(复用 _VENDOR 表); 查不到返回空。"""
    if not mac:
        return ""
    mac = mac.replace(":", "").upper()
    for prefix, name in OUI_BRANDS.items():
        if mac.startswith(prefix.replace(":", "").upper()):
            return name
    return ""


def router_fingerprint(gateway=None, mac=None):
    """生成不含凭据的路由器标识；优先用 MAC，退化为网关地址。"""
    gateway = netinfo.get_gateway() if gateway is None else gateway
    mac = get_gateway_mac() if mac is None else mac
    return (mac or gateway or "unknown").lower()


def detect_router_hardware():
    """只读路由器体检。返回证据与保守结论，绝不执行刷机。"""
    gateway = netinfo.get_gateway()
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
    if common.IS_MACOS:
        # macOS 没有稳定的无权限命令读取 Internet Sharing 状态，由界面提示用户确认。
        return None
    out = netinfo._run_decode(["powershell", "-NoProfile", "-Command",
                       "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                       "Where-Object { $_.IPAddress -like '192.168.137.*' } | "
                       "Select-Object -First 1 -ExpandProperty IPAddress"], timeout=15)
    return "192.168.137" in out


def open_wifi_settings():
    """打开当前平台的 Wi-Fi 设置页。"""
    try:
        if common.IS_MACOS:
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.wifi-settings-extension"])
        else:
            os.startfile("ms-settings:network-wifi")
        return True
    except Exception:
        return False


def open_hotspot_settings():
    """打开 Windows 移动热点设置页"""
    try:
        if common.IS_MACOS:
            subprocess.Popen(["open", "x-apple.systempreferences:com.apple.Sharing-Settings.extension"])
        else:
            os.startfile("ms-settings:network-mobilehotspot")
        return True
    except Exception:
        return False


# ---------- 热点客户端列表 + 流量估算 ----------

def _iface_total_bytes(iface):
    """读取接口累计收发字节(ifconfig / netstat -I); 失败返 None。"""
    try:
        if common.IS_MACOS:
            out = netinfo._run_decode(["ifconfig", iface], timeout=3)
        else:
            # Windows: 用 netstat -e 拿全接口汇总(不够精确, 但无依赖)
            out = netinfo._run_decode(["netstat", "-e"], timeout=3)
            return None  # Windows 走 Get-NetAdapterStatistics 路径, 这里不解析
        m = re.search(r"RX bytes:(\d+).*?TX bytes:(\d+)", out, re.S)
        if m:
            return int(m.group(1)), int(m.group(2))
    except Exception:
        pass
    return None


def _iface_list():
    """列出本机所有 IPv4 接口名(macOS 用 ifconfig, Windows 用 Get-NetAdapter)."""
    if common.IS_MACOS:
        out = netinfo._run_decode(["ifconfig", "-l"], timeout=3)
        return [x for x in out.split() if x]
    # Windows: PowerShell 拿 adapter 名
    out = netinfo._run_decode([
        "powershell", "-NoProfile", "-Command",
        "Get-NetAdapter -ErrorAction SilentlyContinue | "
        "Where-Object {$_.Status -eq 'Up'} | Select-Object -ExpandProperty Name"
    ], timeout=8)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def list_hotspot_clients():
    """返回连接到本机热点/共享 NAT 的设备列表 + 流量估算。
    每项 dict: {ip, mac, vendor, tx_bytes, rx_bytes, iface, since, note}
    跨平台: macOS 走 arp + ifconfig bridge0; Windows 走 Get-NetNeighbor + Get-NetIPStatistics。
    无热点/共享时返 [].
    """
    # 1) 找当前作为热点/共享 NAT 网关的接口
    #    - macOS: bridge0/bridge100 等(系统开 Internet Sharing 时自动创建)
    #    - Windows: "本地连接*XX" / "Wi-Fi" + Microsoft Wi-Fi Direct Virtual Adapter
    candidates = _hotspot_iface_candidates()
    if not candidates:
        return []
    clients = []
    seen = set()
    for iface in candidates:
        for entry in _iface_clients(iface):
            key = entry.get("ip", "") + "|" + entry.get("mac", "")
            if key in seen:
                continue
            seen.add(key)
            clients.append(entry)
    return clients


def _hotspot_iface_candidates():
    """识别作为热点/共享 NAT 的接口名。"""
    names = set()
    if common.IS_MACOS:
        # macOS Internet Sharing 时会创建 bridge100 (NAT 子网), 客户端在 bridge100 子网
        # 也可能是用户手动创建的 bridge0. 通过 ifconfig 看 inet 192.168.x.1
        out = netinfo._run_decode(["ifconfig"], timeout=4)
        current = None
        for line in out.splitlines():
            m = re.match(r"^([a-z]+\d*):", line)
            if m:
                current = m.group(1)
                continue
            if current and re.search(r"inet (\d+\.\d+\.\d+\.\d+).*netmask 0xffffff00", line):
                # 256 地址子网通常是 NAT 网关(192.168.x.1)
                ipm = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", line)
                if ipm and ipm.group(1).endswith(".1"):
                    names.add(current)
        # 也接受 bridge100 等已知共享接口(防漏检)
        for b in ("bridge0", "bridge100", "bridge101", "bridge102"):
            if re.search(rf"^{b}:.*\n.*inet ", out, re.M | re.S):
                names.add(b)
    else:
        # Windows: 移动热点 = Microsoft Wi-Fi Direct Virtual Adapter (Netwtw 之类),
        # 也可能是 "本地连接*XX" (ICS). 用 PowerShell 查 v4 子网不是 APIPA 的
        out = netinfo._run_decode([
            "powershell", "-NoProfile", "-Command",
            "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
            "Where-Object { $_.IPAddress -like '192.168.*' -and $_.PrefixLength -le 24 } | "
            "Select-Object InterfaceAlias,IPAddress"
        ], timeout=8)
        for ln in out.splitlines():
            parts = ln.strip().split()
            if len(parts) >= 2 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[-1]):
                names.add(parts[0])
    return sorted(names)


def _iface_clients(iface):
    """拿指定接口下的客户端 IP+MAC+流量(平台分支)."""
    out = []
    if common.IS_MACOS:
        # macOS: arp -an 看整个表, 过滤落在 iface 子网内的 IP. 流量的"按 IP 估算"靠
        # netstat -f inet 抽样(普通用户能跑); 标注 (粗略) + 加上 bridge0 接口总流量给上下文.
        # 1) 找 iface 子网
        ifc = netinfo._run_decode(["ifconfig", iface], timeout=3)
        sub = re.search(r"inet (\d+\.\d+\.\d+)\.\d+ netmask 0x(..)(..)(..)", ifc)
        if not sub:
            return []
        base = sub.group(1)
        # netmask bytes -> mask length
        nm = int(sub.group(2), 16) * 65536 + int(sub.group(3), 16) * 256 + int(sub.group(4), 16)
        bits = bin(nm).count("1")
        # 2) 抽样 netstat -an 看每个 src IP 的字节(粗略但 sudo-free)
        sample = netinfo._run_decode(["netstat", "-an", "-f", "inet", "-p", "tcp"], timeout=4)
        # netstat -I iface -b 在 macOS 需要 sudo; 退化用 ifconfig 总字节 + 客户端数均分
        total = _iface_total_bytes(iface)
        total_note = ""
        if total:
            total_note = "bridge %s 总 RX/TX: %s / %s" % (
                iface, fmt_bytes(total[0]), fmt_bytes(total[1]))
        # 3) arp 表筛子网内
        for ip, mac in _arp_entries():
            if ip.startswith(base + ".") and ip != "%s.1" % base and ip != "%s.255" % base:
                vendor = vender_lookup(mac)
                out.append({
                    "ip": ip, "mac": mac, "vendor": vendor,
                    "rx_bytes": None, "tx_bytes": None,
                    "iface": iface, "since": None,
                    "note": total_note or None,
                })
    else:
        # Windows: Get-NetNeighbor 拿热点客户端, Get-NetIPStatistics 拿每 IP 流量
        neigh = netinfo._run_decode([
            "powershell", "-NoProfile", "-Command",
            f"Get-NetNeighbor -InterfaceAlias '{iface}' -ErrorAction SilentlyContinue | "
            "Where-Object {$_.State -eq 'Reachable'} | "
            "Select-Object -ExpandProperty IPAddress"
        ], timeout=8)
        ips = [ln.strip() for ln in neigh.splitlines() if re.match(r"^\d+\.\d+\.\d+\.\d+$", ln.strip())]
        # 每 IP 流量
        ipstat = {}
        if ips:
            stats = netinfo._run_decode([
                "powershell", "-NoProfile", "-Command",
                "Get-NetIPStatistics -ErrorAction SilentlyContinue | "
                "Where-Object {$_.IPAddress -in @(%s)} | "
                "Select-Object IPAddress,BytesReceived,BytesSent" % ",".join("'%s'" % x for x in ips)
            ], timeout=10)
            for ln in stats.splitlines()[3:]:  # 跳过表头
                m = re.search(r"(\d+\.\d+\.\d+\.\d+)\s+(\d+)\s+(\d+)", ln)
                if m:
                    ipstat[m.group(1)] = (int(m.group(2)), int(m.group(3)))
        # arp 表查 MAC
        arp_map = {ip: mac for ip, mac in _arp_entries()}
        for ip in ips:
            mac = arp_map.get(ip, "")
            out.append({
                "ip": ip, "mac": mac, "vendor": vender_lookup(mac),
                "rx_bytes": ipstat.get(ip, (None, None))[0],
                "tx_bytes": ipstat.get(ip, (None, None))[1],
                "iface": iface, "since": None, "note": None,
            })
    return out


def fmt_bytes(n):
    """字节数 -> 人类可读 (KiB/MiB/GiB)"""
    try:
        n = int(n)
    except Exception:
        return str(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024:
            return "%.1f %s" % (n, unit) if unit != "B" else "%d %s" % (n, unit)
        n /= 1024
    return "%.1f PiB" % n


def start_mobile_hotspot():
    """Windows 一键开启移动热点 (PowerShell 优先, netsh 兜底).
    macOS 上 Internet Sharing 无法脚本化, 返 False 让调用方跳系统设置.
    返回: (ok: bool, message: str)."""
    if common.IS_MACOS:
        return False, "macOS 互联网共享不支持脚本化, 请手动到「系统设置 → 通用 → 共享」开启"
    # 1) 优先 PowerShell Start-MobileHotspot (需要 Windows 10+ 且网卡支持)
    out = netinfo._run_decode([
        "powershell", "-NoProfile", "-Command",
        "Start-MobileHotspot -ErrorAction SilentlyContinue; "
        "if ($?) { 'OK' } else { 'FAIL' }"
    ], timeout=15)
    if "OK" in out:
        return True, "已通过 PowerShell 启动移动热点"
    # 2) 兜底: netsh hostednetwork (老 Win 支持)
    out2 = netinfo._run_decode([
        "netsh", "wlan", "start", "hostednetwork"
    ], timeout=10)
    if "started" in out2.lower() or "已启动" in out2 or "Started" in out2:
        return True, "已通过 netsh 启动 hostednetwork 热点"
    return False, "网卡可能不支持 hostednetwork, 请到「设置 → 移动热点」手动开启"


def get_router_brand():
    """返回 (品牌, 管理地址); 识别不到返回 (None, 网关)"""
    gw = netinfo.get_gateway()
    mac = get_gateway_mac()
    brand = None
    if mac:
        oui = mac[:8].upper()
        brand = OUI_BRANDS.get(oui)
    return brand, gw


# 各品牌"无线中继"设置路径指引 (目标 = 上游WiFi名 + 是否要账号密码认证)
def _brand_relay_guide(brand, target_ssid, need_auth):
    """生成指定品牌路由器连「上游WiFi」做无线中继的分步指引。
    target_ssid: 上游主路由/校园网的WiFi名; need_auth: 中继时是否需输入上游账号密码。"""
    auth_extra = ("\n  → 输入上游 WiFi 的账号密码" if need_auth else
                  "\n  → 输入主路由的 WiFi 密码")
    guides = {
        "华为": "华为路由器：\n  打开管理页 → 点「更多功能」→「网络设置」→「无线中继」\n"
                "  → 开启无线中继 → 扫描 WiFi → 选择「%s」%s → 保存\n"
                "  (也可用「智慧生活 App」远程设置)",
        "小米": "小米路由器：\n  打开管理页 →「常用设置」→「上网设置」→ 工作模式选「无线中继」\n"
                "  → 扫描 WiFi → 选择「%s」%s → 保存\n  (也可用「米家 App」远程设置)",
        "TP-LINK": "TP-LINK 路由器：\n  打开管理页 →「应用管理」→「无线桥接」→ 开始设置\n"
                   "  → 扫描 → 选择「%s」%s → 保存",
        "水星": "水星路由器：\n  打开管理页 →「无线设置」→「无线桥接」→ 扫描 → 选择「%s」%s → 保存",
        "腾达": "腾达路由器：\n  打开管理页 →「无线设置」→「无线中继」→ 扫描 → 选择「%s」%s → 保存",
        "迅捷(FAST)": "迅捷 FAST 路由器：\n  打开管理页 → 点顶部「高级设置」→「无线设置」→「无线中继 / WISP」\n"
                      "  → 开启无线中继 → 扫描 WiFi → 选择「%s」%s → 保存\n"
                      "  (FAC1200R 等型号的中继在「高级设置」里, 不在 WAN口设置)",
        "华硕": "华硕路由器：\n  打开管理页 →「无线网络」→「无线中继」/ 或「外部网络」WISP 模式\n"
                "  → 扫描 → 选择「%s」%s → 保存",
        "网件": "网件路由器：\n  打开管理页 →「高级」→「无线设置」→「中继」/「桥接」→ 扫描 → 选择「%s」%s → 保存",
        "中兴": "中兴路由器：\n  打开管理页 →「网络」→「无线中继」→ 扫描 → 选择「%s」%s → 保存",
        "360": "360 路由器：\n  打开管理页 →「路由设置」→「无线中继」→ 扫描 → 选择「%s」%s → 保存",
        "D-Link": "D-Link 路由器：\n  打开管理页 →「设置」→「无线设置」→「中继模式」→ 扫描 → 选择「%s」%s → 保存",
    }
    if brand in guides:
        return guides[brand] % (target_ssid, auth_extra)
    return ("通用步骤（大部分路由器适用）：\n"
            "  1. 打开管理页（浏览器输入上面的地址）\n"
            "  2. 登录（账号密码在路由器底部标签，常见 admin/admin）\n"
            "  3. 找到「无线中继 / WISP / 桥接 / 无线扩展」功能\n"
            "  4. 扫描 WiFi → 选择「%s」\n"
            "  5. %s → 保存\n"
            "  6. 等路由器重启，完成中继" % (target_ssid, auth_extra.strip()))


def router_guide(target_ssid="LIDA-UNIVERSITY", need_auth=True):
    """返回 (品牌, 管理地址, 操作指引文字)。
    target_ssid: 中继要连接的上游WiFi名(默认校园网)。need_auth: 中继是否需输上游账号密码。"""
    brand, gw = get_router_brand()
    guide = _brand_relay_guide(brand, target_ssid, need_auth)
    return brand, gw, guide


# ---------- 固件下载 / 校验 / 路由器方案索引 ----------

# 品牌 -> 固件搜索/下载入口(只列官方页面链接, 不内置镜像以免携带第三方文件)
_FIRMWARE_SOURCES = {
    "华为": {
        "vendor_search": "https://consumer.huawei.com/en/support/routers/",
        "openwrt_toh": "https://openwrt.org/toh/hw.start",
        "note": "华为家用路由器仅部分机型在 OpenWrt 官方适配列表中。\n"
                "EMUI/鸿蒙智联路由器不支持 OpenWrt, 建议保留厂商固件。"
    },
    "小米": {
        "vendor_search": "https://www.mi.com/service/miwifi/settings",
        "openwrt_toh": "https://openwrt.org/toh/xiaomi/xiaomi",
        "note": "小米 / 红米路由器大多有 Padavan / OpenWrt 第三方固件。\n"
                "刷前务必核对型号完全一致(包括末尾小版本号)。"
    },
    "TP-LINK": {
        "vendor_search": "https://www.tp-link.com/en/support/download/",
        "openwrt_toh": "https://openwrt.org/toh/tp-link/start",
        "note": "TP-LINK 是 OpenWrt 官方适配最多的品牌之一, 支持型号广。"
    },
    "水星": {
        "vendor_search": "https://service.mercurycom.com.cn/",
        "openwrt_toh": "https://openwrt.org/toh/tp-link/start",
        "note": "水星与 TP-LINK 同源, 可共用 OpenWrt 适配（核对硬件版本号 Rev 前缀）。"
    },
    "迅捷(FAST)": {
        "vendor_search": "https://www.fastcom.com.cn/",
        "openwrt_toh": "https://openwrt.org/toh/tp-link/start",
        "note": "迅捷 FAST 与 TP-LINK 同源, FAC1200R / FW316R 等型号在 OpenWrt 有移植。"
    },
    "腾达": {
        "vendor_search": "https://www.tenda.com.cn/support/download.html",
        "openwrt_toh": "https://openwrt.org/toh/tenda/start",
        "note": "腾达家用型号大多支持 OpenWrt (核对型号完全一致)。"
    },
    "华硕": {
        "vendor_search": "https://www.asus.com/networking-iot-servers/wifi-routers/",
        "merlin": "https://www.asuswrt-merlin.net/",
        "note": "华硕官方固件已开放; 想要更强功能可刷 Merlin (asuswrt-merlin)。\n"
                "Merlin 与 OpenWrt 不同, 是 ASUS 官方分支的第三方增强版本。"
    },
    "网件": {
        "vendor_search": "https://www.netgear.com/support/product/",
        "openwrt_toh": "https://openwrt.org/toh/netgear/start",
        "note": "网件多型号在 OpenWrt 官方列表, 社区资源丰富。"
    },
    "中兴": {
        "vendor_search": "https://www.zte.com.cn/global/support",
        "openwrt_toh": "https://openwrt.org/toh/zte/start",
        "note": "中兴运营商定制版机型通常锁定固件; 自购型号大多可刷。"
    },
    "360": {
        "vendor_search": "https://luyou.360.cn/",
        "openwrt_toh": "https://openwrt.org/toh/360.start",
        "note": "360 路由器可刷 OpenWrt/PandoraBox, 注意核对芯片类型。"
    },
    "D-Link": {
        "vendor_search": "https://www.dlink.com/en/support",
        "openwrt_toh": "https://openwrt.org/toh/d-link/start",
        "note": "D-Link 部分型号官方开放, 详情查 OpenWrt 适配表。"
    },
    "斐讯": {
        "vendor_search": "https://www.luyouwang.com.cn/",
        "openwrt_toh": "https://openwrt.org/toh/phicomm/start",
        "note": "斐讯(Phicomm)K2/K2P/K3 等型号社区活跃, 多适配。"
    },
}


def lookup_firmware_urls(brand, model="", revision=""):
    """路由器统一刷固件准备: 返回适配入口 + 提示, 不直接 OTA 刷写。

    返回 dict:
        brand, model, revision, vendor_name, vendor_url, openwrt_toh,
        merlin_url (如有), note
    """
    if not brand:
        return {
            "brand": "", "model": model, "revision": revision,
            "vendor_name": "", "vendor_url": "",
            "openwrt_toh": "",
            "merlin_url": "",
            "note": "尚未识别路由器品牌; 请确认电脑已连接路由器 WiFi 后重试, 或在「保存识别结果」里手动填入品牌/型号。"
        }
    src = _FIRMWARE_SOURCES.get(brand)
    if not src:
        return {
            "brand": brand, "model": model, "revision": revision,
            "vendor_name": brand, "vendor_url": "",
            "openwrt_toh": "https://openwrt.org/toh/start",
            "note": "暂未内置该品牌的固件入口; 直接查 OpenWrt 官方适配列表, 或浏览器搜索「%s + OpenWrt 适配」。" % brand
        }
    return {
        "brand": brand, "model": model, "revision": revision,
        "vendor_name": brand, "vendor_url": src["vendor_search"],
        "openwrt_toh": src.get("openwrt_toh", "https://openwrt.org/toh/start"),
        "merlin_url": src.get("merlin", ""),
        "note": src["note"]
    }


def sha256_of_file(path, chunk=65536):
    """计算文件 SHA256 (用于刷机前校验固件包完整)."""
    import hashlib
    h = hashlib.sha256()
    try:
        with open(path, "rb") as handle:
            while True:
                block = handle.read(chunk)
                if not block:
                    break
                h.update(block)
        return h.hexdigest()
    except Exception:
        return ""


def download_firmware(url, save_path, expected_sha256="", progress_cb=None,
                      timeout=120, headers=None):
    """下载固件到本地(只下载不刷入); 给定 SHA256 时自动校验。

    progress_cb(done_bytes, total_bytes) 用于进度条 (主线程需 after 切回).
    超时或失败抛 RuntimeError 或返回 (ok, msg, sha256).
    """
    import urllib.request
    if not url or not url.startswith(("http://", "https://")):
        return (False, "URL 非法(只支持 http/https)", "")
    req_headers = {"User-Agent": "CampusNetManager/4"}
    if headers:
        req_headers.update(headers)
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            total = int(response.headers.get("Content-Length", "0") or 0)
            os.makedirs(os.path.dirname(os.path.abspath(save_path)) or ".", exist_ok=True)
            done = 0
            with open(save_path, "wb") as out:
                while True:
                    block = response.read(8192)
                    if not block:
                        break
                    out.write(block)
                    done += len(block)
                    if progress_cb:
                        try:
                            progress_cb(done, total)
                        except Exception:
                            pass
            sha = sha256_of_file(save_path)
            if expected_sha256 and sha.lower() != expected_sha256.lower():
                try:
                    os.remove(save_path)
                except Exception:
                    pass
                return (False, "SHA256 校验失败, 已删除不完整文件", sha)
            return (True, "下载完成 (%.1f MB)" % (done / 1048576), sha)
    except Exception as exc:
        return (False, "下载失败: %s" % exc, "")

