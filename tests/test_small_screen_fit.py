# -*- coding: utf-8 -*-
"""v5.0.1 小屏适配回归: 所有窗口高度钳制 + 主窗/偏好设置整页滚动。"""
import inspect
import unittest

from gui.scrollkit import fit_geometry


class _FakeWin:
    def __init__(self, screen_h):
        self._sh = screen_h

    def winfo_screenheight(self):
        return self._sh


class TestFitGeometry(unittest.TestCase):
    def test_tall_window_clamped(self):
        # 设计 780, 屏幕 800 → 可视区 690 → 钳到 690
        self.assertEqual(fit_geometry(_FakeWin(800), 760, 780), "760x690")

    def test_small_window_untouched(self):
        self.assertEqual(fit_geometry(_FakeWin(800), 460, 300), "460x300")

    def test_big_screen_full_height(self):
        self.assertEqual(fit_geometry(_FakeWin(1200), 760, 780), "760x780")

    def test_min_h_floor(self):
        # 极小屏也不低于 min_h
        self.assertEqual(fit_geometry(_FakeWin(500), 680, 800, min_h=520), "680x520")


class TestAllWindowsClamped(unittest.TestCase):
    """每个会超高的窗口都必须走 fit_geometry。"""

    def _src(self, cls, meth):
        return inspect.getsource(getattr(cls, meth))

    def test_tunnel_ready(self):
        from gui.tunnel_ui import TunnelUiMixin
        self.assertIn("fit_geometry", self._src(TunnelUiMixin, "_show_tunnel_ready"))

    def test_vpn_dialog(self):
        from gui.tunnel_ui import TunnelUiMixin
        self.assertIn("fit_geometry", self._src(TunnelUiMixin, "_show_vpn_upstream_dialog"))

    def test_router_windows(self):
        from gui.router_tools import RouterToolsMixin
        self.assertIn("fit_geometry", self._src(RouterToolsMixin, "show_router_assessment"))
        self.assertIn("fit_geometry", self._src(RouterToolsMixin, "show_router_relay_window"))
        from gui.router_proxy import RouterProxyMixin
        self.assertIn("fit_geometry", self._src(RouterProxyMixin, "show_router_proxy_window"))

    def test_speed_hotspot_report(self):
        from gui.speed_window import SpeedWindowMixin
        self.assertIn("fit_geometry", self._src(SpeedWindowMixin, "show_speed_test"))
        from gui.feature_windows import FeatureWindowsMixin
        self.assertIn("fit_geometry", self._src(FeatureWindowsMixin, "open_hotspot_window"))
        self.assertIn("fit_geometry", self._src(FeatureWindowsMixin, "open_report_window"))

    def test_prefs_scrolled_and_clamped(self):
        from gui.preferences import PreferencesMixin
        src = self._src(PreferencesMixin, "show_preferences")
        self.assertIn("fit_geometry", src)
        self.assertIn("make_scrollable", src)

    def test_wizard_and_help(self):
        from gui.wizard import WizardMixin
        self.assertIn("fit_geometry", self._src(WizardMixin, "show_wizard"))
        self.assertIn("fit_geometry", self._src(WizardMixin, "show_help"))

    def test_main_window_scrolled(self):
        from app_gui import App
        src = inspect.getsource(App._build_ui)
        self.assertIn("make_scrollable", src)


if __name__ == "__main__":
    unittest.main()
