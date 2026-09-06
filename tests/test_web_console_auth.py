# -*- coding: utf-8 -*-
"""回归 v4.0.3 修复: 网络控制台鉴权失败时返引导页(不再 403 — 避免 iOS Safari 缓存"未接入互联网"误导文案)。

关键场景:
  1) 根路径无 key → KEY_ENTRY_HTML (200, text/html, Cache-Control: no-store)
  2) 根路径错误 key → KEY_ENTRY_HTML (不再 403)
  3) API 无 key → KEY_ENTRY_HTML(不再 403/JSON 错误)
  4) 引导页含 iOS Safari 缓存旁路提示
  5) /api/key 鉴权校验正确返 authed=true/false
"""
import time
import threading
import urllib.request
import urllib.error
import unittest

from web_console import WebConsole


def _start(state_fn, key="good-key", port=19091):
    c = WebConsole(state_fn=state_fn, key=key, port=port, host="127.0.0.1")
    c.start()
    time.sleep(0.2)
    return c


def _fake_state():
    return {
        "version": "4.0.3", "platform": "macOS", "hostname": "h",
        "lan_ips": ["10.52.188.32"], "daemon_running": True,
        "authed": True, "internet": True, "in_campus": True,
        "profile": "立达校园网", "mode": "ethernet", "ssid": "",
        "gateway": "10.52.191.254", "last_check": "now",
        "proxy_running": False,
    }


class TestWebConsoleAuth(unittest.TestCase):
    def setUp(self):
        self.port = 19091
        self.url = f"http://127.0.0.1:{self.port}"
        self.console = _start(_fake_state, key="good-key", port=self.port)

    def tearDown(self):
        self.console.stop()
        self.console = None

    # 1) 根路径无 key → 引导页 200 + Cache-Control
    def test_root_no_key_returns_entry_html(self):
        r = urllib.request.urlopen(self.url + "/", timeout=3)
        self.assertEqual(r.status, 200)
        body = r.read().decode("utf-8", "replace")
        self.assertIn("访问口令", body)
        self.assertNotIn("403", body)
        # 关键: 不再让 Safari 缓存失败状态
        self.assertIn("no-store", r.headers.get("Cache-Control", ""))
        self.assertEqual(r.headers.get("Pragma"), "no-cache")
        self.assertEqual(r.headers.get("Connection"), "close")

    # 2) 根路径错误 key → 引导页(不再 403)
    def test_root_wrong_key_returns_entry_html_not_403(self):
        try:
            r = urllib.request.urlopen(self.url + "/?key=wrong", timeout=3)
        except urllib.error.HTTPError as e:
            self.fail(f"错误 key 不应再 403, 实际 {e.code}")
        body = r.read().decode("utf-8", "replace")
        self.assertIn("访问口令", body)

    # 3) API 无 key → 引导页(不再 403/JSON)
    def test_api_no_key_returns_entry_html(self):
        r = urllib.request.urlopen(self.url + "/api/status", timeout=3)
        self.assertEqual(r.status, 200)
        body = r.read().decode("utf-8", "replace")
        # 必须返 HTML 引导页而不是 JSON {"error"}
        self.assertIn("访问口令", body)
        self.assertNotIn('"error"', body)

    # 4) 引导页文案含 Safari 缓存旁路提示
    def test_entry_page_has_ios_cache_tip(self):
        r = urllib.request.urlopen(self.url + "/", timeout=3)
        body = r.read().decode("utf-8", "replace")
        self.assertIn("iOS Safari", body)
        self.assertIn("未接入互联网", body)

    # 5) /api/key 鉴权接口正确
    def test_api_key_auth_query(self):
        # 错误 key → authed:false
        r = urllib.request.urlopen(self.url + "/api/key?key=wrong", timeout=3)
        self.assertEqual(r.status, 200)
        import json as _json
        self.assertEqual(_json.loads(r.read()), {"authed": False})
        # 正确 key → authed:true
        r2 = urllib.request.urlopen(self.url + "/api/key?key=good-key", timeout=3)
        self.assertEqual(_json.loads(r2.read()), {"authed": True})

    # 6) 正确 key 访问根路径 → 控制台 PAGE
    def test_root_with_correct_key_returns_console(self):
        r = urllib.request.urlopen(self.url + "/?key=good-key", timeout=3)
        self.assertEqual(r.status, 200)
        body = r.read().decode("utf-8", "replace")
        self.assertIn("校园网连接管家 · 控制台", body)
        self.assertIn("/api/status", body)  # 控制台 JS 拉 API

    # 7) 正确 key + 头鉴权也能过(控制台 JS 用 X-Console-Key)
    def test_api_with_header_auth(self):
        req = urllib.request.Request(
            self.url + "/api/status",
            headers={"X-Console-Key": "good-key"})
        r = urllib.request.urlopen(req, timeout=3)
        import json as _json
        self.assertEqual(r.status, 200)
        data = _json.loads(r.read())
        self.assertEqual(data["version"], "4.0.3")


if __name__ == "__main__":
    unittest.main()