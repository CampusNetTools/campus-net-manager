# -*- coding: utf-8 -*-
"""v4.0.4 路由器代理独立窗口 Mixin 验证。
(v5.0.0 起 v4 主界面 10 宫格已由双栏布局取代, 相关断言迁移到 test_v5_main_layout.py)
"""
import inspect
import unittest


class TestRouterProxyWindow(unittest.TestCase):
    """v4.0.4 新增「路由器代理」独立窗口 Mixin."""

    def test_mixin_exists(self):
        """RouterProxyMixin 在 gui/router_proxy.py 里存在."""
        from gui.router_proxy import RouterProxyMixin
        self.assertTrue(hasattr(RouterProxyMixin, "show_router_proxy_window"))

    def test_window_has_required_sections(self):
        """show_router_proxy_window 必须含 A 识别 / B 探测 / C 装固件 / D 手机配置 四段."""
        from gui.router_proxy import RouterProxyMixin
        src = inspect.getsource(RouterProxyMixin.show_router_proxy_window)
        # A. 路由器识别 + 固件查询
        self.assertIn("router_fingerprint", src)
        self.assertIn("lookup_firmware_urls", src)
        # B. 端口探测
        self.assertIn("probe_router_proxy", src)
        self.assertIn("探测", src)
        # C. 固件分步
        self.assertIn("OpenWrt", src)
        self.assertIn("Padavan", src)
        self.assertIn("Merlin", src)
        self.assertIn("iKuaiOS", src)
        # D. 手机配置
        self.assertIn("iOS", src)
        self.assertIn("Android", src)

    def test_probe_router_proxy_signature(self):
        """probe_router_proxy 接收 ip + 可选 ports, 返回 dict 含 is_proxy."""
        from gui.router_proxy import probe_router_proxy
        # 探测本地不存在的地址, 应在 timeout 内返回 is_proxy=False
        result = probe_router_proxy("127.0.0.1", ports=[39999], timeout=0.5)
        self.assertIn("is_proxy", result)
        self.assertIn("ip", result)
        self.assertIn("port", result)
        self.assertEqual(result["ip"], "127.0.0.1")

    def test_build_router_pac_format(self):
        """build_router_pac 输出的 PAC 含 FindProxyForURL 函数 + PROXY 行."""
        from gui.router_proxy import build_router_pac
        pac = build_router_pac("192.168.1.1", 8080)
        self.assertIn("FindProxyForURL", pac)
        self.assertIn("PROXY 192.168.1.1:8080", pac)

    def test_app_mixes_in_router_proxy(self):
        """App 必须继承 RouterProxyMixin, 否则主界面点不到新窗口."""
        from app_gui import App
        from gui.router_proxy import RouterProxyMixin
        self.assertTrue(issubclass(App, RouterProxyMixin),
                        "App 没继承 RouterProxyMixin, 主界面宫格会调用失败")


class TestTunnelReadyThreeCards(unittest.TestCase):
    """v4.0.4: 隧道共享窗口集成三种上游模式 (① 路由器中继 + ② 电脑直连 + ③ 路由器代理)."""

    def test_tunnel_ready_has_router_proxy_card(self):
        """_show_tunnel_ready 含 ③ 路由器代理段."""
        from gui.tunnel_ui import TunnelUiMixin
        src = inspect.getsource(TunnelUiMixin._show_tunnel_ready)
        self.assertIn("③ 路由器代理", src)
        self.assertIn("路由器自身开 HTTP 代理", src)
        self.assertIn("路由器 LAN IP", src)
        self.assertIn("代理端口", src)


if __name__ == "__main__":
    unittest.main()