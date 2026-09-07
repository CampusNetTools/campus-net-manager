# -*- coding: utf-8 -*-
"""v5.0.6 有线/无线判定回归: 按网卡硬件类型, 不再依赖能否读到 SSID。

背景: macOS 26 隐私机制对无定位授权的进程打码 SSID(networksetup 甚至谎报
not associated), 旧逻辑「读不到 SSID = 有线」把 Wi-Fi 误判成有线以太网。
新逻辑: 默认路由网卡的 Hardware Port 是 Wi-Fi 且 ipconfig getsummary
存在 SSID 行(内容可打码) → 无线; 以太网类网卡 → 有线。
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.netinfo as netinfo
import core.router as router

WIFI_SUMMARY = """ipconfig getsummary en0
  SSID : <redacted>
  BSSID : aa:bb:cc:dd:ee:ff
  router = 10.14.0.1
"""

WIRED_SUMMARY = """ipconfig getsummary en5
  router = 10.14.0.1
"""


def _patch_run(mapping):
    """patch netinfo._run_decode: 完整命令串按 mapping key 前缀匹配。"""
    def fake(cmd, timeout=10):
        full = " ".join(cmd)
        for k, v in mapping.items():
            if full.startswith(k):
                return v
        return ""
    return patch.object(netinfo, "_run_decode", side_effect=fake)


class TestConnectionModeByIfaceType(unittest.TestCase):
    def test_wifi_redacted_ssid_is_wifi(self):
        """Wi-Fi 网卡已关联但 SSID 被打码 → 必须判 wifi(不是 ethernet)。"""
        mapping = {
            "networksetup -listallhardwareports":
                'Hardware Port: Wi-Fi\nDevice: en0\n\n'
                'Hardware Port: Ethernet\nDevice: en5\n',
            "networksetup -getairportnetwork en0":
                "You are not associated with an AirPort network.",  # 谎报
            "ipconfig getsummary en0": WIFI_SUMMARY,
            "netstat -rn -f inet":
                "default 10.14.0.1 UGScIg en0\n",
        }
        with _patch_run(mapping), \
                patch.object(netinfo, "get_ssid", return_value=None):
            mode, ssid = netinfo.get_connection_mode()
        self.assertEqual(mode, "wifi")
        self.assertIsNone(ssid)  # 真名读不到, 但模式必须对

    def test_real_ethernet_is_ethernet(self):
        mapping = {
            "networksetup -listallhardwareports":
                'Hardware Port: Wi-Fi\nDevice: en0\n\n'
                'Hardware Port: Ethernet Adapter\nDevice: en5\n',
            "ipconfig getsummary en5": WIRED_SUMMARY,
            "netstat -rn -f inet":
                "default 10.14.0.1 UGScIg en5\n",
        }
        with _patch_run(mapping):
            mode, ssid = netinfo.get_connection_mode()
        self.assertEqual(mode, "ethernet")
        self.assertIsNone(ssid)

    def test_no_network_is_none(self):
        mapping = {
            "networksetup -listallhardwareports":
                'Hardware Port: Wi-Fi\nDevice: en0\n',
            "ipconfig getsummary en0": "",
            "netstat -rn -f inet": "",
        }
        with _patch_run(mapping):
            mode, ssid = netinfo.get_connection_mode()
        self.assertEqual(mode, "none")


class TestDetectGatewayModeIfaceAware(unittest.TestCase):
    """detect_gateway_mode: Wi-Fi(打码) 不再走「有线直连」分支。"""

    def _detect(self, conn_mode, wired_is_campus=True):
        with patch.object(router.netinfo, "get_gateway",
                          return_value="10.14.0.1"), \
                patch.object(router.netinfo, "get_connection_mode",
                             return_value=(conn_mode, None)):
            return router.detect_gateway_mode(wired_is_campus=wired_is_campus)

    def test_wifi_redacted_not_misjudged_wired_campus(self):
        from core import router
        r = self._detect("wifi", wired_is_campus=True)
        # Wi-Fi + SSID 打码 → 不能进「有线直连」分支, 走旧启发式(router)
        self.assertEqual(r["mode"], "router")

    def test_ethernet_campus_is_computer(self):
        from core import router
        r = self._detect("ethernet", wired_is_campus=True)
        self.assertEqual(r["mode"], "computer")
        self.assertIn("有线直连校园网", r["description"])

    def test_ethernet_no_campus_is_router(self):
        from core import router
        r = self._detect("ethernet", wired_is_campus=False)
        self.assertEqual(r["mode"], "router")


if __name__ == "__main__":
    unittest.main()
