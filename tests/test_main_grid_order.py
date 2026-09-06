# -*- coding: utf-8 -*-
"""v4.0.3 主界面宫格顺序 + 路由器中继独立窗口回归。
v4.0.4 升级: 宫格改为 10 项, 新增「路由器代理」; 详细见 test_router_proxy_window.py.
"""
import inspect
import re
import unittest

import keepalive_core as core  # noqa


class TestMainGridOrder(unittest.TestCase):
    """主界面 10 宫格按用户指定顺序排列 (v4.0.4)。"""

    def test_grid_cards_in_order(self):
        """按 row, col 抽取 _build_feature_grid 调用的 title 列表, 验证顺序."""
        from app_gui import App
        src = inspect.getsource(App._build_feature_grid)
        # 用 regex 抽取每个 "_feature_card(grid, ROW, COL, \"title\", ..."
        pat = re.compile(r'_feature_card\(\s*grid\s*,\s*(\d+)\s*,\s*(\d+)\s*,\s*"([^"]+)"',
                          re.M)
        cards = []
        for m in pat.finditer(src):
            row, col, title = int(m.group(1)), int(m.group(2)), m.group(3)
            cards.append((row, col, title))
        # 按 (row, col) 排
        cards.sort()
        titles = [c[2] for c in cards]
        # v4.0.4 期望顺序 (10 项: 3 + 4 + 3)
        expected = ["连接档案", "隧道共享", "热点分享",
                    "路由器中继", "路由器代理", "路由器检测", "网络控制台",
                    "网络测速", "新手向导", "偏好设置"]
        self.assertEqual(titles, expected,
                         f"主界面宫格顺序不对: 实际 {titles}")

    def test_grid_has_ten_cards(self):
        """v4.0.4 确认是 10 项宫格 (3 + 4 + 3)."""
        from app_gui import App
        src = inspect.getsource(App._build_feature_grid)
        self.assertEqual(src.count("_feature_card("), 10)


class TestRouterWindowsSplit(unittest.TestCase):
    """show_router_assessment 现在精简（A 段）+ show_router_relay_window 独立（B+C）."""

    def test_assessment_no_longer_calls_lookup_firmware(self):
        """旧 show_router_assessment 不再调 lookup_firmware_urls / download_firmware."""
        from gui.router_tools import RouterToolsMixin
        src = inspect.getsource(RouterToolsMixin.show_router_assessment)
        self.assertNotIn("lookup_firmware_urls", src)
        self.assertNotIn("download_firmware", src)
        self.assertNotIn("router_guide", src)
        # 仍然保留检测
        self.assertIn("detect_router_hardware", src)
        self.assertIn("开始检测", src)

    def test_relay_window_exists(self):
        from gui.router_tools import RouterToolsMixin
        self.assertTrue(hasattr(RouterToolsMixin, "show_router_relay_window"))
        src = inspect.getsource(RouterToolsMixin.show_router_relay_window)
        # 中继窗口同时含中继方案与固件查询
        self.assertIn("router_guide", src)
        self.assertIn("lookup_firmware_urls", src)
        self.assertIn("download_firmware", src)
        self.assertIn("中继校园网方案", src)
        self.assertIn("固件统一准备", src)


if __name__ == "__main__":
    unittest.main()
