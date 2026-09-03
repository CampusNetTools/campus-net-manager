import unittest
from unittest.mock import patch

import app_gui


class _Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class _Button:
    def configure(self, **kwargs):
        self.options = kwargs


class _Label(_Button):
    pass


class AutostartToggleTests(unittest.TestCase):
    def test_autostart_button_toggles_both_directions(self):
        fake = type("FakeApp", (), {})()
        fake.var_auto = _Value(False)
        fake.btn_auto = _Button()
        fake._log = lambda message: None
        fake._update_auto_btn = lambda: app_gui.App._update_auto_btn(fake)

        with patch.object(app_gui.core, "set_autostart", return_value=True) as setter:
            app_gui.App._toggle_autostart(fake)
            self.assertTrue(fake.var_auto.get())
            setter.assert_called_with(True)

            app_gui.App._toggle_autostart(fake)
            self.assertFalse(fake.var_auto.get())
            self.assertEqual(setter.call_args.args[0], False)


class NetworkStatusTests(unittest.TestCase):
    def test_vpn_failure_does_not_show_fake_online(self):
        fake = type("FakeApp", (), {})()
        fake.lbl_last = _Label()
        fake.lbl_net = _Label()
        fake.dot_net = _Label()
        app_gui.App.set_net(fake, {"vpn": True, "current": False, "physical": True}, True, "now")
        self.assertEqual(fake.lbl_net.options["text"], "网络: 校园网在线 (VPN异常)")

    def test_both_paths_online_are_reported(self):
        fake = type("FakeApp", (), {})()
        fake.lbl_last = _Label()
        fake.lbl_net = _Label()
        fake.dot_net = _Label()
        app_gui.App.set_net(fake, {"vpn": True, "current": True, "physical": True}, True, "now")
        self.assertEqual(fake.lbl_net.options["text"], "网络: VPN 与校园网在线")


if __name__ == "__main__":
    unittest.main()
