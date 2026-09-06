# -*- coding: utf-8 -*-
"""get_lan_ips 排序/过滤: 校园网直连多网卡(Mac + Clash TUN + 历史热点)场景回归。"""
import unittest
from unittest.mock import patch

import shared_proxy


class LanIpsOrderingTests(unittest.TestCase):
    def test_campus_ip_first_when_gateway_same_subnet(self):
        """真实案例: 电脑有线连校园网 + Clash TUN(198.18) + 历史热点(bridge)。
        二维码/代理必须给到校园网出口 IP, 而不是虚拟网卡的旧地址。"""
        fake_ifaces = [
            ("en0", "10.52.188.32", "ffffe000"),    # 校园网出口 (en0)
            ("en7", "192.168.2.1", "ffffff00"),      # 另一张真实网卡(旧热点上游?)
            ("bridge100", "192.168.3.1", "ffffff00"),  # 历史互联网共享网段
            ("utun6", "198.18.0.1", "ffff0000"),      # Clash TUN 假 IP
            ("awdl0", "169.254.1.1", "ffff0000"),     # 链路本地, 应被过滤
        ]
        with patch.object(shared_proxy, "_iface_ips", return_value=fake_ifaces), \
                patch.object(shared_proxy, "_default_gateway_ip",
                             return_value="10.52.191.254"):
            ips = shared_proxy.get_lan_ips()
        # 校园网出口排第一; 虚拟接口与假 IP 全部不出现
        self.assertEqual(ips[0], "10.52.188.32")
        self.assertNotIn("198.18.0.1", ips)
        self.assertNotIn("169.254.1.1", ips)
        # bridge(热点)仍保留作为候选项, 但排真实网卡之后
        self.assertIn("192.168.3.1", ips)
        self.assertLess(ips.index("10.52.188.32"), ips.index("192.168.3.1"))

    def test_no_gateway_falls_back_but_skips_virtual(self):
        """无法解析网关时, 至少过滤掉纯虚拟接口/假 IP, 真实网卡都在。"""
        fake_ifaces = [
            ("en0", "10.52.188.32", "ffffe000"),
            ("utun6", "198.18.0.1", "ffff0000"),
            ("ppp0", "10.0.8.2", "ffffff00"),
        ]
        with patch.object(shared_proxy, "_iface_ips", return_value=fake_ifaces), \
                patch.object(shared_proxy, "_default_gateway_ip", return_value=None):
            ips = shared_proxy.get_lan_ips()
        self.assertIn("10.52.188.32", ips)
        self.assertNotIn("198.18.0.1", ips)
        self.assertNotIn("10.0.8.2", ips)

    def test_same_net_mask_logic(self):
        self.assertTrue(shared_proxy._same_net("10.52.188.32", "10.52.191.254", "ffffe000"))
        # /16 下两者同属 10.52.0.0 网段
        self.assertTrue(shared_proxy._same_net("10.52.188.32", "10.52.191.254", "ffff0000"))
        # /32(精确主机)不再同段
        self.assertFalse(shared_proxy._same_net("10.52.188.32", "10.52.191.254", "ffffffff"))
        self.assertFalse(shared_proxy._same_net("192.168.3.1", "10.52.191.254", "ffffff00"))


if __name__ == "__main__":
    unittest.main()
