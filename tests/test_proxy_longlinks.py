import socket
import threading
import time
import unittest
import http.client
from unittest.mock import patch
import shared_proxy
from proxy_transport import relay, forward_head


class LongLinkTests(unittest.TestCase):
    def test_upgrade_and_credentials(self):
        head = forward_head([b"GET http://example/ HTTP/1.1", b"Host: example",
                             b"Connection: keep-alive, Upgrade", b"Upgrade: websocket",
                             b"Proxy-Authorization: secret", b"X-Shared-Key: secret"],
                            b"GET", b"/")
        self.assertIn(b"Connection: Upgrade\r\n", head)
        self.assertIn(b"Upgrade: websocket", head)
        self.assertNotIn(b"secret", head)
        self.assertNotIn(b"Connection: close", head)

    def test_one_way_activity_does_not_timeout_other_direction(self):
        client, a = socket.socketpair()
        b, origin = socket.socketpair()
        errors = []
        thread = threading.Thread(target=relay, args=(a, b),
                                  kwargs=dict(idle_timeout=0.4, on_error=errors.append))
        thread.start()
        client.settimeout(2)
        try:
            for _ in range(12):
                origin.sendall(b"x")
                self.assertEqual(client.recv(1), b"x")
                time.sleep(0.06)
            origin.shutdown(socket.SHUT_WR)
            self.assertEqual(client.recv(1), b"")
            client.sendall(b"ack")
            client.shutdown(socket.SHUT_WR)
            origin.settimeout(2)
            self.assertEqual(origin.recv(3), b"ack")
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
        finally:
            for s in (client, a, b, origin):
                s.close()
            thread.join(2)

    def test_idle_timeout_has_safe_diagnostic(self):
        client, a = socket.socketpair()
        b, origin = socket.socketpair()
        errors = []
        try:
            relay(a, b, idle_timeout=0.03, on_error=errors.append)
            self.assertEqual(errors, ["传输空闲超时"])
        finally:
            for s in (client, a, b, origin):
                s.close()

    def test_stop_interrupts_idle_relay(self):
        client, a = socket.socketpair()
        b, origin = socket.socketpair()
        stopped = threading.Event()
        errors = []
        thread = threading.Thread(target=relay, args=(a, b), kwargs={
            "should_stop": stopped.is_set, "on_error": errors.append})
        thread.start()
        try:
            stopped.set()
            thread.join(2)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
        finally:
            for s in (client, a, b, origin):
                s.close()
            thread.join(2)

    def test_real_upgrade_bidirectional_exchange(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        received = []
        def server():
            conn, _ = listener.accept()
            with conn:
                conn.settimeout(3)
                header = b""
                while not header.endswith(b"\r\n\r\n"):
                    header += conn.recv(1)
                received.append(header)
                conn.sendall(b"HTTP/1.1 101 Switching Protocols\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\nHELLO")
                received.append(conn.recv(4))
                conn.sendall(b"PONG")
        worker = threading.Thread(target=server)
        worker.start()
        proxy = shared_proxy.SharedProxy(host="127.0.0.1", port=0, allowed=["127.0.0.1"])
        proxy.start()
        try:
            with socket.create_connection(("127.0.0.1", proxy.port), timeout=3) as client:
                client.sendall(("GET http://127.0.0.1:%d/socket HTTP/1.1\r\nHost: localhost\r\nConnection: Upgrade\r\nUpgrade: websocket\r\n\r\n" % listener.getsockname()[1]).encode())
                header = b""
                while not header.endswith(b"\r\n\r\n"):
                    header += client.recv(1)
                self.assertIn(b"101", header)
                def read_exact(n):
                    data = b""
                    while len(data) < n:
                        chunk = client.recv(n-len(data))
                        if not chunk:
                            break
                        data += chunk
                    return data
                self.assertEqual(read_exact(5), b"HELLO")
                client.sendall(b"PING")
                self.assertEqual(read_exact(4), b"PONG")
            worker.join(3)
            self.assertIn(b"Connection: Upgrade", received[0])
            self.assertEqual(received[1], b"PING")
        finally:
            proxy.stop()
            listener.close()
            worker.join(3)

    def test_ipv6_connect_authority(self):
        proxy = shared_proxy.SharedProxy(allowed=["127.0.0.1"])
        client, peer = socket.socketpair()
        peer.sendall(b"CONNECT [::1]:443 HTTP/1.1\r\n\r\n")
        try:
            with patch.object(proxy, "_connect", return_value=None) as connect:
                proxy._handle(client, "127.0.0.1")
                connect.assert_called_once_with("::1", 443)
        finally:
            client.close()
            peer.close()
