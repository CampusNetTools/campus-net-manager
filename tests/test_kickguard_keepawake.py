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


CAMPUS_PROFILE = {"name": "立达校园网", "ssid": "LIDA-UNIVERSITY", "username": "24012752",
                  "password": "x", "auth_url": "http://192.168.16.3/", "gateway": ""}


class CampusLockTests(unittest.TestCase):
    """环境判定 is_campus_locked: 认证探测失败时是否按校园网处理"""

    def test_wifi_direct_lida_locked(self):
        self.assertTrue(core.is_campus_locked(CAMPUS_PROFILE, "LIDA-UNIVERSITY", "10.52.1.1"))

    def test_ethernet_relay_locked(self):
        """有线接路由器(无SSID) + 有账号档案 -> 锁定(不误判非校园网)"""
        self.assertTrue(core.is_campus_locked(CAMPUS_PROFILE, None, "192.168.1.1"))

    def test_home_wifi_not_locked(self):
        """家里WiFi(SSID不匹配, 有SSID) -> 不锁定(保持休眠不误登)"""
        self.assertFalse(core.is_campus_locked(CAMPUS_PROFILE, "MyHomeWiFi", "192.168.50.1"))

    def test_empty_profile_not_locked(self):
        self.assertFalse(core.is_campus_locked(
            {"name": "空", "ssid": "", "username": "", "password": "",
             "auth_url": "http://192.168.16.3/"}, None, "192.168.1.1"))
        self.assertFalse(core.is_campus_locked(None, None, "192.168.1.1"))

    def test_gateway_bound_locked(self):
        prof = dict(CAMPUS_PROFILE, ssid="", gateway="192.168.1.1")
        self.assertTrue(core.is_campus_locked(prof, None, "192.168.1.1"))
        self.assertFalse(core.is_campus_locked(prof, "SomeWiFi", "10.0.0.1"))


class RespectUserChoiceTests(unittest.TestCase):
    """尊重「任意网络使用」选择: 不自动回退到校园网档案, 不强制锁定为校园网"""

    def _cfg(self):
        return {"profiles": [
            {"name": "立达校园网", "ssid": "LIDA-UNIVERSITY", "username": "24012752",
             "password": "pw", "auth_url": "http://192.168.16.3/", "gateway": ""},
            {"name": "新档案1", "ssid": "", "username": "", "password": "",
             "auth_url": "http://192.168.16.3/"},
        ], "active_profile": "新档案1"}  # 用户选"任意网络"

    def test_match_respects_any_network(self):
        cfg = self._cfg()
        p = core.match_profile(cfg, "192.168.1.1", None, respect_user_choice=True)
        self.assertEqual(p["name"], "新档案1")  # 不回退到立达

    def test_match_default_still_falls_back_for_autologin(self):
        cfg = self._cfg()
        p = core.match_profile(cfg, "192.168.1.1", None, respect_user_choice=False)
        self.assertEqual(p["name"], "立达校园网")  # 自动登录用的兜底保留

    def test_user_any_network_detected(self):
        cfg = self._cfg()
        active = next(p for p in cfg["profiles"] if p["name"] == cfg["active_profile"])
        user_any = not active.get("ssid") and not active.get("gateway") and not core.profile_has_credentials(active)
        self.assertTrue(user_any)

    def test_any_network_hotspot_not_locked(self):
        """连手机热点(无SSID) + 用户选任意网络 -> 不锁定(不硬拉去登校园网)"""
        anyprof = {"name": "新档案1", "ssid": "", "username": "", "password": "",
                   "auth_url": "http://192.168.16.3/"}
        self.assertFalse(core.is_campus_locked(anyprof, None, "172.20.10.1", respect_user_choice=True))

    def test_campus_profile_locked_when_no_ssid(self):
        """选立达档案 + 无SSID -> 锁定(用户明确要登校园网)"""
        lida = {"name": "立达", "ssid": "LIDA-UNIVERSITY", "username": "u", "password": "p",
                "auth_url": "http://192.168.16.3/"}
        self.assertTrue(core.is_campus_locked(lida, None, "172.20.10.1", respect_user_choice=False))

    def test_campus_profile_ssid_match_locked(self):
        lida = {"name": "立达", "ssid": "LIDA-UNIVERSITY", "username": "u", "password": "p",
                "auth_url": "http://192.168.16.3/"}
        self.assertTrue(core.is_campus_locked(lida, "LIDA-UNIVERSITY", "10.52.1.1", respect_user_choice=False))

    def test_any_network_ssid_mismatch_not_locked(self):
        anyprof = {"name": "新档案1", "ssid": "", "username": "", "password": "",
                   "auth_url": "http://192.168.16.3/"}
        self.assertFalse(core.is_campus_locked(anyprof, "SomeWiFi", "192.168.1.1", respect_user_choice=True))

    def test_choosing_campus_profile_not_any(self):
        cfg = dict(self._cfg(), active_profile="立达校园网")
        active = next(p for p in cfg["profiles"] if p["name"] == cfg["active_profile"])
        user_any = not active.get("ssid") and not active.get("gateway") and not core.profile_has_credentials(active)
        self.assertFalse(user_any)


if __name__ == "__main__":
    unittest.main()
