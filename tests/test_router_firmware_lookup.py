# -*- coding: utf-8 -*-
"""v4.0.3 路由器方案核心能力测试: 固件查询 / 下载 / SHA256 / 中继指引。"""
import hashlib
import http.server
import os
import tempfile
import threading
import unittest

import keepalive_core as core
from core import router as core_router


class TestRouterFirmwareUrls(unittest.TestCase):
    """lookup_firmware_urls 覆盖内置常见品牌 + 未识别品牌 + 空格处理。"""

    def test_known_brands_have_entries(self):
        for brand in ("华为", "小米", "TP-LINK", "水星", "迅捷(FAST)",
                      "腾达", "华硕", "网件", "中兴", "360",
                      "D-Link", "斐讯"):
            res = core_router.lookup_firmware_urls(brand, "model-x", "v1")
            self.assertEqual(res["brand"], brand)
            self.assertTrue(res["openwrt_toh"].startswith("https://"))
            self.assertTrue(res["vendor_url"].startswith("https://"))
            self.assertIn("note", res)
            self.assertGreater(len(res["note"]), 0)

    def test_asus_has_merlin(self):
        res = core_router.lookup_firmware_urls("华硕", "RT-AX86U")
        self.assertIn("merlin_url", res)
        self.assertIn("merlin.net", res["merlin_url"])

    def test_unknown_brand_falls_back(self):
        res = core_router.lookup_firmware_urls("", "x", "v1")
        self.assertEqual(res["brand"], "")
        self.assertIn("尚未识别", res["note"])

        res2 = core_router.lookup_firmware_urls("未听说过牌", "x", "v1")
        self.assertEqual(res2["brand"], "未听说过牌")
        self.assertTrue(res2["openwrt_toh"].startswith("https://"))

    def test_model_revision_passed_through(self):
        res = core_router.lookup_firmware_urls("小米", "AX3600", "Rev 1.0")
        self.assertEqual(res["model"], "AX3600")
        self.assertEqual(res["revision"], "Rev 1.0")


class TestSha256(unittest.TestCase):
    """sha256_of_file 准确计算. (用于刷机前校验固件包完整)"""

    def test_sha256_known_content(self):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        tmp.write(b"hello campusnet\n" * 100)
        tmp.close()
        try:
            expect = hashlib.sha256(b"hello campusnet\n" * 100).hexdigest()
            self.assertEqual(core_router.sha256_of_file(tmp.name), expect)
        finally:
            os.remove(tmp.name)

    def test_sha256_missing_file(self):
        self.assertEqual(core_router.sha256_of_file("/nonexistent/path/abc"), "")


class TestDownloadFirmware(unittest.TestCase):
    """download_firmware: 本地 HTTP server 验证下载 + 进度回调 + SHA256 校验。"""

    def setUp(self):
        self.body = b"A" * 1024 + b"fw-data-here" * 17
        self.sha = hashlib.sha256(self.body).hexdigest()

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self_inner):
                self_inner.send_response(200)
                self_inner.send_header("Content-Type", "application/octet-stream")
                self_inner.send_header("Content-Length", str(len(self.body)))
                self_inner.end_headers()
                self_inner.wfile.write(self.body)

        self.server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=2)

    def test_download_ok_with_sha(self):
        tmpdir = tempfile.mkdtemp(prefix="cnm_fw_")
        save_path = os.path.join(tmpdir, "test.bin")
        progress = []
        ok, msg, sha = core_router.download_firmware(
            "http://127.0.0.1:%d/firmware.bin" % self.port,
            save_path, expected_sha256=self.sha,
            progress_cb=lambda d, t: progress.append((d, t)))
        self.assertTrue(ok, msg)
        self.assertIn("下载完成", msg)
        self.assertEqual(sha, self.sha)
        self.assertEqual(progress[-1][0], len(self.body))
        self.assertTrue(os.path.exists(save_path))
        os.remove(save_path)
        os.rmdir(tmpdir)

    def test_download_sha_mismatch_rejected(self):
        tmpdir = tempfile.mkdtemp(prefix="cnm_fw_")
        save_path = os.path.join(tmpdir, "bad.bin")
        ok, msg, sha = core_router.download_firmware(
            "http://127.0.0.1:%d/firmware.bin" % self.port,
            save_path, expected_sha256="0" * 64)
        self.assertFalse(ok)
        self.assertIn("SHA256", msg)
        self.assertFalse(os.path.exists(save_path))  # 不完整文件被删除
        os.rmdir(tmpdir)

    def test_download_bad_url_returns_error(self):
        tmpdir = tempfile.mkdtemp(prefix="cnm_fw_")
        save_path = os.path.join(tmpdir, "x.bin")
        ok, msg, sha = core_router.download_firmware(
            "ftp://not-allowed/", save_path)
        self.assertFalse(ok)
        self.assertIn("URL 非法", msg)
        os.rmdir(tmpdir)


class TestRouterGuide(unittest.TestCase):
    """router_guide 返回品牌+管理页+分步路径, 不会抛错. (即使品牌未识别也返通用模板)"""

    def test_returns_triple(self):
        result = core_router.router_guide()
        # brand 可能是 None（未识别）或字符串, 但 guide / gw 必为字符串
        brand, gw, guide = result
        self.assertIn(type(brand), (str, type(None)))
        self.assertIsInstance(gw, str)
        self.assertIsInstance(guide, str)
        self.assertGreater(len(guide), 10)


if __name__ == "__main__":
    unittest.main()
