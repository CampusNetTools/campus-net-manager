# -*- coding: utf-8 -*-
"""v5.0.0 主界面双栏布局回归 (v4 宫格测试已随宫格删除而重写)。
路由器中继独立窗口断言保留。
"""
import inspect
import unittest

import keepalive_core as core  # noqa


class TestV5LayoutReplacesGrid(unittest.TestCase):
    """v4 的 10 宫格已由 v5 双栏(左档案表单+右功能导航)取代。"""

    def test_grid_methods_removed(self):
        from app_gui import App
        self.assertFalse(hasattr(App, "_build_feature_grid"),
                         "v5 已删除 _build_feature_grid")

    def test_nav_uses_fwin_single_instance(self):
        """右栏导航按钮仍走 _fwin_open_legacy 单实例机制。"""
        from app_gui import App
        src = inspect.getsource(App._build_ui)
        self.assertIn("_fwin_open_legacy", src)
        # 计数: 路由器中继/代理/检测 + 测速 + 向导 + 偏好 = 6 处
        self.assertEqual(src.count("_fwin_open_legacy"), 6)


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
