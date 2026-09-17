# -*- coding: utf-8 -*-
"""v5.5.0 「NAS 管家」测试。

覆盖:
  - core.nas_api 纯逻辑(大小格式化/路径拼接/条目解析/主机拆分/错误措辞)
  - 登录与列目录的请求封装(打桩 urlopen, 校验 token 传递与响应解析)
  - CGI 服务控制的请求封装(校验 op 字段与令牌)
  - GUI 源码断言(读文件而非导入, 避免无 tkinter 环境跑不了)
"""
import json
import os
import sys
import unittest
from urllib import request as urlrequest
from urllib.error import URLError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import nas_api

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeResponse:
    def __init__(self, body, status=200, headers=None):
        self._body = body.encode("utf-8") if isinstance(body, str) else body
        self.status = status
        self.headers = headers or {}

    def read(self, *_a):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *_a):
        return False


class FakeOpener:
    def __init__(self, body, recorder, status=200, headers=None):
        self.body, self.recorder, self.status = body, recorder, status
        self.headers = headers or {}

    def open(self, req, timeout=None):
        self.recorder.append(req)
        return FakeResponse(self.body, self.status, dict(self.headers))


def _patch_opener(case, body, status=200):
    recorder = []
    fake = FakeOpener(body, recorder, status)
    case._orig = urlrequest.build_opener
    urlrequest.build_opener = lambda *_a, **_k: fake
    case.addCleanup(setattr, urlrequest, "build_opener", case._orig)
    return recorder


class TestPureHelpers(unittest.TestCase):
    def test_human_size(self):
        self.assertEqual(nas_api.human_size(0), "0 B")
        self.assertEqual(nas_api.human_size(1023), "1023 B")
        self.assertEqual(nas_api.human_size(1024), "1.0 KB")
        self.assertEqual(nas_api.human_size(1536), "1.5 KB")
        self.assertEqual(nas_api.human_size(5 * 1024 * 1024 * 1024), "5.0 GB")
        self.assertEqual(nas_api.human_size(None), "-")
        self.assertEqual(nas_api.human_size("abc"), "-")
        self.assertEqual(nas_api.human_size(-5), "-")

    def test_join_path(self):
        self.assertEqual(nas_api.join_path("/nas", "volume3"), "/nas/volume3")
        self.assertEqual(nas_api.join_path("/nas/", "/volume3//x"), "/nas/volume3/x")
        self.assertEqual(nas_api.join_path("", ""), "/")
        self.assertEqual(nas_api.join_path("/nas", "a b/中文"), "/nas/a b/中文")

    def test_parent_path(self):
        self.assertEqual(nas_api.parent_path("/nas/volume3/x"), "/nas/volume3")
        self.assertEqual(nas_api.parent_path("/nas"), "/")
        self.assertEqual(nas_api.parent_path("/"), "/")
        self.assertEqual(nas_api.parent_path("nas/volume3"), "/nas")

    def test_error_hint_kinds(self):
        self.assertIn("启动服务", nas_api.error_hint(nas_api.NasApiError("x", kind="network")))
        self.assertIn("密码", nas_api.error_hint(nas_api.NasApiError("x", kind="auth")))
        self.assertIn("路径", nas_api.error_hint(nas_api.NasApiError("x", kind="notfound")))
        self.assertIn("令牌", nas_api.error_hint(nas_api.NasApiError("x", kind="rejected")))

    def test_split_host(self):
        self.assertEqual(nas_api.split_host("192.168.31.1:5244"), ("192.168.31.1", 5244))
        self.assertEqual(nas_api.split_host("http://100.64.0.1:5244"),
                         ("100.64.0.1", 5244))
        self.assertEqual(nas_api.split_host("192.168.31.1"),
                         ("192.168.31.1", nas_api.DEFAULT_ALIST_PORT))
        self.assertEqual(nas_api.split_host(""), ("", nas_api.DEFAULT_ALIST_PORT))

    def test_parse_entries(self):
        data = {"code": 200, "data": {"content": [
            {"name": "volume3", "size": 0, "is_dir": True, "modified": "2026-09-17"},
            {"name": "a.bin", "size": 10, "is_dir": False, "modified": "2026-09-17"},
            "bad-item",
        ]}}
        entries = nas_api.parse_entries(data)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["name"], "volume3")
        self.assertTrue(entries[0]["is_dir"])
        self.assertEqual(entries[1]["size"], 10)
        self.assertEqual(nas_api.parse_entries(None), [])
        self.assertEqual(nas_api.parse_entries({"code": 200}), [])

    def test_kind_from_message(self):
        self.assertEqual(nas_api._kind_from_message("user or password error"), "auth")
        self.assertEqual(nas_api._kind_from_message("failed get storage: /nas"), "notfound")
        self.assertEqual(nas_api._kind_from_message("other"), "unknown")


