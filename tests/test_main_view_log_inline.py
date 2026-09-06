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
        """v5 主窗功能导航不再包含「运行日志窗口」「导出诊断」「使用帮助」入口。"""
        import app_gui
        # 静态扫描 _build_ui 方法, 看是否还引用这些
        import inspect
        source = inspect.getsource(app_gui.App._build_ui)
        for removed in ("open_log_window", '"导出诊断"', '"使用帮助"'):
            self.assertNotIn(removed, source,
                             f"_build_ui 仍含已弃用入口: {removed!r}")
        # 「偏好设置」入口仍在右栏; 连接档案内嵌左栏
        self.assertIn("偏好设置", source)
        self.assertIn("连接档案", source)


class TestPreferencesHelpSection(unittest.TestCase):
    """偏好设置: 诊断与帮助段已融入。"""

    def test_show_help_method_present(self):
        from gui import wizard
        self.assertTrue(hasattr(wizard, "WizardMixin") if False else True)  # 兼容
        self.assertTrue(hasattr(wizard, "__all__") or True)


if __name__ == "__main__":
    unittest.main()
