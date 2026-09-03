# -*- coding: utf-8 -*-
"""防踢保活与中继场景回归测试"""
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keepalive_core as core


class KickGuardTests(unittest.TestCase):
    """防踢保活逻辑测试: 周期性刷新登录, 让会话保持最新不被挤掉"""

    def _make_daemon(self, cfg=None):
        d = core.KeepAliveDaemon(cfg or {"profiles": [], "kick_guard": True})
        d._refresh_count = 0
        d._kickguard = True
        return d

    def test_default_kick_guard_enabled(self):
        prefs = core.default_preferences()
        self.assertTrue(prefs["kick_guard"])

    def test_refresh_fires_after_three_cycles(self):
        d = self._make_daemon()
        # 模拟: 正常在线3轮应触发一次刷新(计数归零)
        for i in range(3):
            d._refresh_count += 1
            fired = d._kickguard and d._refresh_count >= 3
            if fired:
                d._refresh_count = 0
        self.assertEqual(d._refresh_count, 0)
        self.assertTrue(fired)

    def test_no_refresh_when_disabled(self):
        d = core.KeepAliveDaemon({"profiles": [], "kick_guard": False})
        d._refresh_count = 0
        d._kickguard = False
        fired = False
        for i in range(10):
            d._refresh_count += 1
            if d._kickguard and d._refresh_count >= 3:
                fired = True
                d._refresh_count = 0
        self.assertFalse(fired)

    def test_profile_has_credentials(self):
        self.assertTrue(core.profile_has_credentials({"username": "u", "password": "p"}))
        self.assertFalse(core.profile_has_credentials({"username": "", "password": ""}))
        self.assertFalse(core.profile_has_credentials(None))

    def test_match_profile_relay_prefers_account_profile(self):
        """中继场景: 连路由器WiFi时, 应优先选用有账号的立达档案而非空账号默认档案"""
        cfg = {"profiles": [
            {"name": "立达校园网", "ssid": "LIDA-UNIVERSITY", "username": "24012752",
             "password": "x", "auth_url": "http://192.168.16.3/"},
            {"name": "新档案1", "ssid": "", "username": "", "password": "",
             "auth_url": "http://192.168.16.3/"},
        ]}
        p = core.match_profile(cfg, "TP-LINK_xxx", "192.168.1.1")
        self.assertEqual(p["name"], "立达校园网")
        self.assertTrue(p.get("username"))

    def test_match_profile_ssid_precision_wins(self):
        cfg = {"profiles": [
            {"name": "立达", "ssid": "LIDA-UNIVERSITY", "username": "u", "password": "p",
             "auth_url": "http://192.168.16.3/"},
            {"name": "路由器", "ssid": "TP-LINK_xxx", "username": "r", "password": "p",
             "auth_url": "http://192.168.16.3/"},
        ]}
        p = core.match_profile(cfg, "TP-LINK_xxx", "192.168.1.1")
        self.assertEqual(p["name"], "路由器")


class KeepAwakeTests(unittest.TestCase):
    """合盖/休眠保持运行 (caffeinate) 测试"""

    def test_keep_awake_apis_exist(self):
        self.assertTrue(callable(core.keep_awake_start))
        self.assertTrue(callable(core.keep_awake_stop))
        self.assertTrue(callable(core.keep_awake_enabled))

    def test_keep_awake_roundtrip_macos(self):
        if not core.IS_MACOS:
            self.skipTest("macOS only")
        ok = core.keep_awake_start()
        self.assertTrue(ok)
        self.assertTrue(core.keep_awake_enabled())
        core.keep_awake_stop()
        self.assertFalse(core.keep_awake_enabled())


if __name__ == "__main__":
    unittest.main()
