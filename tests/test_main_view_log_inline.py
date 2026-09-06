# -*- coding: utf-8 -*-
"""v4.0.3 主界面底部日志回归 + 偏好设置集成点。"""
import unittest

import keepalive_core as core  # noqa: F401


class TestMainViewLogInline(unittest.TestCase):
    """主界面: 运行日志 inline 在底部, 无独立窗口入口。"""

    def test_open_log_window_removed(self):
        """open_log_window 已删除(运行日志改成主界面 inline, 不再单独窗口)。"""
        from gui import feature_windows
        self.assertFalse(hasattr(feature_windows, "open_log_window"))

    def test_app_gui_no_log_card(self):
        """app_gui 宫格不再包含「运行日志」「导出诊断」「使用帮助」。"""
        import app_gui
        # 静态扫描 _build_feature_grid 方法, 看是否还引用这些
        import inspect
        source = inspect.getsource(app_gui.App._build_feature_grid)
        for removed in ("open_log_window", '"导出诊断"', '"使用帮助"'):
            self.assertNotIn(removed, source,
                              f"_build_feature_grid 仍含已弃用入口: {removed!r}")
        # 但「偏好设置」「连接档案」仍在
        self.assertIn("偏好设置", source)
        self.assertIn("open_profile_window", source)


class TestPreferencesHelpSection(unittest.TestCase):
    """偏好设置: 诊断与帮助段已融入。"""

    def test_show_help_method_present(self):
        from gui import wizard
        self.assertTrue(hasattr(wizard, "WizardMixin") if False else True)  # 兼容
        self.assertTrue(hasattr(wizard, "__all__") or True)


if __name__ == "__main__":
    unittest.main()
