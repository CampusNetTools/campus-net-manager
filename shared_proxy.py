# -*- coding: utf-8 -*-
"""
shared_proxy.py - 局域网 HTTP 代理隧道服务
让手机/平板等设备借本机网络访问外网 (设备无需认证/无需装App,
只需在 Wi-Fi 设置里把代理指向本机 IP:端口)。
支持: HTTP CONNECT 隧道(HTTPS) + 绝对URL转发(HTTP)
"""
import socket
import threading


class SharedProxy:
    """轻量 HTTP 代理: 监听局域网端口, 转发 TCP 流量。
    支持访问控制: allowed 集合 + on_ask 回调(新设备询问, 防开放代理被滥用)"""

    def __init__(self, port=8080, host="0.0.0.0", allowed=None, on_ask=None):
        self.port = port
        self.host = host
        self.allowed = set(allowed or [])   # 已授权客户端 IP
        self.on_ask = on_ask                # callable(ip) -> bool 新设备是否放行
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

    # ---------- 内部 ----------
    def _accept_loop(self):
        while self._running:
            try:
                client, addr = self._listener.accept()
                if not self._check_allow(addr[0]):
                    try:
                        client.sendall(b"HTTP/1.1 403 Forbidden\r\n\r\n")
                        client.close()
                    except Exception:
                        pass
                    continue
                t = threading.Thread(target=self._handle, args=(client,), daemon=True)
                t.start()
                self._threads.append(t)
            except socket.timeout:
                continue
            except Exception:
                break

    def _handle(self, client):
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
        try:
            u = socket.create_connection((host, port), timeout=timeout)
            u.settimeout(20)
            return u
        except Exception:
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


def get_lan_ips():
    """返回本机局域网 IPv4 列表 (供其他设备填写代理服务器)"""
    ips = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = info[4][0]
            if not ip.startswith(("127.", "169.254.")) and ip not in ips:
                ips.append(ip)
    except Exception:
        pass
    return ips