class TestLoginAndList(unittest.TestCase):
    def test_login_ok(self):
        recorder = _patch_opener(
            self, json.dumps({"code": 200, "message": "success",
                              "data": {"token": "tok-123"}}))
        token = nas_api.login("192.168.31.1:5244", "admin", "pw")
        self.assertEqual(token, "tok-123")
        req = recorder[0]
        self.assertTrue(req.full_url.endswith("/api/auth/login"))
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["username"], "admin")
        self.assertEqual(body["password"], "pw")

    def test_login_bad_password(self):
        _patch_opener(self, json.dumps({"code": 401, "message": "wrong password"}),
                      status=401)
        with self.assertRaises(nas_api.NasApiError) as ctx:
            nas_api.login("192.168.31.1:5244", "admin", "bad")
        self.assertEqual(ctx.exception.kind, "auth")

    def test_login_network_down(self):
        class DeadOpener:
            def open(self, *_a, **_k):
                raise URLError("conn refused")
        self._orig = urlrequest.build_opener
        urlrequest.build_opener = lambda *_a, **_k: DeadOpener()
        self.addCleanup(setattr, urlrequest, "build_opener", self._orig)
        with self.assertRaises(nas_api.NasApiError) as ctx:
            nas_api.login("192.168.31.1:5244", "admin", "pw")
        self.assertEqual(ctx.exception.kind, "network")

    def test_fs_list_sends_token_and_path(self):
        recorder = _patch_opener(
            self, json.dumps({"code": 200, "data": {"content": [
                {"name": "volume1", "is_dir": True, "size": 0}]}}))
        entries = nas_api.fs_list("192.168.31.1:5244", "tok", "/nas")
        self.assertEqual(entries[0]["name"], "volume1")
        req = recorder[0]
        self.assertEqual(req.get_header("Authorization"), "tok")
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["path"], "/nas")
        self.assertTrue(body["refresh"] is False)

    def test_fs_list_notfound(self):
        _patch_opener(self, json.dumps(
            {"code": 500, "message": "failed get storage: /nas"}), status=500)
        with self.assertRaises(nas_api.NasApiError) as ctx:
            nas_api.fs_list("192.168.31.1:5244", "tok", "/nas")
        self.assertEqual(ctx.exception.kind, "notfound")


class TestCgiControl(unittest.TestCase):
    def test_status_request(self):
        recorder = _patch_opener(
            self, json.dumps({"ok": True, "alist": 1, "rclone": 1,
                              "tailscale": 0, "web": "200", "ts_ip": ""}))
        data = nas_api.cgi_request("192.168.31.1", "8088", "token-x", "status")
        self.assertTrue(data["ok"])
        req = recorder[0]
        self.assertTrue(req.full_url.endswith("/cgi-bin/nas-api.sh"))
        body = json.loads(req.data.decode("utf-8"))
        self.assertEqual(body["token"], "token-x")
        self.assertEqual(body["op"], "status")

    def test_rejected(self):
        _patch_opener(self, json.dumps({"ok": False, "msg": "令牌错误"}))
        with self.assertRaises(nas_api.NasApiError) as ctx:
            nas_api.cgi_request("192.168.31.1", "8088", "bad", "status")
        self.assertEqual(ctx.exception.kind, "rejected")

    def test_badjson(self):
        _patch_opener(self, "<html>portal</html>")
        with self.assertRaises(nas_api.NasApiError) as ctx:
            nas_api.cgi_request("192.168.31.1", "8088", "t", "status")
        self.assertEqual(ctx.exception.kind, "badjson")


class TestGuiSourceAssertions(unittest.TestCase):
    """读源码断言(不 import gui): 线程安全模式与主界面入口。"""

    def test_nas_ui_has_no_direct_tkinter_in_workers(self):
        with open(os.path.join(ROOT, "gui", "nas_ui.py"), encoding="utf-8") as fh:
            src = fh.read()
        # 工作线程通道与泵必须存在(照抄 ClashNodesMixin 的模式)
        self.assertIn("def _nas_ui(self, fn)", src)
        self.assertIn("def _nas_pump(self)", src)
        self.assertIn("ui_queue.put(", src)
        # 不允许工作线程里直接 after(仅允许 _nas_ui 包装与 pump 内部)
        self.assertIn("win.after(80, self._nas_pump)", src)

    def test_app_has_nas_entry(self):
        with open(os.path.join(ROOT, "app_gui.py"), encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn("NasUiMixin", src)
        self.assertIn('self._fwin_open_legacy(\n                       "nas"', src)


if __name__ == "__main__":
    unittest.main()
