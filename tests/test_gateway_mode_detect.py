# -*- coding: utf-8 -*-
"""v5.0.5 网关模式判定回归: 直连校园网不再被误判为路由器。

旧启发式「网关是私网地址 → 路由器」的 bug: 校园网自身就是大内网
(立达 WiFi 网关 10.52.191.254 / 有线 10.14.0.1 均为私网), 导致
直连校园网永远被判成「经路由器接入」。
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import core.router as router


def _patch_net(gw="10.14.0.1", conn=("ethernet", None), gmac="58:69:6c:5e:cc:9e",
               brand=""):
    """统一打桩: 网关/连接模式(网卡类型判定结果)/MAC/品牌。"""
    return [
        patch.object(router.netinfo, "get_gateway", return_value=gw),
        patch.object(router.netinfo, "get_connection_mode", return_value=conn),
        patch.object(router, "get_gateway_mac", return_value=gmac),
        patch.object(router, "get_router_brand", return_value=brand),
    ]


class TestGatewayModeDetect(unittest.TestCase):
    def _run(self, conn=("ethernet", None), wired_is_campus=True, **kw):
        patches = _patch_net(gw=kw.get("gw", "10.14.0.1"), conn=conn)
        with patches[0], patches[1], patches[2], patches[3]:
            return router.detect_gateway_mode(wired_is_campus=wired_is_campus)

    def test_wired_campus_reachable_is_computer(self):
        """有线 + 校园认证可达 → 电脑有线直连校园网(不再误判路由器)。"""
        r = self._run(conn=("ethernet", None), wired_is_campus=True)
        self.assertEqual(r["mode"], "computer")
        self.assertIn("有线直连校园网", r["description"])

    def test_wired_campus_unreachable_still_router(self):
        """有线但认证不可达(如插了自家路由器) → 维持路由器判定。"""
        r = self._run(conn=("ethernet", None), wired_is_campus=False)
        self.assertEqual(r["mode"], "router")

    def test_ssid_matches_campus_profile_is_computer(self):
        """WiFi SSID 命中校园网档案 → 直连校园网 WiFi。"""
        patches = _patch_net(gw="10.52.191.254",
                             conn=("wifi", "LIDA-UNIVERSITY"))
        with patches[0], patches[1], patches[2], patches[3]:
            r = router.detect_gateway_mode(
                campus_ssids={"LIDA-UNIVERSITY"}, wired_is_campus=False)
        self.assertEqual(r["mode"], "computer")
        self.assertIn("LIDA-UNIVERSITY", r["description"])

    def test_ssid_not_campus_still_router(self):
        """SSID 不在校园网档案(如自家路由器 WiFi/免认证校园 WiFi) → 路由器判定。"""
        r = self._run(conn=("wifi", "富婆爱我一万次5G"), gw="10.14.0.1")
        self.assertEqual(r["mode"], "router")

    def test_wifi_ssid_hidden_not_misjudged_wired(self):
        """Wi-Fi 已关联但 SSID 被打码(None) → 不得进入「有线直连」分支。"""
        r = self._run(conn=("wifi", None), wired_is_campus=True)
        self.assertEqual(r["mode"], "router")

    def test_no_gateway_unknown(self):
        patches = [
            patch.object(router.netinfo, "get_gateway", return_value=None),
            patch.object(router.netinfo, "get_connection_mode",
                         return_value=("none", None)),
            patch.object(router, "get_gateway_mac", return_value=""),
            patch.object(router, "get_router_brand", return_value=""),
        ]
        with patches[0], patches[1], patches[2], patches[3]:
            r = router.detect_gateway_mode()
        self.assertEqual(r["mode"], "unknown")

    def test_backward_compatible_no_args(self):
        """不传参(旧调用方 router_proxy) → 走旧启发式不报错。"""
        r = self._run()
        self.assertIn(r["mode"], ("router", "computer", "unknown"))


if __name__ == "__main__":
    unittest.main()
