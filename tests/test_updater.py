# -*- coding: utf-8 -*-
"""自动更新模块测试: 版本比较 / 资产挑选 / 检查与下载(注入假网络) / 自替换脚本 / 节流跳过。"""
import datetime
import io
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import updater  # noqa: E402


class _FakeResp:
    def __init__(self, payload, chunksize=7):
        if isinstance(payload, (dict, list)):
            self._data = json.dumps(payload).encode("utf-8")
        else:
            self._data = payload
        self._pos = 0
        self._chunksize = chunksize
        self.headers = {"Content-Length": str(len(self._data))}

    def read(self, n=-1):
        if n is None or n < 0:
            n = len(self._data) - self._pos
        chunk = self._data[self._pos:self._pos + n]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeOpener:
    def __init__(self, payload):
        self.payload = payload
        self.requests = []

    def open(self, req, timeout=0):
        self.requests.append(req)
        return _FakeResp(self.payload)


RELEASE = {
    "tag_name": "v9.9.9",
    "body": "- 新功能A\n- 修复B",
    "html_url": "https://github.com/x/releases/v9.9.9",
    "assets": [
        {"name": "校园网连接管家-macOS-arm64-v9.9.9.zip",
         "browser_download_url": "https://x/mac.zip", "size": 100},
        {"name": "CampusNetManager_v9.9.9_win64.exe",
         "browser_download_url": "https://x/win.exe", "size": 200},
    ],
}


