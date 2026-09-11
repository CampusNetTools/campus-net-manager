# -*- coding: utf-8 -*-
"""v5.1.2 修复批次回归测试。

覆盖(每条对应一处真实问题):
- ensure_lida_profile: 不再改写 v5 用户自建的同名"校园网"档案; 迁移只做一次
- ensure_lida_profile: 旧版遗留档案仍能原位升级(保留账号密码)
- 密码不再明文落盘(Windows DPAPI / macOS 钥匙串), 导出不含密文
- auth._authed_from_page: 不再只认死 <title>注销页</title>
- auth.auth_reachable: 防抖 + debounce=False 直通
- auth.ensure_login: 认证服务器不可达时快速失败, 不阻塞 100s+
- updater: SHA256 解析/校验/资产挑选(规范命名优先)
- web_console: 短时令牌、常量时间比较、非 ASCII 口令不 500
- matching.profiles_snapshot: 遍历前浅拷贝, 抗并发改列表
- router._iface_clients: Windows 不再调用无效的 Get-NetIPStatistics
- router.download_firmware: timeout 参数真正生效
- keepalive_core.acquire_lock: 用启动时刻指纹识别 PID 复用
"""
import inspect
import json
import os
import sys
import tempfile
import time
import unittest
import urllib.request
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import keepalive_core as core  # noqa: E402
import updater  # noqa: E402
from core import auth, common, config, matching, router, sysutils  # noqa: E402


class LidaProfileMigrationTests(unittest.TestCase):
    """档案迁移: 只碰真正的旧版遗留档案, 且只碰一次。"""

    def test_new_style_same_name_profile_is_not_rewritten(self):
        # v5 用户自建的"校园网"档案(带 profile_type)不该被改名/绑 SSID
        cfg = {"profiles": [{"name": "校园网", "profile_type": "campus", "ssid": "",
                             "username": "u", "password": "p",
                             "auth_url": core.DEFAULT_AUTH_URL, "interval": 60}],
               "active_profile": "校园网"}
        self.assertTrue(core.ensure_lida_profile(cfg))
        self.assertEqual(len(cfg["profiles"]), 2)
        self.assertEqual(cfg["profiles"][0]["name"], core.LIDA_PROFILE_NAME)
        # 用户自建档案原样保留
        self.assertEqual(cfg["profiles"][1]["name"], "校园网")
        self.assertEqual(cfg["profiles"][1]["ssid"], "")
        self.assertEqual(cfg["active_profile"], "校园网")

    def test_migration_runs_only_once(self):
        cfg = {"profiles": [{"name": "校园网", "ssid": "", "username": "u",
                             "password": "p", "auth_url": core.DEFAULT_AUTH_URL,
                             "interval": 300}],
               "active_profile": "校园网"}
        self.assertTrue(core.ensure_lida_profile(cfg))
        self.assertTrue(cfg["lida_migrated"])
        self.assertEqual(cfg["profiles"][0]["preset"], core.LIDA_PROFILE_ID)
        # 用户把名字改回去 -> 因为标记已置位, 不会被再次改写
        cfg["profiles"][0]["name"] = "校园网"
        self.assertFalse(core.ensure_lida_profile(cfg))
        self.assertEqual(cfg["profiles"][0]["name"], "校园网")


