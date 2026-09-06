# -*- coding: utf-8 -*-
"""档案窗口按类型动态表单: wifi 档案只填必填字段, save_profile 校验按类型。"""
import unittest
from unittest.mock import patch, MagicMock

import keepalive_core as core  # noqa: E402


class WifiProfileSaveTests(unittest.TestCase):
    def setUp(self):
        # 模拟 App: 仅有 wifi 类型必填字段
        self.app = MagicMock()
        self.app.cfg = {"profiles": [], "active_profile": "", "auth_history": []}
        self.app._current_profile = lambda: None
        self.app.ent_name.get = lambda: "寝室华为"
        self.app.ent_ssid.get = lambda: "Huawei-Hi"
        self.app.ent_gw.get = lambda: "192.168.3.1"
        self.app.ent_user = None  # wifi 模式不存在
        self.app.ent_pass = None
        self.app.cmb_type = None
        self.app.cmb_auth = None
        self.app.btn_detect = None
        self.app.cmb_interval.get = lambda: "60"
        self.app.cmb_ptype.get = lambda: "普通WiFi/热点（只检测断网）"
        self.app._is_wifi_form = lambda: True
        # 替换 messagebox 与 save_config
        self._msgbox = patch("gui.profile_form.messagebox").start()
        self._savecfg = patch("gui.profile_form.core.save_config",
                             lambda *a, **kw: None).start()
        self._savesec = patch("gui.profile_form.core.keychain_set",
                             lambda *a, **kw: None).start()
        self.addCleanup(patch.stopall)

    def test_wifi_profile_saves_only_bind_fields(self):
        """wifi 档案保存后: 仅 ssid/gateway/name/interval/profile_type 有值, 不堆积空字段。"""
        from gui.profile_form import ProfileFormMixin
        fake = ProfileFormMixin.__new__(ProfileFormMixin)
        fake.cfg = self.app.cfg
        fake.ent_name = self.app.ent_name
        fake.ent_ssid = self.app.ent_ssid
        fake.ent_gw = self.app.ent_gw
        fake.cmb_interval = self.app.cmb_interval
        fake.cmb_ptype = self.app.cmb_ptype
        fake.ent_user = None
        fake.ent_pass = None
        fake.cmb_type = None
        fake.cmb_auth = None
        fake.btn_detect = None
        fake._is_wifi_form = lambda: True
        fake._log = lambda m: None
        fake._refresh_profile_list = lambda: None

        with patch.object(ProfileFormMixin, "_current_profile", return_value=None), \
                patch.object(core, "save_config", lambda *a, **kw: None):
            ProfileFormMixin.save_profile(fake)
        # 应新建一个 wifi 档案
        self.assertEqual(len(self.app.cfg["profiles"]), 1)
        prof = self.app.cfg["profiles"][0]
        self.assertEqual(prof["profile_type"], "wifi")
        self.assertEqual(prof["name"], "寝室华为")
        self.assertEqual(prof["ssid"], "Huawei-Hi")
        self.assertEqual(prof["gateway"], "192.168.3.1")
        self.assertEqual(prof["interval"], 60)
        # 关键: wifi 档案不应有 username/password/auth_url/login_type 残留
        self.assertEqual(prof.get("username", ""), "")
        self.assertEqual(prof.get("password", ""), "")
        self.assertEqual(prof.get("auth_url", ""), "")
        self.assertEqual(prof.get("login_type", ""), "")

    def test_wifi_profile_requires_ssid_or_gateway(self):
        """wifi 档案 ssid 与 gateway 都为空时拒绝保存, 提示用户绑定网络。"""
        from gui.profile_form import ProfileFormMixin
        fake = ProfileFormMixin.__new__(ProfileFormMixin)
        fake.cfg = self.app.cfg
        fake.ent_name = MagicMock(get=lambda: "x")
        fake.ent_ssid = MagicMock(get=lambda: "")
        fake.ent_gw = MagicMock(get=lambda: "")
        fake.cmb_interval = MagicMock(get=lambda: "60")
        fake.cmb_ptype = MagicMock(get=lambda: "普通WiFi/热点（只检测断网）")
        fake.ent_user = None
        fake.ent_pass = None
        fake.cmb_type = None
        fake.cmb_auth = None
        fake.btn_detect = None
        fake._is_wifi_form = lambda: True
        fake._log = lambda m: None
        fake._refresh_profile_list = lambda: None
        with patch.object(ProfileFormMixin, "_current_profile", return_value=None):
            ProfileFormMixin.save_profile(fake)
        self.assertEqual(self.app.cfg["profiles"], [])
        self._msgbox.showwarning.assert_called()


if __name__ == "__main__":
    unittest.main()
