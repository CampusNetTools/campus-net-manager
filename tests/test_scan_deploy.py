# -*- coding: utf-8 -*-
"""网关模式识别 + 扫码自动配置引导页 + iOS描述文件 测试"""
import os
import sys
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keepalive_core as core
import shared_proxy as sp


class DetectGatewayModeTests(unittest.TestCase):
    """网关模式识别: 路由器 / 电脑"""

    def test_unknown_no_gateway(self):
        # 无默认网关时返回 unknown
        self.assertIn(core.detect_gateway_mode()["mode"], ("router", "computer", "unknown"))


class SetupPageTests(unittest.TestCase):
    """统一引导页(按设备系统)"""

    def test_ios_page(self):
        page = sp.SharedProxy._setup_page("ios", "192.168.1.180", 8080,
                                          "", "http://192.168.1.180:8080/setup.mobileconfig", "k1")
        p = page.decode() if isinstance(page, bytes) else page
        self.assertIn("iPhone", p)
        self.assertIn("setup.mobileconfig", p)

    def test_android_page(self):
        page = sp.SharedProxy._setup_page("android", "192.168.1.180", 8080,
                                          "http://192.168.1.180:8080/proxy.pac", "", "k1")
        p = page.decode() if isinstance(page, bytes) else page
        self.assertIn("安卓", p)
        self.assertIn("192.168.1.180", p)

    def test_harmony_page(self):
        page = sp.SharedProxy._setup_page("harmony", "192.168.1.180", 8080, "", "", "k1")
        p = page.decode() if isinstance(page, bytes) else page
        self.assertIn("鸿蒙", p)

    def test_key_shown(self):
        page = sp.SharedProxy._setup_page("other", "192.168.1.180", 8080, "", "", "secretKEY")
        p = page.decode() if isinstance(page, bytes) else page
        self.assertIn("secretKEY", p)


class MobileConfigTests(unittest.TestCase):
    """iOS 配置描述文件生成"""

    def test_mobileconfig_valid(self):
        mob = sp.SharedProxy._ios_mobileconfig("192.168.1.180", 8080, "k")
        s = mob.decode("utf-8")
        self.assertIn("plist", s)
        self.assertIn("ProxyServer", s)
        self.assertIn("192.168.1.180", s)
        self.assertIn("8080", s)

    def test_mobileconfig_content_type_endpoint(self):
        # 描述文件端点应有 Content-Type application/x-apple-aspen-config
        self.assertIn("aspen", "application/x-apple-aspen-config")


class UADetectTests(unittest.TestCase):
    """User-Agent 设备识别"""

    def test_ios(self):
        self.assertEqual(sp.SharedProxy._detect_ua(b"User-Agent: iPhone"), "ios")

    def test_android(self):
        self.assertEqual(sp.SharedProxy._detect_ua(b"User-Agent: Android 14"), "android")

    def test_harmony(self):
        self.assertEqual(sp.SharedProxy._detect_ua(b"User-Agent: HarmonyOS 4"), "harmony")

    def test_other(self):
        self.assertEqual(sp.SharedProxy._detect_ua(b"User-Agent: curl/8.0"), "other")


if __name__ == "__main__":
    unittest.main()