class SecretStoreTests(unittest.TestCase):
    """密码一律不落明文: Windows 走 DPAPI, macOS 走钥匙串。"""

    def _profile_cfg(self):
        return {
            "profiles": [{
                "name": core.LIDA_PROFILE_NAME, "preset": core.LIDA_PROFILE_ID,
                "ssid": core.LIDA_SSID, "username": "student", "password": "secret123",
                "auth_url": core.DEFAULT_AUTH_URL, "interval": 60,
            }],
            "active_profile": core.LIDA_PROFILE_NAME,
        }

    def test_windows_password_is_encrypted_on_disk(self):
        if not common.IS_WINDOWS:
            self.skipTest("仅 Windows 用 DPAPI")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "config.json")
            with patch.object(common, "CONFIG_PATH", path):
                cfg = self._profile_cfg()
                config.ensure_preferences(cfg)
                config.save_config(cfg, sync_secrets=True)
                raw = open(path, encoding="utf-8").read()
                stored = json.loads(raw)
                loaded = config.load_config()
        self.assertNotIn("secret123", raw)                     # 明文没落盘
        self.assertEqual(stored["profiles"][0]["password"], "")
        self.assertEqual(stored["profiles"][0]["password_store"], "dpapi")
        self.assertTrue(stored["profiles"][0]["password_enc"])
        self.assertEqual(loaded["profiles"][0]["password"], "secret123")   # 能解回来

    def test_export_and_clear_drop_ciphertext(self):
        cfg = self._profile_cfg()
        cfg["profiles"][0].update({"password_enc": "CIPHERTEXT", "password_store": "dpapi"})
        exported = core.config_for_export(cfg)
        self.assertNotIn("password_enc", exported["profiles"][0])
        self.assertNotIn("password_store", exported["profiles"][0])
        self.assertEqual(exported["profiles"][0]["password"], "")

    def test_undecryptable_ciphertext_is_cleared_without_crash(self):
        if not common.IS_WINDOWS:
            self.skipTest("仅 Windows 用 DPAPI")
        cfg_bad = {
            "profiles": [{
                "name": "立达校园网", "preset": core.LIDA_PROFILE_ID,
                "ssid": core.LIDA_SSID, "username": "u", "password": "",
                "password_store": "dpapi", "password_enc": "bm90LWEtcmVhbC1ibG9i",
                "auth_url": core.DEFAULT_AUTH_URL, "interval": 60,
            }],
            "active_profile": "立达校园网",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(cfg_bad, handle)
            with patch.object(common, "CONFIG_PATH", path):
                loaded = config.load_config()
                stored = json.loads(open(path, encoding="utf-8").read())
        # 解不开就清空并提示, 不留残骸; 也不抛异常
        self.assertEqual(loaded["profiles"][0]["password"], "")
        self.assertEqual(loaded["profiles"][0]["password_store"], "")
        self.assertNotIn("password_enc", stored["profiles"][0])


class CheckAuthHeuristicsTests(unittest.TestCase):
    """check_auth 不能只认死一个标题。"""

    def test_logout_page_variants(self):
        self.assertTrue(auth._authed_from_page("<html><title>注销页</title></html>"))
        self.assertTrue(auth._authed_from_page("<HTML><TITLE>Logout</TITLE></HTML>"))
        self.assertTrue(auth._authed_from_page("<title>已注销</title>"))
        # title 变了但页面是 Dr.COM 注销页
        self.assertTrue(auth._authed_from_page(
            "<html><title>Welcome</title><body>drcom logout</body></html>"))

    def test_login_page_is_not_treated_as_authed(self):
        self.assertFalse(auth._authed_from_page(
            "<html><title>登录页</title><body>drcom login 请登录</body></html>"))
        self.assertFalse(auth._authed_from_page(""))
        self.assertFalse(auth._authed_from_page("<html><title>网络已连接</title></html>"))


class AuthReachableDebounceTests(unittest.TestCase):
    """认证探测防抖: 单次失败不翻转, 连续 3 次才翻。"""

    def setUp(self):
        auth._reach_state.clear()

    def test_single_failure_keeps_previous_result(self):
        with patch.object(auth, "_probe_auth_url", return_value=True):
            self.assertTrue(auth.auth_reachable("http://a/"))
        with patch.object(auth, "_probe_auth_url", return_value=False):
            self.assertTrue(auth.auth_reachable("http://a/"))    # 第 1 次失败: 沿用
            self.assertTrue(auth.auth_reachable("http://a/"))    # 第 2 次失败: 沿用
            self.assertFalse(auth.auth_reachable("http://a/"))   # 第 3 次失败: 翻转

    def test_debounce_false_is_immediate(self):
        with patch.object(auth, "_probe_auth_url", return_value=True):
            auth.auth_reachable("http://a/")
        with patch.object(auth, "_probe_auth_url", return_value=False):
            self.assertFalse(auth.auth_reachable("http://a/", debounce=False))
            # 实时探测会把状态同步过去, 后续防抖调用不会又"恢复"
            self.assertFalse(auth.auth_reachable("http://a/"))


class EnsureLoginRetryTests(unittest.TestCase):
    """认证服务器不可达时不要死磕到 150s。"""

    def test_unreachable_server_short_circuits_attempts(self):
        calls = []
        with patch.object(auth, "auth_reachable", return_value=False), \
                patch.object(auth, "try_login", side_effect=lambda p: calls.append(1) or False), \
                patch.object(auth.time, "sleep", return_value=None):
            ok = auth.ensure_login({"auth_url": "http://a/"}, on_log=lambda m: None)
        self.assertFalse(ok)
        params = inspect.signature(auth.ensure_login).parameters
        self.assertEqual(len(calls), params["fast_attempts"].default)

    def test_reachable_server_uses_full_budget(self):
        calls = []
        with patch.object(auth, "auth_reachable", return_value=True), \
                patch.object(auth, "try_login", side_effect=lambda p: calls.append(1) or False), \
                patch.object(auth.time, "sleep", return_value=None):
            ok = auth.ensure_login({"auth_url": "http://a/"}, on_log=lambda m: None)
        self.assertFalse(ok)
        params = inspect.signature(auth.ensure_login).parameters
        self.assertEqual(len(calls), params["attempts"].default)


class UpdateIntegrityTests(unittest.TestCase):
    """更新包校验与资产挑选。"""

    RELEASE_ASSETS = [
        {"name": "CampusNetManager_v9.9.9_win64.exe",      # 旧式下划线命名(遗留重复包)
         "url": "https://x/legacy.exe", "size": 10, "digest": ""},
        {"name": "CampusNetManager-v9.9.9-win64.exe",      # 规范命名
         "url": "https://x/canonical.exe", "size": 20, "digest": ""},
        {"name": "CampusNetManager-v9.9.9-win64.exe.sha256",
         "url": "https://x/canonical.exe.sha256", "size": 5, "digest": ""},
        {"name": "CampusNetManager-macOS-arm64-v9.9.9.zip",
         "url": "https://x/mac.zip", "size": 30, "digest": ""},
    ]

    def test_pick_asset_prefers_canonical_name(self):
        asset = updater.pick_asset(self.RELEASE_ASSETS, "windows")
        self.assertEqual(asset["name"], "CampusNetManager-v9.9.9-win64.exe")
        self.assertEqual(updater.pick_asset([], "windows"), None)
        self.assertEqual(updater.pick_asset([{"name": "readme.txt"}], "windows"), None)

    def test_digest_to_hex(self):
        good = "a" * 64
        self.assertEqual(updater.digest_to_hex("sha256:" + good), good)
        self.assertEqual(updater.digest_to_hex(good.upper()), good)
        self.assertEqual(updater.digest_to_hex("md5:deadbeef"), "")
        self.assertEqual(updater.digest_to_hex(""), "")

    def test_parse_checksum_for(self):
        text = ("%s  CampusNetManager-v9.9.9-win64.exe\n%s  other.bin\n"
                % ("1" * 64, "2" * 64))
        self.assertEqual(updater.parse_checksum_for(text, "CampusNetManager-v9.9.9-win64.exe"),
                         "1" * 64)
        self.assertEqual(updater.parse_checksum_for(text, "other.bin"), "2" * 64)
        self.assertEqual(updater.parse_checksum_for(text, "missing.bin"), "")
        # 单条无文件名 -> 直接采用
        self.assertEqual(updater.parse_checksum_for("3" * 64, "whatever"), "3" * 64)
        self.assertEqual(updater.parse_checksum_for("no hash here", "x"), "")

    def test_resolve_prefers_asset_digest(self):
        asset = {"name": "a.exe", "digest": "sha256:" + "d" * 64, "url": "u"}
        self.assertEqual(updater.resolve_expected_sha256([asset], asset), "d" * 64)

    def test_resolve_reads_checksum_asset(self):
        payload = ("%s  CampusNetManager-v9.9.9-win64.exe\n" % ("e" * 64)).encode()

        class FakeOpener:
            def open(self, req, timeout=0):
                class R:
                    def read(self_inner):
                        return payload

                    def __enter__(self_inner):
                        return self_inner

                    def __exit__(self_inner, *a):
                        return False
                return R()

        asset = next(a for a in self.RELEASE_ASSETS if a["name"].endswith("-win64.exe"))
        got = updater.resolve_expected_sha256(self.RELEASE_ASSETS, asset, opener=FakeOpener())
        self.assertEqual(got, "e" * 64)

    def test_verify_download(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "pkg.bin")
            with open(path, "wb") as handle:
                handle.write(b"hello world")
            real = updater.sha256_of_file(path)
            self.assertEqual(updater.verify_download(path, real), (True, "SHA256 校验通过"))
            self.assertEqual(updater.verify_download(path, "f" * 64)[0], False)
            # 没有期望值时不拦(只提示), 不让老 Release 直接卡死更新流程
            ok, msg = updater.verify_download(path, "")
            self.assertTrue(ok)
            self.assertIn("跳过校验", msg)


class WebConsoleTokenTests(unittest.TestCase):
    """控制台: 短时令牌 + 常量时间比较 + 畸形口令不 500。"""

    PORT = 19095

    def setUp(self):
        import web_console
        self.web_console = web_console
        self.url = "http://127.0.0.1:%d" % self.PORT
        self.console = web_console.WebConsole(
            state_fn=lambda: {"version": "5.1.2"}, key="good-key-123",
            port=self.PORT, host="127.0.0.1")
        self.console.start()
        time.sleep(0.2)

    def tearDown(self):
        self.console.stop()

    def test_token_roundtrip(self):
        req = urllib.request.Request(
            self.url + "/api/session", method="POST",
            data=json.dumps({}).encode(),
            headers={"X-Console-Key": "good-key-123",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            payload = json.loads(resp.read())
        self.assertTrue(payload["authed"])
        self.assertTrue(payload["token"])
        self.assertEqual(payload["ttl"], self.web_console.TOKEN_TTL)

        # 只用令牌(不带口令)也要能过 —— 令牌走请求头, 不进 URL/历史
        req2 = urllib.request.Request(
            self.url + "/api/status",
            headers={"X-Console-Token": payload["token"]})
        with urllib.request.urlopen(req2, timeout=3) as resp2:
            self.assertEqual(json.loads(resp2.read())["version"], "5.1.2")

    def test_bad_token_falls_back_to_entry_page(self):
        req = urllib.request.Request(
            self.url + "/api/status", headers={"X-Console-Token": "deadbeef"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            self.assertIn("访问口令", resp.read().decode("utf-8", "replace"))

    def test_non_ascii_key_does_not_crash(self):
        # hmac.compare_digest 对含非 ASCII 的 str 会抛 TypeError, 必须编码成 bytes
        with urllib.request.urlopen(self.url + "/api/key?key=%E4%B8%AD%E6%96%87%E5%8F%A3%E4%BB%A4", timeout=3) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(json.loads(resp.read()), {"authed": False})

    def test_referrer_policy_header(self):
        with urllib.request.urlopen(self.url + "/", timeout=3) as resp:
            self.assertEqual(resp.headers.get("Referrer-Policy"), "no-referrer")

    def test_console_page_strips_key_from_url(self):
        with urllib.request.urlopen(self.url + "/?key=good-key-123", timeout=3) as resp:
            body = resp.read().decode("utf-8", "replace")
        self.assertIn("replaceState", body)          # 载入后从地址栏抹掉口令
        self.assertIn("sessionStorage", body)


class SnapshotConcurrencyTests(unittest.TestCase):
    """遍历档案前必须浅拷贝, 否则 GUI 并发增删会抛 RuntimeError。"""

    def test_snapshot_is_a_copy(self):
        cfg = {"profiles": [{"name": "a"}]}
        snap = matching.profiles_snapshot(cfg)
        cfg["profiles"].append({"name": "b"})     # 模拟 GUI 线程同时改列表
        self.assertEqual(len(snap), 1)
        self.assertEqual(len(matching.profiles_snapshot(cfg)), 2)

    def test_snapshot_handles_any_iterable(self):
        # 快照把任意可迭代对象都固化成 list, match_profile 的索引/遍历都安全
        cfg = {"profiles": iter([{"name": "a", "ssid": "X"}])}
        self.assertEqual(matching.match_profile(cfg, "X")["name"], "a")

    def test_match_profile_without_profiles_returns_none(self):
        self.assertIsNone(matching.match_profile({}, "X"))
        self.assertEqual(matching.profiles_snapshot({"profiles": None}), [])


class WindowsHotspotStatsTests(unittest.TestCase):
    """Windows 分支不应再调用拿不到数据的 Get-NetIPStatistics。"""

    def test_no_ip_statistics_call(self):
        calls = []

        def fake_run(cmd, timeout=0):
            calls.append(" ".join(cmd))
            if "Get-NetNeighbor" in " ".join(cmd):
                return "192.168.137.2\n"
            if "Get-NetAdapterStatistics" in " ".join(cmd):
                return "1024 2048\n"
            return ""

        with patch.object(common, "IS_MACOS", False), \
                patch.object(common, "IS_WINDOWS", True), \
                patch.object(router.netinfo, "_run_decode", side_effect=fake_run), \
                patch.object(router, "_arp_entries",
                             return_value=[("192.168.137.2", "AA:BB:CC:DD:EE:FF")]):
            clients = router._iface_clients("本地连接* 10")
        joined = " | ".join(calls)
        self.assertNotIn("Get-NetIPStatistics", joined)
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["ip"], "192.168.137.2")
        self.assertIsNone(clients[0]["rx_bytes"])          # 不假装能按设备拆分
        self.assertIn("整机口径", clients[0]["note"] or "")


class DownloadFirmwareTimeoutTests(unittest.TestCase):
    """timeout 参数必须真的传到 urlopen(旧实现硬编码 30s)。"""

    def test_timeout_is_forwarded(self):
        seen = {}

        class FakeResp:
            headers = {"Content-Length": "3"}

            def read(self, n=-1):
                if seen.get("read"):
                    return b""
                seen["read"] = True
                return b"abc"

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def fake_urlopen(req, timeout=None, **kwargs):
            seen["timeout"] = timeout
            return FakeResp()

        with tempfile.TemporaryDirectory() as temp_dir, \
                patch("urllib.request.urlopen", side_effect=fake_urlopen):
            dest = os.path.join(temp_dir, "fw.bin")
            ok, msg, _sha = router.download_firmware("https://x/fw.bin", dest, timeout=77)
        self.assertTrue(ok, msg)
        self.assertEqual(seen["timeout"], 77)


class SingleInstanceLockTests(unittest.TestCase):
    """lock 记录进程启动时刻, 用于识别 PID 复用。"""

    def test_token_is_available_for_own_process(self):
        self.assertTrue(sysutils.process_start_token(os.getpid()))
        self.assertEqual(sysutils.process_start_token(-1), "")
        self.assertEqual(sysutils.process_start_token("not-a-pid"), "")

    def test_pid_reuse_is_detected_and_lock_taken(self):
        import subprocess
        with tempfile.TemporaryDirectory() as temp_dir:
            lock = os.path.join(temp_dir, "x.lock")
            child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
            try:
                time.sleep(0.8)
                token = sysutils.process_start_token(child.pid)
                if not token:
                    self.skipTest("本环境拿不到进程启动指纹")
                with patch.object(common, "LOCK_PATH", lock):
                    # 同 PID + 正确指纹 => 真的已有实例
                    open(lock, "w").write("%d %s" % (child.pid, token))
                    self.assertFalse(core.acquire_lock())
                    # 同 PID + 过期指纹(= PID 被复用) => 应能接管
                    open(lock, "w").write("%d %s" % (child.pid, "1234567"))
                    self.assertTrue(core.acquire_lock())
            finally:
                child.terminate()
                child.wait()


if __name__ == "__main__":
    unittest.main()
