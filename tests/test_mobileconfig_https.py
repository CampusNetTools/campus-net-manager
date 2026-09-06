# -*- coding: utf-8 -*-
"""回归 mobileconfig 必须含 HTTP + HTTPS 两套代理 (v4.0.4 修复)。

v4.0.3 之前只填 HTTPEnable/HTTPPort/HTTPProxy, iPhone Safari 默认全 HTTPS 直连
导致即使装上描述文件, 浏览器仍然走 HTTPS 直连失败 (手机上不了网)。
本测试验证 _ios_mobileconfig 同时含 HTTPSEnable/HTTPSPort/HTTPSProxy。
"""
import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shared_proxy  # noqa: E402


class TestIOSMobileconfigHTTPS(unittest.TestCase):
    """iOS mobileconfig 必须含 HTTP + HTTPS 两套代理."""

    def test_mobileconfig_has_http_proxy(self):
        """兼容老 case: HTTPEnable/HTTPPort/HTTPProxy 三件套仍在."""
        plist = shared_proxy.SharedProxy._ios_mobileconfig(
            "10.52.188.32", 8080, "testkey123")
        if isinstance(plist, bytes):
            plist = plist.decode("utf-8")
        self.assertIn("<key>HTTPEnable</key><integer>1</integer>", plist)
        self.assertIn("<key>HTTPPort</key><integer>8080</integer>", plist)
        self.assertIn("<key>HTTPProxy</key><string>10.52.188.32</string>", plist)

    def test_mobileconfig_has_https_proxy(self):
        """v4.0.4 新增: HTTPSEnable/HTTPSPort/HTTPSProxy 也必须填, 否则 iPhone Safari 上不了网."""
        plist = shared_proxy.SharedProxy._ios_mobileconfig(
            "10.52.188.32", 8080, "testkey123")
        if isinstance(plist, bytes):
            plist = plist.decode("utf-8")
        self.assertIn("<key>HTTPSEnable</key><integer>1</integer>", plist)
        self.assertIn("<key>HTTPSPort</key><integer>8080</integer>", plist)
        self.assertIn("<key>HTTPSProxy</key><string>10.52.188.32</string>", plist)

    def test_mobileconfig_has_proxy_server_port(self):
        """ProxyServer/ProxyServerPort 是 iOS 顶层代理设置, 必须存在."""
        plist = shared_proxy.SharedProxy._ios_mobileconfig(
            "192.168.1.1", 8080, "key")
        if isinstance(plist, bytes):
            plist = plist.decode("utf-8")
        self.assertIn("<key>ProxyServer</key><string>192.168.1.1</string>", plist)
        self.assertIn("<key>ProxyServerPort</key><integer>8080</integer>", plist)

    def test_mobileconfig_valid_plist(self):
        """生成的 plist 是合法 XML, 包含 plist/dict/array 根节点."""
        plist = shared_proxy.SharedProxy._ios_mobileconfig(
            "10.0.0.1", 8080, "key")
        if isinstance(plist, bytes):
            plist = plist.decode("utf-8")
        self.assertIn("<?xml version=\"1.0\" encoding=\"UTF-8\"?>", plist)
        self.assertIn("<plist version=\"1.0\">", plist)
        self.assertIn("<key>PayloadContent</key>", plist)
        self.assertIn("<key>PayloadType</key><string>com.apple.proxy.managed</string>", plist)


if __name__ == "__main__":
    unittest.main()