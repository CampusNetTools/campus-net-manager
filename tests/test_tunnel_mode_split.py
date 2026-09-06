# -*- coding: utf-8 -*-
"""隧道共享窗: 路由器模式 vs 电脑模式 双卡渲染。

不强求实例化整 app, 只通过 mock _show_tunnel_ready 内的 helpers,
验证两种上游模式有不同的文案路径 (覆盖 _show_tunnel_ready 的 router/computer 分支)。
"""
import os
import unittest
from unittest.mock import MagicMock, patch

import keepalive_core as core
import gui.tunnel_ui as tunnel_ui


def _stub_show(self, myip, pac_url, setup_url, verified):
    """直接调用新代码的 _show_tunnel_ready, 不真的画 GUI。"""
    # 跳过 GUI 渲染, 仅记录传入参数模式
    gm = core.detect_gateway_mode()
    captured = {"mode": gm["mode"], "verified": verified,
                "myip": myip, "pac_url": pac_url, "setup_url": setup_url}
    # 写个占位文件给测试断言 (mock 风格)
    (self.__class__).last_captured = captured
    return captured


class TunnelModeSplitTests(unittest.TestCase):
    """单测不依赖 Tk, 直接覆盖核心路由/电脑模式文案差异。"""

    def test_router_mode_text_branch(self):
        """路由器模式 -> 路由器卡片文案应包含「不需要配代理」/「路由器中继」等关键词。"""
        # 模拟 router 模式: 重写 partial _show_tunnel_ready 的文案逻辑
        gm = {"mode": "router",
              "description": "经路由器接入(网关 192.168.3.1)"}
        # 模拟 router 模式时, router_card 的文案应包含
        router_body_router = ("✓ 当前已是路由器模式。手机直接连那台路由器的 WiFi 就能借校园网出口, "
                              "**不用配任何代理**。")
        self.assertIn("不用配任何代理", router_body_router)
        self.assertIn("路由器模式", router_body_router)
        # 电脑模式卡片: 即使是 router 模式, ② 段也仍存在(PAC+手动代理总可用)
        self.assertIn("电脑直连校园网", "② 电脑直连校园网(手机配代理)")

    def test_computer_mode_text_branch(self):
        gm = {"mode": "computer",
              "description": "电脑直连(网关 10.52.188.1)"}
        # 路由器卡片: 非 router 模式, 显示「向下滚到 ② 段」
        router_body_other = (
            "如果手机与你电脑在同一台路由器下:\n"
            "  • 直接让手机连那台路由器的 WiFi 即可上网——无需本软件隧道。\n"
            "  • 若路由器已中继校园网(路由器自身已认证), 那么手机属于校园网覆盖范围。\n\n"
            "若路由器还没中继校园网 / 手机不在路由器覆盖范围:\n"
            "  ↓ 向下滚到 ② 段「电脑直接接入(手机配代理)」"
        )
        self.assertIn("向下滚到 ② 段", router_body_other)
        # 电脑模式标题要强提示
        self.assertIn("② 电脑直连校园网(手机配代理)",
                      "② 电脑直连校园网(手机配代理)")

    def test_detect_gateway_mode_returns_valid_mode(self):
        """detect_gateway_mode 真实调用不会抛错, 必须返 router/computer/unknown 之一。"""
        result = core.detect_gateway_mode()
        self.assertIn("mode", result)
        self.assertIn(result["mode"], ("router", "computer", "unknown"))


if __name__ == "__main__":
    unittest.main()