class VersionTests(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(updater.parse_version("v3.0.0"), (3, 0, 0))
        self.assertEqual(updater.parse_version("2.10.1"), (2, 10, 1))
        self.assertIsNone(updater.parse_version("abc"))

    def test_is_newer(self):
        self.assertTrue(updater.is_newer("v3.0.1", "3.0.0"))
        self.assertTrue(updater.is_newer("v3.1.0", "3.0.9"))
        self.assertFalse(updater.is_newer("v3.0.0", "3.0.0"))
        self.assertFalse(updater.is_newer("v2.9.9", "3.0.0"))
        self.assertFalse(updater.is_newer("bad", "3.0.0"))


class CheckTests(unittest.TestCase):
    def test_check_has_update(self):
        info = updater.check_for_update("3.0.0", opener=_FakeOpener(RELEASE))
        self.assertIsNotNone(info)
        self.assertEqual(info["tag"], "v9.9.9")
        self.assertEqual(info["version"], (9, 9, 9))
        self.assertIn("新功能A", info["notes"])
        self.assertEqual(len(info["assets"]), 2)

    def test_check_already_latest(self):
        old = dict(RELEASE, tag_name="v1.0.0")
        self.assertIsNone(updater.check_for_update("3.0.0", opener=_FakeOpener(old)))

    def test_check_network_failure(self):
        class BadOpener:
            def open(self, req, timeout=0):
                raise OSError("网络不通")
        self.assertIsNone(updater.check_for_update("3.0.0", opener=BadOpener()))


class AssetTests(unittest.TestCase):
    def test_pick_macos(self):
        a = updater.pick_asset(RELEASE["assets"], "macos")
        self.assertTrue(a["name"].endswith(".zip"))

    def test_pick_windows(self):
        a = updater.pick_asset(RELEASE["assets"], "windows")
        self.assertTrue(a["name"].endswith(".exe"))

    def test_pick_none(self):
        self.assertIsNone(updater.pick_asset([], "macos"))
        self.assertIsNone(updater.pick_asset([{"name": "readme.txt"}], "windows"))


class DownloadTests(unittest.TestCase):
    def test_download_with_progress(self):
        payload = b"x" * 100
        seen = []
        with tempfile.TemporaryDirectory() as td:
            dest = os.path.join(td, "a.bin")
            updater.download("https://x/a.bin", dest,
                             progress=lambda d, t: seen.append((d, t)),
                             opener=_FakeOpener(payload))
            self.assertEqual(open(dest, "rb").read(), payload)
        self.assertTrue(seen)
        self.assertEqual(seen[-1], (100, 100))


class ScriptTests(unittest.TestCase):
    def test_macos_script(self):
        s = updater.macos_apply_script("/Applications/校园网连接管家.app",
                                       "/tmp/new/校园网连接管家.app", pid=1234)
        self.assertIn("kill -0 1234", s)
        self.assertIn('rm -rf "/Applications/校园网连接管家.app"', s)
        self.assertIn("com.apple.quarantine", s)

    def test_windows_script(self):
        s = updater.windows_apply_script(r"C:\Apps\CampusNetManager.exe",
                                         r"C:\Apps\CampusNetManager_new.exe", pid=5678)
        self.assertIn("PID eq 5678", s)
        self.assertIn("move /y", s)

    def test_windows_script_renames_to_cn_and_cleans_stale(self):
        """更新后统一重命名为中文规范名, 并删除旧英文/带版本号 exe。"""
        s = updater.windows_apply_script(
            r"C:\Downloads\CampusNetManager-v5.1.0-win64.exe",
            r"C:\Downloads\校园网连接管家_new.exe", pid=5678,
            stale_exe=[r"C:\Downloads\CampusNetManager.exe"],
            final_exe=r"C:\Downloads\校园网连接管家.exe")
        # 新文件落到中文规范名
        self.assertIn('move /y "C:\\Downloads\\校园网连接管家_new.exe" '
                      '"C:\\Downloads\\校园网连接管家.exe"', s)
        # 旧 exe 被删除(带版本号的当前 exe + 无版本号旧英文 exe)
        self.assertIn('del /f /q "C:\\Downloads\\CampusNetManager.exe"', s)
        self.assertIn('del /f /q "C:\\Downloads\\CampusNetManager-v5.1.0-win64.exe"', s)
        # 启动中文名
        self.assertIn('start "" "C:\\Downloads\\校园网连接管家.exe"', s)

    def test_windows_script_no_final_exe_keeps_original(self):
        """缺省 final_exe 时仍覆盖原路径(向后兼容, 不误删自身)。"""
        s = updater.windows_apply_script(r"C:\Apps\CampusNetManager.exe",
                                         r"C:\Apps\CampusNetManager_new.exe", pid=5678)
        self.assertIn('move /y "C:\\Apps\\CampusNetManager_new.exe" '
                      '"C:\\Apps\\CampusNetManager.exe"', s)
        # 不能把刚替换好的目标 exe 也写进删除名单
        self.assertNotIn('del /f /q "C:\\Apps\\CampusNetManager.exe"', s)

    def test_canonical_asset_matches_cn_name(self):
        self.assertTrue(updater._CANONICAL_ASSET.match("校园网连接管家-v5.2.1-win64.exe"))
        self.assertTrue(updater._CANONICAL_ASSET.match("校园网连接管家-macOS-arm64-v5.2.1.zip"))
        # 旧英文连字符名仍兼容
        self.assertTrue(updater._CANONICAL_ASSET.match("CampusNetManager-v5.2.0-win64.exe"))
        # 更旧的下划线命名是次选(非规范), 保持向后兼容的优先级语义
        self.assertIsNone(updater._CANONICAL_ASSET.match("CampusNetManager_v5.1.0_win64.exe"))

    def test_pick_asset_cn_windows(self):
        assets = [
            {"name": "校园网连接管家-v9.9.9-win64.exe",
             "browser_download_url": "https://x/cn.exe", "size": 100},
            {"name": "CampusNetManager_v9.9.8_win64.exe",
             "browser_download_url": "https://x/old.exe", "size": 90},
        ]
        a = updater.pick_asset(assets, "windows")
        # 中文规范名优先于旧下划线英文名
        self.assertEqual(a["name"], "校园网连接管家-v9.9.9-win64.exe")

    def test_find_stale_executables(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            current = os.path.join(td, "校园网连接管家.exe")
            old_en = os.path.join(td, "CampusNetManager.exe")
            old_ver = os.path.join(td, "CampusNetManager-v5.1.0-win64.exe")
            other = os.path.join(td, "readme.txt")
            for p in (current, old_en, old_ver, other):
                open(p, "wb").close()
            stale = updater.find_stale_executables(td, current)
            self.assertIn(old_en, stale)
            self.assertIn(old_ver, stale)
            # 不包含当前运行 exe 与无关文件
            self.assertNotIn(current, stale)
            self.assertNotIn(other, stale)

    @unittest.skipIf(os.name == "nt", "Windows 无可执行位语义")
    def test_write_script_executable(self):
        path = updater.write_apply_script("#!/bin/bash\necho hi\n", ".sh")
        try:
            self.assertTrue(os.stat(path).st_mode & 0o111)
        finally:
            os.unlink(path)


class ThrottleTests(unittest.TestCase):
    def test_first_check_allowed(self):
        self.assertTrue(updater.should_auto_check({}))

    def test_throttled(self):
        now = datetime.datetime.now()
        prefs = {"update_last_check": now.isoformat()}
        self.assertFalse(updater.should_auto_check(prefs, now=now))
        old = (now - datetime.timedelta(hours=21)).isoformat()
        self.assertTrue(updater.should_auto_check({"update_last_check": old}, now=now))

    def test_skip_version(self):
        self.assertFalse(updater.should_notify({"update_skip_version": "v9.9.9"}, "v9.9.9"))
        self.assertTrue(updater.should_notify({"update_skip_version": "v9.9.8"}, "v9.9.9"))

    def test_mark_checked(self):
        prefs = updater.mark_checked({})
        self.assertTrue(prefs["update_last_check"])


if __name__ == "__main__":
    unittest.main()
