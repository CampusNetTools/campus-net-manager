# -*- coding: utf-8 -*-
"""VPN 上游代理: 电脑当网关 + VPN 全透明转发 测试"""
import os
import sys
import socket
import threading
import time
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shared_proxy as sp


class VPNUpstreamTests(unittest.TestCase):
    """SharedProxy 配置 VPN 上游后, 设备流量应经上游 CONNECT 转发"""

    def _make_upstream(self):
        up = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        up.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        up.bind(("127.0.0.1", 0))
        up.listen(8)
        up.settimeout(0.5)
        port = up.getsockname()[1]
        state = {}
        def accept():
            while True:
                try:
                    c, _ = up.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                data = c.recv(4096)
                state["req"] = data.split(b"\r\n", 1)[0].decode(errors="replace")
                c.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                time.sleep(0.05)
                c.close()
        threading.Thread(target=accept, daemon=True).start()
        return up, port, state

    def test_connect_goes_through_upstream(self):
        up, up_port, state = self._make_upstream()
        time.sleep(0.2)
        proxy = sp.SharedProxy(port=0, host="127.0.0.1",
                               upstream_proxy={"host": "127.0.0.1", "port": up_port, "type": "http"},
                               shared_key="k")
        proxy.allowed.add("127.0.0.1")
        proxy.start()
        time.sleep(0.2)
        try:
            c = socket.create_connection(("127.0.0.1", proxy.port), timeout=5)
            c.sendall(b"CONNECT example.com:443 HTTP/1.1\r\nHost: example.com:443\r\n"
                      b"X-Shared-Key: k\r\n\r\n")
            resp = c.recv(200).decode(errors="replace")
            first = resp.split("\r\n", 1)[0]
            self.assertIn("200", first)
            # 上游收到的应是目标 CONNECT
            self.assertIn("example.com:443", state.get("req", ""))
            c.close()
        finally:
            proxy.stop()
            up.close()

    def test_no_upstream_direct(self):
        # 未配置上游时, _connect 不走上游
        proxy = sp.SharedProxy(port=0, host="127.0.0.1")
        self.assertIsNone(proxy.upstream_proxy)

    def test_connect_via_upstream_method(self):
        up, up_port, state = self._make_upstream()
        time.sleep(0.2)
        proxy = sp.SharedProxy(port=0, host="127.0.0.1",
                               upstream_proxy={"host": "127.0.0.1", "port": up_port, "type": "http"})
        s = proxy._connect_via_upstream("example.com", 443)
        self.assertIsNotNone(s)
        self.assertIn("example.com:443", state.get("req", ""))
        s.close()
        up.close()


if __name__ == "__main__":
    unittest.main()
