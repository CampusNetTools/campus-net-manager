# -*- coding: utf-8 -*-
"""
shared_proxy.py - 局域网 HTTP 代理隧道服务
让手机/平板等设备借本机网络访问外网 (设备无需认证/无需装App,
只需在 Wi-Fi 设置里把代理指向本机 IP:端口)。
支持: HTTP CONNECT 隧道(HTTPS) + 绝对URL转发(HTTP)
"""
import re
import socket
import subprocess
import threading
import urllib.request
import urllib.parse
import proxy_transport

def validate_upstream(upstream, timeout=2):
    """检查所填 HTTP 代理是否在监听；不修改系统 VPN 或静默绕过用户上游。"""
    if not upstream:
        return
    if upstream.get("type", "http") != "http":
        raise ValueError("请使用 VPN 客户端的 HTTP/混合代理端口，不能填写 SOCKS 专用端口")
    host = upstream.get("host", "")
    port = int(upstream.get("port", 0))
    if not host or not 1 <= port <= 65535:
        raise ValueError("上游代理地址或端口无效")
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError as exc:
        raise ValueError("上游 %s:%d 无法连接。请启动对应代理客户端或清空上游，使用电脑当前网络（含系统 VPN）。" % (host, port)) from exc


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
        self._allow_lock = threading.Lock()
        self._pending_allow = {}
        self.last_error = ""
        self.upload_bytes = 0
        self.download_bytes = 0
        self.relay_idle_timeout = 300
        self._active_clients = {}

        self._connections = set()
        self._connections_lock = threading.Lock()
        # 电脑自己所有 IPv4 接口(127.0.0.1 + en0/bridge0/bridge100/awdl0/...).
        # 收到 host 是自己的绝对 URL 时, 视同内嵌路径处理(返回引导页/mobileconfig/PAC),
        # 避免代理到 192.168.3.1:80 / 10.52.188.32:80 失败返 502, 触发 iOS Safari
        # "未接入互联网"误导文案。
        self._my_ips = self._collect_my_ips()

    @property
    def running(self):
        return self._running

    def check_exit(self):
        """独立检查代理出口的 TLS/HTTP；配置页可达不代表此检查通过。"""
        import ssl
        sock = self._connect("www.apple.com", 443, timeout=8)
        if sock is None:
            return self.last_error or "外网出口连接失败"
        try:
            with ssl.create_default_context().wrap_socket(sock, server_hostname="www.apple.com") as tls:
                tls.settimeout(8)
                tls.sendall(b"GET /library/test/success.html HTTP/1.1\r\nHost: www.apple.com\r\nConnection: close\r\n\r\n")
                response = bytearray()
                while len(response) < 32768:
                    data = tls.recv(4096)
                    if not data:
                        break
                    response.extend(data)
                if b" 200 " in response.split(b"\r\n", 1)[0] and b"Success" in response:
                    return "电脑外网测试通过；此检查不代表手机所有 App 均可用。"
                return "已连接外网，但测试页面返回异常；请检查认证或上游规则。"
        except Exception as exc:
            return "外网出口验证失败 (%s)；请检查上游、VPN 或校园认证。" % type(exc).__name__
        finally:
            sock.close()

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
        with self._connections_lock:
            connections = list(self._connections)
        for connection in connections:
            try:
                connection.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            connection.close()
        for t in self._threads[:]:
            try:
                t.join(0.3)
            except Exception:
                pass
        self._threads = []

    def _check_allow(self, ip):
        """访问控制: 白名单直接放行, 新设备走询问回调"""
        with self._allow_lock:
            if ip in self.allowed:
                return True
            pending = self._pending_allow.get(ip)
            owner = pending is None
            if owner:
                pending = threading.Event()
                self._pending_allow[ip] = pending
        if not owner:
            pending.wait(46)
            return ip in self.allowed
        try:
            if self.on_ask is not None and self.on_ask(ip):
                self.allowed.add(ip)
                return True
            self.last_error = "设备尚未授权；请在电脑主窗口允许设备连接"
            return False
        except Exception:
            return False
        finally:
            with self._allow_lock:
                self._pending_allow.pop(ip, None)
                pending.set()

    @staticmethod
    def _collect_my_ips():
        """列出本机所有 IPv4 接口(用于识别对'代理自己'的绝对 URL 请求)。
        macOS 走 ifconfig; Windows 没有 ifconfig, 用 getaddrinfo + ipconfig 兜底,
        否则只有 127.0.0.1, 引导页/PAC 的"代理到自己"识别在 Windows 上失效。"""
        ips = {"127.0.0.1"}
        try:
            out = subprocess.check_output(["ifconfig"], text=True, timeout=3,
                                          stderr=subprocess.DEVNULL)
            for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)", out):
                ips.add(m.group(1))
            if len(ips) > 1:
                return ips
        except Exception:
            pass
        # Windows / ifconfig 缺失: hostname 解析 + ipconfig 解析
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip and not ip.startswith("127."):
                    ips.add(ip)
        except Exception:
            pass
        try:
            kwargs = {"capture_output": True, "timeout": 5}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            out = subprocess.run(["ipconfig"], **kwargs).stdout.decode(
                "utf-8", errors="replace")
            # 注: 中文系统 ipconfig 输出是 GBK, 中文标签会乱码, 但 "IPv4"/":"/
            # 数字都是 ASCII 不受影响, 足以提取地址。
            for m in re.finditer(r"IPv4[^\r\n]*?:\s*(\d+\.\d+\.\d+\.\d+)", out):
                ip = m.group(1)
                if not ip.startswith(("127.", "169.254.")):
                    ips.add(ip)
        except Exception:
            pass
        return ips

    def _is_loopback_url(self, url):
        """绝对 URL 形式的 GET host 是否就是代理自己(任意接口)。"""
        if not url.startswith("http://"):
            return False
        rest = url[7:]
        host, _, _path = rest.partition("/")
        # 去掉 :port
        host_only = host.split(":", 1)[0].strip("[]")  # 兼容 IPv6
        if not host_only:
            return False
        # 主机名(本机 hostname)也算
        if host_only.lower() == socket.gethostname().lower():
            return True
        return host_only in self._my_ips

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
            '        <key>HTTPSEnable</key><integer>1</integer>\n'
            '        <key>HTTPSPort</key><integer>%d</integer>\n'
            '        <key>HTTPSProxy</key><string>%s</string>\n'
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
            % (label, payload_uuid[:8], payload_uuid, host, port, port, host, port, host, prof_uuid)
        )
        return xml.encode("utf-8")

    # ---------- 内部 ----------
    def _accept_loop(self):
        while self._running:
            try:
                client, addr = self._listener.accept()
                t = threading.Thread(target=self._handle, args=(client, addr[0]), daemon=True)
                t.start()
                self._threads = [worker for worker in self._threads if worker.is_alive()]
                self._threads.append(t)
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle(self, client, client_ip):
        with self._connections_lock:
            self._connections.add(client)
            self._active_clients[client_ip] = self._active_clients.get(client_ip, 0) + 1
        stage = "读取手机代理请求"
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
            # loopback 绝对 URL 识别: 手机 Safari 访问 http://192.168.3.1/ 或
            # http://10.52.188.32:8081/?key=... 时, host 是代理自己。
            # 代理到自己:80 会 502 触发 Safari "未接入互联网"误导。三种处理:
            #   1) host 是代理自己 + port 是本地服务端口(如 8081 控制台) -> 代理到 127.0.0.1:port
            #   2) host 是代理自己 + port 缺省或 == 代理端口(8080) -> 视同相对路径, 走引导页/mobileconfig
            #   3) host 是代理自己 + 其他 port -> 代理到 127.0.0.1:port (本地服务透传)
            if target.startswith(b"http://"):
                t = target.decode(errors="ignore")
                rest = t[7:]
                hp, _, path_only = rest.partition("/")
                host_only = hp.split(":", 1)[0].strip("[]")
                port_only = None
                if ":" in hp:
                    _, _, ps = hp.rpartition(":")
                    if ps.isdigit():
                        port_only = int(ps)
                is_self = (host_only.lower() == socket.gethostname().lower()
                           or host_only in self._my_ips)
                if is_self:
                    # path_only 已经包含 query，不能再次追加口令参数。
                    parsed = urllib.parse.urlsplit(t)
                    local_target = parsed.path or "/"
                    if parsed.query:
                        local_target += "?" + parsed.query
                    if port_only and port_only != self.port:
                        # 代理到本地服务(例如控制台 8081)
                        stage = "连接电脑本地服务"
                        upstream = socket.create_connection(("127.0.0.1", port_only), timeout=10)
                        if not upstream:
                            client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                            return
                        new_target = local_target.encode()
                        new_head = proxy_transport.forward_head(lines, method, new_target)
                        rest2 = data.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in data else b""
                        self._relay(client, upstream, new_head + rest2)
                        return
                    # port 缺省 / 等于代理端口 -> 视同相对路径, 走下面 / /setup.mobileconfig / proxy.pac
                    target = local_target.encode()
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
                    self.last_error = "设备代理口令校验失败（不是控制台口令）"
                    client.sendall(b"HTTP/1.1 407 Proxy Authentication Required\r\n\r\n")
                    return
            if method == b"CONNECT":
                # HTTPS 隧道: 连上游后转发
                stage = "解析 CONNECT 地址"
                parsed = urllib.parse.urlsplit("//" + target.decode("ascii"))
                host, port = parsed.hostname, parsed.port or 443
                if not host or parsed.username is not None:
                    raise ValueError("invalid authority")
                upstream = self._connect(host, port)
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
                    stage = "解析 HTTP 地址"
                    parsed = urllib.parse.urlsplit(url)
                    host, port = parsed.hostname, parsed.port or 80
                    path = parsed.path or "/"
                    if parsed.query:
                        path += "?" + parsed.query
                    upstream = self._connect(host, port)
                    if not upstream:
                        client.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
                        return
                    # 重写请求行: 绝对URL -> 路径, 去掉 Proxy-Connection
                    new_head = proxy_transport.forward_head(lines, method, path.encode())
                    rest2 = data.split(b"\r\n\r\n", 1)[1] if b"\r\n\r\n" in data else b""
                    self._relay(client, upstream, new_head + rest2)
        except Exception as exc:
            self.last_error = "%s失败 (%s)" % (stage, type(exc).__name__)
        finally:
            with self._connections_lock:
                self._connections.discard(client)
                count = self._active_clients.get(client_ip, 1) - 1
                if count:
                    self._active_clients[client_ip] = count
                else:
                    self._active_clients.pop(client_ip, None)
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
        except Exception as exc:
            self.last_error = "外网连接失败 (%s)" % type(exc).__name__
            return None

    def _connect_via_upstream(self, host, port, timeout=10):
        """经 VPN 上游代理建立 CONNECT 隧道到目标, 返回隧道 socket。"""
        up = self.upstream_proxy
        if not up:
            return None
        u = None
        try:
            u = socket.create_connection((up["host"], up["port"]), timeout=timeout)
            u.settimeout(timeout)
            # 发送 HTTP CONNECT 请求给上游, 请求建立到目标的隧道
            authority_host = "[" + host + "]" if ":" in host else host
            req = ("CONNECT %s:%d HTTP/1.1\r\nHost: %s:%d\r\n"
                   "Proxy-Connection: keep-alive\r\n\r\n" % (
                       authority_host, port, authority_host, port)).encode("utf-8")
            u.sendall(req)
            # 读上游响应头
            resp = b""
            while b"\r\n\r\n" not in resp and len(resp) < 65536:
                # 精确读完响应头，保留与响应头同时到达的隧道数据。
                chunk = u.recv(1)
                if not chunk:
                    break
                resp += chunk
            # 上游代理可能需要认证 (407) 或直接拒绝 (403/502)
            head = resp.split(b"\r\n", 1)[0].decode("utf-8", errors="ignore")
            if " 200 " not in head and "200 connection" not in head.lower():
                self.last_error = "上游代理拒绝 CONNECT，请检查代理端口和认证设置"
                u.close()
                return None
            u.settimeout(120)
            return u
        except Exception as exc:
            self.last_error = "无法连接配置的上游 %s:%s (%s)" % (up.get("host"), up.get("port"), type(exc).__name__)
            if u is not None:
                try:
                    u.close()
                except Exception:
                    pass
            return None

    def _relay(self, a, b, first=b""):
        with self._connections_lock:
            self._connections.add(b)
        def count(direction, size):
            with self._connections_lock:
                if direction == "upload":
                    self.upload_bytes += size
                else:
                    self.download_bytes += size
        def error(message):
            self.last_error = message
        try:
            proxy_transport.relay(a, b, first, idle_timeout=self.relay_idle_timeout,
                                  on_bytes=count, on_error=error,
                                  should_stop=lambda: not self._running)
        finally:
            b.close()
            with self._connections_lock:
                self._connections.discard(b)


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
    """返回 [(接口名, IPv4, 掩码hex), ...] (排除回环/链路本地)。
    macOS 走 ifconfig; Windows 走 PowerShell Get-NetIPAddress
    (旧版只用 ifconfig, Windows 上恒返回 [] 导致 get_lan_ips 为空)。"""
    import re
    import subprocess
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        # Windows: PowerShell 拿 接口名/IP/前缀长度, 前缀长度转十六进制掩码
        try:
            kwargs = {"capture_output": True, "timeout": 8,
                      "creationflags": subprocess.CREATE_NO_WINDOW}
            out = subprocess.run([
                "powershell", "-NoProfile", "-Command",
                "Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | "
                "Where-Object { $_.IPAddress -ne '127.0.0.1' -and $_.IPAddress -notlike '169.254.*' } | "
                "ForEach-Object { '{0}|{1}|{2}' -f $_.InterfaceAlias, $_.IPAddress, $_.PrefixLength }"
            ], **kwargs).stdout.decode("utf-8", errors="replace")
        except Exception:
            return []
        rows = []
        for line in out.splitlines():
            parts = line.strip().split("|")
            if len(parts) == 3 and re.match(r"^\d+\.\d+\.\d+\.\d+$", parts[1]):
                try:
                    plen = max(0, min(32, int(parts[2])))
                    mask = (0xFFFFFFFF << (32 - plen)) & 0xFFFFFFFF
                    mask_hex = "%08x" % mask
                except Exception:
                    continue
                rows.append((parts[0], parts[1], mask_hex))
        return rows
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
    Windows: 复用 core.netinfo.get_gateway() 的 route print 解析(已处理 VPN/On-link);
    macOS: 先试 `route get default`; 若默认路由被 VPN/Clash(TUN) 抢走导致无 gateway,
    回退 netstat -rn 取第一条实体 IPv4 网关(跳过 link# 的虚拟默认路由)。
    """
    import re
    import subprocess
    try:
        from core import netinfo as _netinfo
        gw = _netinfo.get_gateway()
        if gw:
            return gw
    except Exception:
        pass
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
        if (_VIRT.match(iface) or "vpn" in iface.lower()
                or ip.startswith("198.18.")):
            continue                       # 纯虚拟/VPN隧道/假 IP, 直接丢弃
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
