# -*- coding: utf-8 -*-
"""
shared_proxy.py - 局域网 HTTP 代理隧道服务
让手机/平板等设备借本机网络访问外网 (设备无需认证/无需装App,
只需在 Wi-Fi 设置里把代理指向本机 IP:端口)。
支持: HTTP CONNECT 隧道(HTTPS) + 绝对URL转发(HTTP)
"""
import socket
import threading
import urllib.request


class SharedProxy:
    """轻量 HTTP 代理: 监听局域网端口, 转发 TCP 流量。
    支持访问控制: allowed 集合 + on_ask 回调(新设备询问, 防开放代理被滥用)"""

    def __init__(self, port=8080, host="0.0.0.0", allowed=None, on_ask=None, pac_host=None,
                 shared_key=None, upstream_proxy=None):
        self.port = port
        self.host = host
        self.allowed = set(allowed or [])   # 已授权客户端 IP
        self.on_ask = on_ask                # callable(ip) -> bool 新设备是否放行
        self.pac_host = pac_host             # 自动代理配置文件中返回给客户端的局域网地址
        # 防蹭网: 共享口令。客户端代理请求需带 X-Shared-Key 头, 与口令一致才放行。
        # 留空则不校验口令(仅靠 IP 白名单), 兼容旧用法。
        self.shared_key = shared_key or ""
        # VPN 上游代理: dict {host, port, type('http'|'socks5')}。设置后, 本机收到的
        # 所有设备流量经 CONNECT 隧道转发到该上游代理, 实现"电脑当网关+VPN全透明"。
        self.upstream_proxy = upstream_proxy or None
        self._listener = None
        self._running = False
        self._threads = []

    @property
    def running(self):
        return self._running

    def start(self):
        if self._running:
            return True
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((self.host, self.port))
            self.port = s.getsockname()[1]
            s.listen(32)
            s.settimeout(0.5)
            self._listener = s
            self._running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
            return True
        except Exception as e:
            self._running = False
            try:
                self._listener.close()
            except Exception:
                pass
            raise e

    def stop(self):
        self._running = False
        try:
            self._listener.close()
        except Exception:
            pass
        for t in self._threads[:]:
            try:
                t.join(0.3)
            except Exception:
                pass
        self._threads = []

    def _check_allow(self, ip):
        """访问控制: 白名单直接放行, 新设备走询问回调"""
        if ip in self.allowed:
            return True
        if self.on_ask is not None:
            try:
                if self.on_ask(ip):
                    self.allowed.add(ip)
                    return True
            except Exception:
                pass
        return False

    @staticmethod
    def _detect_ua(head):
        """通过 User-Agent 判断设备类型: ios / android / harmony / other"""
        ua = b""
        for ln in head.split(b"\r\n"):
            if ln.lower().startswith(b"user-agent:"):
                ua = ln[len(b"user-agent:"):].strip().lower()
                break
        if b"iphone" in ua or b"ipad" in ua or b"ios" in ua:
            return "ios"
        if b"harmony" in ua or b"openharmony" in ua or b"emui" in ua:
            return "harmony"
        if b"android" in ua:
            return "android"
        return "other"

    @staticmethod
    def _setup_page(ua_kind, host, port, pac_url, mob_url, key):
        """生成统一智能引导页, 根据设备系统给出对应一键配置方式。
        ua_kind: ios / android / harmony / other"""
        ip = host
        if ua_kind == "ios":
            head = (
                "<h2>📱 检测到 iPhone / iPad</h2>"
                "<p>点击下方按钮下载配置描述文件，随后在系统弹窗里点一次"
                "<b>「安装」</b>即可自动配好代理，无需手动输入。</p>"
                "<p><a class='btn' href='%s' style='background:#0a84ff'>"
                "⬇ 下载配置并自动安装</a></p>" % mob_url)
        elif ua_kind in ("android", "harmony"):
            head = (
                "<h2>📱 检测到 %s</h2>"
                "<p>请按下面两步操作，服务器和端口已经填好：</p>"
                "<p><a class='btn' href='#manual' onclick='fillManual()'>"
                "⚡ 一键获取自动配置地址</a></p>" % ("鸿蒙/华为" if ua_kind == "harmony" else "安卓"))
        else:
            head = (
                "<h2>🔗 隧道共享已就绪</h2>"
                "<p>在其他设备上配置以下代理即可连接（不同系统见下）：</p>")
        manual = (
            "<p><b>服务器(IP)：</b><code>%s</code></p>"
            "<p><b>端口：</b><code>%d</code></p>" % (ip, port))
        pac_section = (
            "<p>如果设备支持「自动代理配置」，可用：<br>"
            "<code>%s</code></p>" % pac_url)
        key_section = (
            "<p>🔐 首次连接需带口令：<b><code>%s</code></b></p>" % (key or "（未开启口令）"))
        note = (
            "<p style='color:#888'>提示：配置一次后，手机连同一个 Wi‑Fi 会自动生效，"
            "无需重复设置。</p>")
        return (
            "<!doctype html><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width'><title>校园网隧道共享</title>"
            "<style>body{font-family:-apple-system,sans-serif;padding:24px;line-height:1.7;"
            "max-width:520px;margin:auto;font-size:16px}code{word-break:break-all;background:#eef2f7;"
            "padding:10px;display:block;border-radius:8px;font-size:15px}"
            ".btn{display:inline-block;padding:12px 20px;border-radius:10px;color:#fff;"
            "text-decoration:none;font-size:16px;margin:6px 0}</style>"
            "%s%s%s%s%s" % (head, manual, pac_section, key_section, note)).encode("utf-8")

    @staticmethod
    def _ios_mobileconfig(host, port, key, label="校园网隧道"):
        """生成 iOS 配置描述文件 (GlobalHTTPProxy 手动代理)，用户点「安装」即自动配置。
        返回 bytes(plist/XML utf-8)。"""
        payload_uuid = "11111111-1111-1111-1111-111111111111"
        prof_uuid = "22222222-2222-2222-2222-222222222222"
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
            '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
            '<plist version="1.0">\n<dict>\n'
            '  <key>PayloadContent</key>\n  <array>\n    <dict>\n'
            '      <key>PayloadDescription</key><string>Configure HTTP Proxy</string>\n'
            '      <key>PayloadDisplayName</key><string>%s</string>\n'
            '      <key>PayloadIdentifier</key><string>com.campusnet.proxy.%s</string>\n'
            '      <key>PayloadType</key><string>com.apple.proxy.managed</string>\n'
            '      <key>PayloadUUID</key><string>%s</string>\n'
            '      <key>PayloadVersion</key><integer>1</integer>\n'
            '      <key>ProxyType</key><string>Manual</string>\n'
            '      <key>ProxyServer</key><string>%s</string>\n'
            '      <key>ProxyServerPort</key><integer>%d</integer>\n'
            '      <key>Proxies</key><dict>\n'
            '        <key>HTTPEnable</key><integer>1</integer>\n'
            '        <key>HTTPPort</key><integer>%d</integer>\n'
            '        <key>HTTPProxy</key><string>%s</string>\n'
            '      </dict>\n'
            '    </dict>\n  </array>\n'
            '  <key>PayloadDescription</key><string>校园网隧道共享代理配置</string>\n'
            '  <key>PayloadDisplayName</key><string>校园网隧道</string>\n'
            '  <key>PayloadIdentifier</key><string>com.campusnet.tunnel</string>\n'
            '  <key>PayloadOrganization</key><string>CampusNet</string>\n'
            '  <key>PayloadRemovalDisallowed</key><false/>\n'
            '  <key>PayloadType</key><string>Configuration</string>\n'
            '  <key>PayloadUUID</key><string>%s</string>\n'
            '  <key>PayloadVersion</key><integer>1</integer>\n'
            '</dict>\n</plist>\n'
            % (label, payload_uuid[:8], payload_uuid, host, port, port, host, prof_uuid)
        )
        return xml.encode("utf-8")

    # ---------- 内部 ----------
    def _accept_loop(self):
        while self._running:
            try:
                client, addr = self._listener.accept()
                t = threading.Thread(target=self._handle, args=(client, addr[0]), daemon=True)
                t.start()
                self._threads.append(t)
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle(self, client, client_ip):
        try:
            client.settimeout(20)
            data = b""
            while b"\r\n\r\n" not in data and len(data) < 65536:
                chunk = client.recv(4096)
                if not chunk:
                    return
                data += chunk
            head = data.split(b"\r\n\r\n", 1)[0]
            lines = head.split(b"\r\n")
            if not lines:
                return
            parts = lines[0].split(b" ")
            if len(parts) < 2:
                return
            method, target = parts[0].upper(), parts[1]
            if method == b"GET" and target.split(b"?", 1)[0] in (b"/proxy.pac", b"/wpad.dat"):
                host = self.pac_host or client.getsockname()[0]
                pac = ('function FindProxyForURL(url, host) { return "PROXY %s:%d; DIRECT"; }'
                       % (host, self.port)).encode("utf-8")
                client.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/x-ns-proxy-autoconfig\r\n"
                    b"Cache-Control: no-store\r\nConnection: close\r\nContent-Length: "
                    + str(len(pac)).encode("ascii") + b"\r\n\r\n" + pac)
                return
            if method == b"GET" and target.split(b"?", 1)[0] == b"/setup.mobileconfig":
                # iOS 配置描述文件: 下载后点「安装」即自动配置代理
                host = self.pac_host or client.getsockname()[0]
                mob = self._ios_mobileconfig(host, self.port, self.shared_key)
                client.sendall(
                    b"HTTP/1.1 200 OK\r\nContent-Type: application/x-apple-aspen-config\r\n"
                    b"Content-Disposition: attachment; filename=\"campusnet.mobileconfig\"\r\n"
                    b"Cache-Control: no-store\r\nConnection: close\r\nContent-Length: "
                    + str(len(mob)).encode("ascii") + b"\r\n\r\n" + mob)
                return
            if method == b"GET" and target.split(b"?", 1)[0] == b"/":
                host = self.pac_host or client.getsockname()[0]
                ua_kind = self._detect_ua(head)
                pac_url = "http://%s:%d/proxy.pac" % (host, self.port)
                mob_url = "http://%s:%d/setup.mobileconfig" % (host, self.port)
                page = self._setup_page(ua_kind, host, self.port, pac_url, mob_url,
                                        self.shared_key)
                client.sendall(b"HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\n"
                               b"Cache-Control: no-store\r\nConnection: close\r\nContent-Length: "
                               + str(len(page)).encode("ascii") + b"\r\n\r\n" + page)
                return
            if not self._check_allow(client_ip):
                client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                return
            # 防蹭网: 校验共享口令 (X-Shared-Key 头). 服务端设了口令才校验; 未设则跳过(兼容旧用法).
            if self.shared_key:
                key_ok = False
                for ln in lines:
                    if ln.lower().startswith(b"x-shared-key:"):
                        provided = ln.split(b":", 1)[1].strip()
                        if provided == self.shared_key.encode("utf-8", errors="ignore"):
                            key_ok = True
                        break
                if not key_ok:
                    client.sendall(b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n")
                    return
            if method == b"CONNECT":
                # HTTPS 隧道: 连上游后转发
                host, _, port = target.partition(b":")
                port = int(port) if port else 443
                upstream = self._connect(host.decode(errors="ignore"), port)
                if not upstream:
                    client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                    return
                client.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                # 剩余数据(可能和头一起收到)一并转发
                rest = data.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in data else b""
                self._relay(client, upstream, rest)
            else:
                # HTTP 代理: 绝对 URL 转相对路径转发
                url = target.decode(errors="ignore")
                if url.startswith("http://"):
                    rest_url = url[7:]
                    host, _, path = rest_url.partition("/")
                    port = 80
                    if ":" in host:
                        host, _, ps = host.partition(":")
                        port = int(ps) if ps.isdigit() else 80
                    path = "/" + path if path else "/"
                    upstream = self._connect(host, port)
                    if not upstream:
                        client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                        return
                    # 重写请求行: 绝对URL -> 路径, 去掉 Proxy-Connection
                    out_lines = []
                    for ln in lines:
                        if ln.startswith(b"Proxy-Connection"):
                            continue
                        if ln.startswith(method + b" "):
                            out_lines.append(method + b" " + path.encode() + b" HTTP/1.1")
                        else:
                            out_lines.append(ln)
                    new_head = b"\r\n".join(out_lines) + b"\r\n\r\n"
                    rest2 = data.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in data else b""
                    self._relay(client, upstream, new_head + rest2)
        except Exception:
            pass
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _connect(self, host, port, timeout=10):
        """连接到目标主机。若配置了 VPN 上游代理, 则先连上游并发 CONNECT 隧道,
        让目标流量经 VPN 转发 (实现电脑当网关+VPN全透明)。"""
        if self.upstream_proxy:
            return self._connect_via_upstream(host, port, timeout)
        try:
            u = socket.create_connection((host, port), timeout=timeout)
            u.settimeout(20)
            return u
        except Exception:
            return None

    def _connect_via_upstream(self, host, port, timeout=10):
        """经 VPN 上游代理建立 CONNECT 隧道到目标, 返回隧道 socket。"""
        up = self.upstream_proxy
        if not up:
            return None
        u = None
        try:
            u = socket.create_connection((up["host"], up["port"]), timeout=timeout)
            u.settimeout(20)
            # 发送 HTTP CONNECT 请求给上游, 请求建立到目标的隧道
            req = ("CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n"
                   "Proxy-Connection: keep-alive\r\n\r\n" % (
                       host, port, host, port)).encode("utf-8")
            u.sendall(req)
            # 读上游响应头
            resp = b""
            while b"\r\n\r\n" not in resp and len(resp) < 65536:
                chunk = u.recv(4096)
                if not chunk:
                    break
                resp += chunk
            # 上游代理可能需要认证 (407) 或直接拒绝 (403/502)
            head = resp.split(b"\r\n", 1)[0].decode("utf-8", errors="ignore")
            if " 200 " not in head and "200 connection" not in head.lower():
                u.close()
                return None
            return u
        except Exception:
            if u is not None:
                try:
                    u.close()
                except Exception:
                    pass
            return None

    def _relay(self, a, b, first=b""):
        if first:
            try:
                b.sendall(first)
            except Exception:
                try:
                    a.close()
                    b.close()
                except Exception:
                    pass
                return
        # 双向转发 (每方向一个线程, 避免 select 平台差异)
        def pipe(src, dst):
            try:
                while True:
                    d = src.recv(65536)
                    if not d:
                        break
                    dst.sendall(d)
            except Exception:
                pass
            finally:
                try:
                    dst.shutdown(socket.SHUT_WR)
                except Exception:
                    pass
        t1 = threading.Thread(target=pipe, args=(a, b), daemon=True)
        t2 = threading.Thread(target=pipe, args=(b, a), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()


def _ip_int(ip):
    """点分 IPv4 -> int (用于子网比较)"""
    return int.from_bytes(socket.inet_aton(ip), "big")


def _same_net(ip, other, mask_hex):
    """判断两个 IP 是否同网段。mask_hex 形如 'ffffe000'。"""
    try:
        m = int(mask_hex, 16)
        return (_ip_int(ip) & m) == (_ip_int(other) & m)
    except Exception:
        return False


def _iface_ips():
    """返回 [(接口名, IPv4, 掩码hex), ...] (排除回环/链路本地)。"""
    import re
    import subprocess
    try:
        out = subprocess.check_output(["ifconfig"], stderr=subprocess.STDOUT,
                                      timeout=3).decode("utf-8", "replace")
    except Exception:
        return []
    cur, rows = None, []
    for line in out.splitlines():
        m = re.match(r"^([A-Za-z0-9_]+):", line.strip())
        if m:
            cur = m.group(1)
            continue
        m = re.search(r"inet (\d+\.\d+\.\d+\.\d+) netmask 0x([0-9a-fA-F]+)", line)
        if m and cur:
            ip = m.group(1)
            if not ip.startswith(("127.", "169.254.")):
                rows.append((cur, ip, m.group(2)))
    return rows


def _default_gateway_ip():
    """当前"真实出口"默认网关 IP。

    先试 `route get default`; 若默认路由被 VPN/Clash(TUN) 抢走导致无 gateway,
    回退 netstat -rn 取第一条实体 IPv4 网关(跳过 link# 的虚拟默认路由)。
    """
    import re
    import subprocess
    ip_re = r"\d+\.\d+\.\d+\.\d+"
    try:
        out = subprocess.check_output(["route", "-n", "get", "default"],
                                      stderr=subprocess.STDOUT,
                                      timeout=3).decode("utf-8", "replace")
        m = re.search(r"gateway:\s*(%s)" % ip_re, out)
        if m:
            return m.group(1)
    except Exception:
        pass
    try:
        out = subprocess.check_output(["netstat", "-rn", "-f", "inet"],
                                      stderr=subprocess.STDOUT,
                                      timeout=3).decode("utf-8", "replace")
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "default":
                gw = parts[1]
                if re.match(r"^(%s)$" % ip_re, gw) and not gw.startswith("0."):
                    return gw
    except Exception:
        pass
    return None


def get_lan_ips():
    """返回本机"适合填给其他设备"的局域网 IPv4 列表, 按可用性排序:

    - 排除虚拟隧道接口(utun/tun/ppp/awdl/llw 等)与 Clash 假 IP(198.18.0.0/15)——
      这些地址手机/平板根本到不了;
    - 保留真实网卡(en/eth) 与 bridge(电脑开热点时手机所在网段);
    - 与默认网关同网段的最优先: 手机连同一校园网/同一路由器时最常用。
    返回如 ['10.52.188.32', '192.168.3.1'] (前者为校园网出口)。
    """
    import re
    _VIRT = re.compile(r"^(utun|tun|ppp|awdl|llw|gif|stf|ipsec|utap|tap|wg|zt|vmnet|vnic)", re.I)
    gw = _default_gateway_ip()
    phys, hot = [], []
    for iface, ip, mask in _iface_ips():
        if _VIRT.match(iface) or ip.startswith("198.18."):
            continue                       # 纯虚拟/假 IP, 直接丢弃
        if iface.startswith("bridge"):
            hot.append((iface, ip, mask))  # 热点/共享网段, 放最后
        else:
            phys.append((iface, ip, mask))

    def key(item):
        iface, ip, mask = item
        same = bool(gw and _same_net(ip, gw, mask))
        return (0 if same else 1, iface)

    phys.sort(key=key)
    hot.sort(key=key)
    return [ip for _iface, ip, _mask in (phys + hot)]


def check_setup_page(host, port=8080, timeout=2):
    """启动后自动确认手机引导页和 PAC 服务确实可访问。"""
    try:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open("http://%s:%d/" % (host, port), timeout=timeout) as response:
            return response.status == 200 and "隧道共享已就绪" in response.read().decode("utf-8", errors="replace")
    except Exception:
        return False
