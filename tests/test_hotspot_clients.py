# -*- coding: utf-8 -*-
"""回归 v4.0.3 热点窗口设备列表/流量 + Windows 一键开热点。

场景:
- fmt_bytes 字节格式化(B/KiB/MiB/GiB/TiB/PiB)
- macOS 上 list_hotspot_clients 不崩溃, _hotspot_iface_candidates 识别 bridge0
- start_mobile_hotspot 在 macOS 上返 False + 明确提示(不调 subprocess)
- start_mobile_hotspot 在 Windows 上 mock 优先 PowerShell Start-MobileHotspot
"""
import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import core  # noqa: E402
from core import router  # noqa: E402


class TestFmtBytes(unittest.TestCase):
    def test_bytes_zero(self):
        self.assertEqual(router.fmt_bytes(0), "0 B")

    def test_bytes_small(self):
        self.assertIn("B", router.fmt_bytes(512))

    def test_kib(self):
        self.assertIn("KiB", router.fmt_bytes(2048))

    def test_mib(self):
        self.assertIn("MiB", router.fmt_bytes(5 * 1024 * 1024))

    def test_gib(self):
        self.assertIn("GiB", router.fmt_bytes(3 * 1024 ** 3))

    def test_invalid_input(self):
        # 非法输入不崩
        self.assertIsInstance(router.fmt_bytes(None), str)


class TestMacOSStartHotspot(unittest.TestCase):
    """macOS 上 start_mobile_hotspot 必须返 False 且不调用 subprocess. """

    def test_macos_returns_false_with_clear_reason(self):
        with patch.object(core.common, "IS_MACOS", True), \
             patch.object(core.common, "IS_WINDOWS", False):
            ok, msg = router.start_mobile_hotspot()
        self.assertFalse(ok)
        self.assertIn("macOS", msg)
        self.assertIn("不支持脚本化", msg)


class TestWindowsStartHotspot(unittest.TestCase):
    """Windows 上优先 PowerShell Start-MobileHotspot; netsh 兜底. """

    def test_powershell_success(self):
        with patch.object(core.common, "IS_MACOS", False), \
             patch.object(core.common, "IS_WINDOWS", True), \
             patch.object(router.netinfo, "_run_decode",
                          return_value="OK\n"):
            ok, msg = router.start_mobile_hotspot()
        self.assertTrue(ok)
        self.assertIn("PowerShell", msg)

    def test_powershell_fail_then_netsh_fail(self):
        with patch.object(core.common, "IS_MACOS", False), \
             patch.object(core.common, "IS_WINDOWS", True), \
             patch.object(router.netinfo, "_run_decode",
                          side_effect=["FAIL\n",
                                       "The wireless local area network interface is disabled.\n"]):
            ok, msg = router.start_mobile_hotspot()
        self.assertFalse(ok)
        self.assertIn("网卡", msg)

    def test_powershell_fail_then_netsh_success(self):
        with patch.object(core.common, "IS_MACOS", False), \
             patch.object(core.common, "IS_WINDOWS", True), \
             patch.object(router.netinfo, "_run_decode",
                          side_effect=["FAIL\n",
                                       "The hosted network started.\n"]):
            ok, msg = router.start_mobile_hotspot()
        self.assertTrue(ok)
        self.assertIn("netsh", msg)


class TestListHotspotClients(unittest.TestCase):
    """list_hotspot_clients 在没有热点时返 [], 不崩溃. """

    def test_no_hotspot_returns_empty(self):
        # 没有 bridge0 NAT 时应该返 []
        with patch.object(router, "_hotspot_iface_candidates", return_value=[]):
            self.assertEqual(router.list_hotspot_clients(), [])

    def test_macos_with_bridge_returns_list(self):
        # bridge0 上有 192.168.3.1 + 一个客户端 192.168.3.10
        fake_ifconfig = (
            "bridge0: flags=8a63<UP> mtu 1500\n"
            "\tinet 192.168.3.1 netmask 0xffffff00 broadcast 192.168.3.255\n"
            "\tether aa:bb:cc:dd:ee:ff\n"
        )
        with patch.object(router, "_hotspot_iface_candidates", return_value=["bridge0"]), \
             patch.object(router.netinfo, "_run_decode", return_value=fake_ifconfig), \
             patch.object(router, "_arp_entries",
                          return_value=[("192.168.3.10", "AA:BB:CC:11:22:33"),
                                        ("192.168.3.1", "AA:BB:CC:DD:EE:FF"),  # 自己, 应过滤
                                        ("192.168.3.255", "FF:FF:FF:FF:FF:FF")]), \
             patch.object(router, "_iface_total_bytes", return_value=(1024, 2048)):
            clients = router.list_hotspot_clients()
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["ip"], "192.168.3.10")
        self.assertEqual(clients[0]["mac"], "AA:BB:CC:11:22:33")
        # macOS 上 rx/tx 是 None (需 sudo 才能按 IP 拆分)
        self.assertIsNone(clients[0]["rx_bytes"])
        self.assertIsNone(clients[0]["tx_bytes"])
        self.assertIn("bridge0", clients[0]["note"])


class TestHotspotIfaceCandidates(unittest.TestCase):
    def test_macos_recognizes_bridge0(self):
        fake = (
            "en0: flags=8863<UP> mtu 1500\n"
            "\tinet 10.52.188.32 netmask 0xffffe000 broadcast 10.52.191.255\n"
            "bridge0: flags=8a63<UP> mtu 1500\n"
            "\tinet 192.168.3.1 netmask 0xffffff00 broadcast 192.168.3.255\n"
            "bridge100: flags=8a63<UP> mtu 1500\n"
            "\tinet 192.168.2.1 netmask 0xffffff00 broadcast 192.168.2.255\n"
        )
        with patch.object(core.common, "IS_MACOS", True), \
             patch.object(core.common, "IS_WINDOWS", False), \
             patch.object(router.netinfo, "_run_decode", return_value=fake):
            names = router._hotspot_iface_candidates()
        self.assertIn("bridge0", names)
        self.assertIn("bridge100", names)
        self.assertNotIn("en0", names)  # 校园网不是 NAT


if __name__ == "__main__":
    unittest.main()