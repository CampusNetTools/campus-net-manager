# -*- coding: utf-8 -*-
"""v4.0.3 排版系统 + 各窗口几何回归测试。"""
import inspect
import unittest

import keepalive_core as core  # noqa


class TestThemePadding(unittest.TestCase):
    """theme.py 排版 8px 网格常量被正确导出。"""

    def test_grid_constants_present(self):
        from gui import theme
        for key in ("PAD_XS", "PAD_S", "PAD_M", "PAD_L", "PAD_XL", "PAD_XXL",
                    "CARD_PAD_MAIN", "CARD_PAD_SUB", "WINDOW_PAD",
                    "GAP_SECTION", "GAP_FORM_ROW", "GAP_LABEL_TO_FIELD",
                    "GAP_FIELD_TO_HINT", "GAP_BUTTON_X",
                    "DESC_WRAP_FEATURE", "DESC_WRAP_FORM", "DESC_WRAP_DIALOG",
                    "DESC_WRAP_LONG", "FONT_MONO"):
            self.assertTrue(hasattr(theme, key),
                            f"theme.{key} 未定义")

    def test_padding_scale_monotonic(self):
        from gui import theme
        self.assertEqual(theme.PAD_XS, 4)
        self.assertEqual(theme.PAD_S, 8)
        self.assertEqual(theme.PAD_M, 12)
        self.assertEqual(theme.PAD_L, 16)
        self.assertEqual(theme.PAD_XL, 20)
        self.assertEqual(theme.PAD_XXL, 24)
        for tup in (theme.CARD_PAD_MAIN, theme.CARD_PAD_SUB, theme.WINDOW_PAD):
            for v in tup:
                self.assertGreaterEqual(v, 8)
                self.assertLessEqual(v, 32)


class TestWindowGeometry(unittest.TestCase):
    """关键窗体的几何尺寸留出足够空间且符合排版规范。"""

    def test_main_window_size(self):
        from app_gui import App
        src = inspect.getsource(App.__init__)
        # v5 主窗 1140x880 / minsize 1020x780 (双栏布局需要更宽)
        self.assertIn("1140", src)
        self.assertIn("880", src)
        self.assertIn("1020", src)
        self.assertIn("780", src)

    def test_preferences_window_size(self):
        from gui.preferences import PreferencesMixin
        src = inspect.getsource(PreferencesMixin.show_preferences)
        # 偏好 680x800 / minsize 640x660 / 卡片 padding 26/24
        self.assertIn("680", src)
        self.assertIn("800", src)
        self.assertIn("padding=(26, 24)", src)

    def test_profile_window_size(self):
        """v5: 连接档案内嵌主窗, open_profile_window 只置前主窗(不再开 780x620 独立窗)。"""
        from gui.feature_windows import FeatureWindowsMixin
        src = inspect.getsource(FeatureWindowsMixin.open_profile_window)
        self.assertNotIn("Toplevel", src)

    def test_hotspot_window_size(self):
        from gui.feature_windows import FeatureWindowsMixin
        src = inspect.getsource(FeatureWindowsMixin.open_hotspot_window)
        self.assertIn("720", src)
        self.assertIn("620", src)
        self.assertIn("padding=(24, 22)", src)


class TestMainViewFooterLog(unittest.TestCase):
    """主界面底部 inline 日志: 取消 open_log_window 单独入口后, 日志跟随主界面。"""

    def test_main_log_text_widget_present(self):
        # 直接验证 app_gui 源码不依赖 open_log_window 单独构造
        import app_gui
        src = inspect.getsource(app_gui.App._build_ui)
        self.assertIn("txt_log", src)
        self.assertIn("log_card", src)
        # 没有 open_log_window 调用的痕迹(已彻底搬到主界面底部)
        # open_log_window 只应在 feature_windows 中作为遗留代码
        from gui import feature_windows
        self.assertFalse(hasattr(feature_windows, "open_log_window"))


if __name__ == "__main__":
    unittest.main()
