# -*- coding: utf-8 -*-
"""档案类型(校园网/普通WiFi) + 普通WiFi只检测断网 测试"""
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keepalive_core as core


class ProfileTypeTests(unittest.TestCase):
    """档案类型判定: 校园网认证 vs 普通WiFi/热点"""

    def test_default_campus_has_auth(self):
        p = core.default_profile("校园网")
        self.assertEqual(p["profile_type"], "campus")
        self.assertEqual(p["auth_url"], core.DEFAULT_AUTH_URL)

    def test_default_wifi_no_auth(self):
        p = core.default_profile("热点", "wifi")
        self.assertEqual(p["profile_type"], "wifi")
        self.assertEqual(p["auth_url"], "")

    def test_profile_is_wifi(self):
        self.assertTrue(core.profile_is_wifi(core.default_profile("热点", "wifi")))
        self.assertFalse(core.profile_is_wifi(core.default_profile("校园网", "campus")))

    def test_legacy_campus_not_wifi(self):
        # 旧档案: 有账号+auth_url, 无profile_type -> 应视为校园网(不误判wifi)
        old = {"name": "立达", "ssid": "LIDA", "username": "u", "password": "p",
               "auth_url": "http://192.168.16.3/"}
        self.assertFalse(core.profile_is_wifi(old))

    def test_legacy_empty_is_wifi(self):
        # 旧空档案(任意网络): 无账号无auth_url -> 兼容视为wifi(只检测)
        old = {"name": "新档案1", "ssid": "", "username": "", "password": "", "auth_url": ""}
        self.assertTrue(core.profile_is_wifi(old))


if __name__ == "__main__":
    unittest.main()
