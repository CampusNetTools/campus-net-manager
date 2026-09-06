# -*- coding: utf-8 -*-
"""Web 控制台测试: 口令鉴权 / 状态与日志接口 / 设备管理 / 守护操作回调。"""
import json
import os
import sys
import unittest
import urllib.request
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import web_console  # noqa: E402


class _FakeProxy:
    def __init__(self):
        self.allowed = {"192.168.1.10", "192.168.1.11"}
        self.running = True


class _ServerFixture(unittest.TestCase):
    KEY = "testkey123"

    def setUp(self):
        self.actions = []
        self.proxy = _FakeProxy()
        self.console = web_console.WebConsole(
            state_fn=lambda: {"version": "3.1.0", "daemon_running": True,
                              "authed": True, "internet": True,
                              "in_campus": True, "profile": "立达校园网",
                              "mode": "wifi", "ssid": "LIDA-UNIVERSITY",
                              "gateway": "10.0.0.1", "last_check": "2026-09-06 01:00:00",
                              "proxy_running": True, "platform": "macOS"},
            key=self.KEY, port=0, host="127.0.0.1",
            proxy=self.proxy,
            action_fn=lambda name: self.actions.append(name) or "已切换")
        self.console.start()
        self.port = self.console._server.server_address[1]

    def tearDown(self):
        self.console.stop()

    def _get(self, path, key=None):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        req = urllib.request.Request(url)
        if key:
            req.add_header("X-Console-Key", key)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req, timeout=5)

    def _post(self, path, body=None, key=None):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        data = json.dumps(body or {}).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        if key:
            req.add_header("X-Console-Key", key)
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(req, timeout=5)


class AuthTests(_ServerFixture):
    # v4.0.3 修复: iOS Safari 对 403 会缓存"未接入互联网"误导文案.
    # 鉴权失败改为返 200 KEY_ENTRY_HTML, 引导用户重新输口令.
    def test_no_key_returns_entry_html(self):
        resp = self._get("/")
        self.assertEqual(resp.status, 200)
        html = resp.read().decode("utf-8")
        self.assertIn("访问口令", html)
        self.assertIn("no-store", resp.headers.get("Cache-Control", ""))

    def test_wrong_key_returns_entry_html(self):
        resp = self._get("/api/status", key="wrong")
        self.assertEqual(resp.status, 200)
        html = resp.read().decode("utf-8")
        self.assertIn("访问口令", html)
        self.assertNotIn('"error"', html)

    # /api/key 是鉴权查询接口, 永远返 JSON(供引导页实时校验)
    def test_api_key_query(self):
        bad = json.loads(self._get("/api/key", key="wrong").read().decode("utf-8"))
        self.assertEqual(bad, {"authed": False})
        ok = json.loads(self._get("/api/key", key=self.KEY).read().decode("utf-8"))
        self.assertEqual(ok, {"authed": True})

    def test_query_key_ok(self):
        resp = self._get("/?key=%s" % self.KEY)
        html = resp.read().decode("utf-8")
        self.assertIn("控制台", html)

    def test_header_key_ok(self):
        resp = self._get("/api/status", key=self.KEY)
        self.assertEqual(resp.status, 200)


class ApiTests(_ServerFixture):
    def test_status_json(self):
        data = json.loads(self._get("/api/status", key=self.KEY).read().decode("utf-8"))
        self.assertEqual(data["version"], "3.1.0")
        self.assertTrue(data["daemon_running"])
        self.assertEqual(data["profile"], "立达校园网")

    def test_logs(self):
        data = json.loads(self._get("/api/logs?n=10", key=self.KEY).read().decode("utf-8"))
        self.assertIn("lines", data)

    def test_outages(self):
        data = json.loads(self._get("/api/outages", key=self.KEY).read().decode("utf-8"))
        self.assertIn("outages", data)

    def test_devices_list(self):
        data = json.loads(self._get("/api/devices", key=self.KEY).read().decode("utf-8"))
        self.assertEqual(data["allowed"], ["192.168.1.10", "192.168.1.11"])
        self.assertTrue(data["proxy_running"])

    def test_devices_remove(self):
        data = json.loads(self._post("/api/devices/remove",
                                     {"ip": "192.168.1.10"}, key=self.KEY).read().decode("utf-8"))
        self.assertTrue(data["ok"])
        self.assertNotIn("192.168.1.10", self.proxy.allowed)

    def test_devices_remove_missing(self):
        data = json.loads(self._post("/api/devices/remove",
                                     {"ip": "1.2.3.4"}, key=self.KEY).read().decode("utf-8"))
        self.assertFalse(data["ok"])

    def test_daemon_toggle(self):
        data = json.loads(self._post("/api/daemon/toggle", key=self.KEY).read().decode("utf-8"))
        self.assertTrue(data["ok"])
        self.assertEqual(self.actions, ["toggle_daemon"])

    # v4.0.3 修复: POST 鉴权失败返 200 引导页(不再 403)
    def test_post_requires_key_returns_entry_html(self):
        resp = self._post("/api/daemon/toggle")
        self.assertEqual(resp.status, 200)
        html = resp.read().decode("utf-8")
        self.assertIn("访问口令", html)


if __name__ == "__main__":
    unittest.main()
