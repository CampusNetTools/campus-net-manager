# -*- coding: utf-8 -*-
"""回归 shared_proxy loopback URL 识别（v4.0.3 增强）:
iPhone Safari 通过 HTTP 代理访问 http://<电脑自己IP>/... 时, 不能代理到自己:80
触发 502/Safari 误判"未接入互联网". 要识别 host 是代理自己, 视同相对路径或转发到本地服务。
"""
import os
import sys
import socket
import threading
import time
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shared_proxy  # noqa: E402


def _start(port=19092):
    """启动代理 + 假上游服务(模拟电脑自己的 8081 控制台)"""
    # 假控制台服务: 优先 8081, 占用时退到 18081
    fake_port = 8081
    for try_port in (8081, 18081, 19081):
        try:
            fake_console = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            fake_console.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            fake_console.bind(("127.0.0.1", try_port))
            fake_port = try_port
            break
        except OSError:
            try:
                fake_console.close()
            except Exception:
                pass
            continue
    fake_console.listen(8)
    fake_console.settimeout(0.5)
    body = b"<html>FAKE CONSOLE OK</html>"
    responses = {b"/": b"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\n"
                          b"Cache-Control: no-store\r\nContent-Length: " +
                 str(len(body)).encode() + b"\r\n\r\n" + body}

    def serve():
        while True:
            try:
                c, _ = fake_console.accept()
            except (socket.timeout, OSError):
                return
            try:
                d = b""
                while b"\r\n\r\n" not in d and len(d) < 4096:
                    chunk = c.recv(1024)
                    if not chunk:
                        break
                    d += chunk
                # 解析 GET 路径 (忽略 ?query)
                line = d.split(b"\r\n", 1)[0]
                full = line.split(b" ", 2)[1]
                path = full.split(b"?", 1)[0]
                resp = responses.get(path)
                if not resp:
                    resp = (b"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n")
                c.sendall(resp)
            except Exception:
                pass
            finally:
                c.close()

    t = threading.Thread(target=serve, daemon=True)
    t.start()

    # 启动 shared_proxy
    sp = shared_proxy.SharedProxy(port=port, host="127.0.0.1")
    sp._my_ips = {"127.0.0.1", "192.168.3.1", "10.52.188.32"}  # 模拟电脑接口
    sp.start()
    time.sleep(0.2)
    return sp, fake_console


class TestLoopbackURL(unittest.TestCase):
    sp = None
    fake = None
    fake_port = 0

    @classmethod
    def setUpClass(cls):
        cls.sp, cls.fake = _start(port=19092)
        cls.fake_port = cls.fake.getsockname()[1]

    @classmethod
    def tearDownClass(cls):
        cls.sp.stop()
        try:
            cls.fake.close()
        except Exception:
            pass

    def _request(self, target_line):
        """直接发 HTTP 代理请求行(模拟 iPhone Safari)"""
        s = socket.create_connection(("127.0.0.1", 19092), timeout=3)
        req = target_line + "\r\nHost: x\r\nUser-Agent: Mozilla/5.0 iPhone\r\n\r\n"
        s.sendall(req.encode("ascii"))
        data = b""
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
                if len(data) > 65536:
                    break
        except Exception:
            pass
        s.close()
        return data

    # 1) http://192.168.3.1/ → 重写为 / → 引导页(返回的是引导页 HTML, 含 'setup.mobileconfig')
    def test_loopback_root_returns_setup_page(self):
        resp = self._request("GET http://192.168.3.1/ HTTP/1.1")
        self.assertIn(b"200 OK", resp)
        body = resp.split(b"\r\n\r\n", 1)[1]
        # 引导页 HTML 含 '/setup.mobileconfig' 下载按钮链接
        self.assertIn(b"setup.mobileconfig", body,
                      f"应该返回引导页, 实际前120字节: {body[:120]!r}")

    # 2) http://192.168.3.1/proxy.pac → 走 PAC 分支(返回 application/x-ns-proxy-autoconfig)
    def test_loopback_proxy_pac(self):
        resp = self._request("GET http://192.168.3.1/proxy.pac HTTP/1.1")
        self.assertIn(b"200 OK", resp)
        self.assertIn(b"application/x-ns-proxy-autoconfig", resp)

    # 3) http://10.52.188.32:<fake_port>/?key=xxx → 代理到 127.0.0.1:<fake_port>(模拟控制台)
    def test_loopback_other_port_proxied_locally(self):
        port = self.fake_port
        resp = self._request(f"GET http://10.52.188.32:{port}/?key=abc HTTP/1.1")
        self.assertIn(b"200 OK", resp)
        self.assertIn(b"FAKE CONSOLE OK", resp)

    # 4) http://baidu.com/ → 外网 host, 不识别为 loopback, 走原代理(应连不上, 但不应是引导页)
    def test_external_host_not_loopback(self):
        resp = self._request("GET http://baidu.com/ HTTP/1.1")
        # 连不上 baidu.com 应该返 502 或空(无引导页内容)
        self.assertNotIn(b"FAKE CONSOLE OK", resp)
        self.assertNotIn(b"application/x-ns-proxy-autoconfig", resp)

    # 5) 直接相对路径 / 也仍然走引导页(回归不破)
    def test_relative_root_still_works(self):
        resp = self._request("GET / HTTP/1.1")
        self.assertIn(b"200 OK", resp)


if __name__ == "__main__":
    unittest.main()