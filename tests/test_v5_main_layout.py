# -*- coding: utf-8 -*-
"""v5.0.0 主界面双栏布局回归。
v5 排版 = v2 双栏(左=连接档案内嵌表单 / 右=功能导航分组) + v4 全功能整合。
"""
import inspect
import unittest


class TestV5MainLayout(unittest.TestCase):
    """主窗口 _build_ui 静态结构断言。"""

    def _src(self):
        from app_gui import App
        return inspect.getsource(App._build_ui)

    def test_left_column_profile_form_embedded(self):
        """左栏: 连接档案内嵌表单 (v2 风格回归)。"""
        src = self._src()
        self.assertIn("连接档案", src)
        self.assertIn("cmb_profile", src)
        self.assertIn("cmb_ptype", src)
        self.assertIn("_profile_form_host", src)
        self.assertIn("保存档案", src)
        self.assertIn("立即检测", src)
        self.assertIn("导入配置", src)
        self.assertIn("导出配置", src)
        self.assertIn("自动探查当前网络", src)

    def test_right_column_nav_groups(self):
        """右栏: 功能导航按场景分组, v4 全功能保留。"""
        src = self._src()
        # 连接组
        self.assertIn("启动守护", src)
        self.assertIn("开机自启", src)
        # 共享上网组
        self.assertIn("隧道共享", src)
        self.assertIn("热点分享", src)
        self.assertIn("网络控制台", src)
        # VPN 加速组 (v5 新增)
        self.assertIn("VPN 加速", src)
        self.assertIn("配置 VPN 代理", src)
        self.assertIn("_vpn_preset_local", src)
        self.assertIn("_vpn_disable", src)
        # 路由器组
        self.assertIn("路由器中继", src)
        self.assertIn("路由器代理", src)
        self.assertIn("路由器检测", src)
        # 工具组
        self.assertIn("网络测速", src)
        self.assertIn("新手向导", src)
        self.assertIn("偏好设置", src)

    def test_log_collapsible(self):
        """底部日志可收起/展开 (v2 风格回归)。"""
        src = self._src()
        self.assertIn("btn_log_toggle", src)
        self.assertIn("log_expanded", src)

    def test_old_grid_removed(self):
        """v4 宫格已删除, 功能入口统一到右栏导航。"""
        from app_gui import App
        self.assertFalse(hasattr(App, "_build_feature_grid"))
        self.assertFalse(hasattr(App, "_feature_card"))


class TestV5ProfileWindowCompat(unittest.TestCase):
    """open_profile_window 兼容行为: 不再开独立窗口, 只置前主窗。"""

    def test_no_toplevel_creation(self):
        from gui.feature_windows import FeatureWindowsMixin
        src = inspect.getsource(FeatureWindowsMixin.open_profile_window)
        self.assertNotIn("Toplevel", src)
        self.assertIn("lift", src)


if __name__ == "__main__":
    unittest.main()
