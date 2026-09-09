"""真实本地 socket 回归：不访问校园账号或外部网络。"""
import concurrent.futures
import socket
import threading
import time
import unittest
from unittest.mock import patch
import shared_proxy


class TransportTests(unittest.TestCase):
    def test_console_auth_through_proxy_preserves_query(self):
        import http.client
        import json
        from web_console import WebConsole
        console = WebConsole(state_fn=lambda: {}, key="test+key", host="127.0.0.1", port=0)
        console.start()
        proxy = shared_proxy.SharedProxy(host="127.0.0.1", port=0,
                                        upstream_proxy={"host": "127.0.0.1", "port": 1})
        proxy.start()
        try:
            for key, expected in (("test%2Bkey", True), ("incorrect", False)):
                client = http.client.HTTPConnection("127.0.0.1", proxy.port, timeout=3)
                try:
                    client.request("GET", "http://127.0.0.1:%d/api/key?key=%s" %
                                   (console._server.server_address[1], key))
                    response = client.getresponse()
                    self.assertEqual(json.loads(response.read())["authed"], expected)
                finally:
                    client.close()
        finally:
            proxy.stop()
            console.stop()

    def test_dead_upstream_is_reported(self):
        with patch.object(socket, "create_connection", side_effect=ConnectionRefusedError):
            with self.assertRaisesRegex(ValueError, "无法连接"):
                shared_proxy.validate_upstream({"host": "127.0.0.1", "port": 7890})

    def test_parallel_phone_requests_only_ask_once(self):
        started = threading.Event()
        release = threading.Event()
        def ask(ip):
            started.set()
            release.wait(2)
            return True
        with patch.object(shared_proxy.SharedProxy, "_collect_my_ips", return_value=set()):
            proxy = shared_proxy.SharedProxy(on_ask=ask)
        with patch.object(proxy, "on_ask", wraps=ask) as callback:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                jobs = [pool.submit(proxy._check_allow, "192.0.2.2") for _ in range(8)]
                self.assertTrue(started.wait(1))
                release.set()
                self.assertTrue(all(job.result(3) for job in jobs))
            self.assertEqual(callback.call_count, 1)

    def test_upstream_connect_preserves_coalesced_data(self):
        client, server = socket.socketpair()
        def respond():
            server.recv(4096)
            server.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\nBANNER")
        thread = threading.Thread(target=respond)
        thread.start()
        with patch.object(shared_proxy.SharedProxy, "_collect_my_ips", return_value=set()):
            proxy = shared_proxy.SharedProxy(upstream_proxy={"host": "localhost", "port": 1})
        try:
            with patch.object(socket, "create_connection", return_value=client):
                upstream = proxy._connect("example.com", 443)
            self.assertIsNotNone(upstream)
            self.assertEqual(upstream.recv(6), b"BANNER")
        finally:
            client.close()
            server.close()
            thread.join(2)

    def test_connect_bulk_transfer_and_half_close(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        payload = b"x" * (2 * 1024 * 1024)
        def respond():
            conn, _ = listener.accept()
            with conn:
                while conn.recv(4096):
                    pass
                conn.sendall(payload)
        thread = threading.Thread(target=respond, daemon=True)
        thread.start()
        with patch.object(shared_proxy.SharedProxy, "_collect_my_ips", return_value=set()):
            proxy = shared_proxy.SharedProxy(host="127.0.0.1", port=0, allowed=["127.0.0.1"])
        proxy.start()
        try:
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=5) as client:
                client.sendall(("CONNECT 127.0.0.1:%d HTTP/1.1\r\n\r\n" % listener.getsockname()[1]).encode())
                head = b""
                while not head.endswith(b"\r\n\r\n"):
                    head += client.recv(1)
                self.assertIn(b"200", head)
                client.shutdown(socket.SHUT_WR)
                received = bytearray()
                while True:
                    chunk = client.recv(65536)
                    if not chunk:
                        break
                    received.extend(chunk)
                self.assertEqual(received, payload)
        finally:
            proxy.stop()
            listener.close()
            thread.join(2)
