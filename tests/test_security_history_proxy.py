import json
import os
import tempfile
import unittest
import urllib.request
from unittest.mock import patch

import keepalive_core as core
import shared_proxy


class KeychainConfigTests(unittest.TestCase):
    def test_password_is_kept_out_of_config_and_restored_from_keychain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "config.json")
            cfg = {
                "profiles": [{
                    "name": core.LIDA_PROFILE_NAME, "preset": core.LIDA_PROFILE_ID,
                    "ssid": core.LIDA_SSID, "username": "student", "password": "secret",
                    "login_type": "cmcc", "auth_url": core.DEFAULT_AUTH_URL, "interval": 60,
                }],
                "active_profile": core.LIDA_PROFILE_NAME,
                "auth_history": [core.DEFAULT_AUTH_URL],
            }
            core.ensure_preferences(cfg)
            with patch.object(core, "IS_MACOS", True), \
                    patch.object(core, "CONFIG_PATH", path), \
                    patch.object(core, "keychain_set", return_value=True):
                core.save_config(cfg, sync_secrets=True)
            with open(path, "r", encoding="utf-8") as handle:
                stored = json.load(handle)
            self.assertEqual(stored["profiles"][0]["password"], "")
            self.assertEqual(stored["profiles"][0]["password_store"], "keychain")
            with patch.object(core, "IS_MACOS", True), \
                    patch.object(core, "CONFIG_PATH", path), \
                    patch.object(core, "keychain_get", return_value="secret"):
                loaded = core.load_config()
            self.assertEqual(loaded["profiles"][0]["password"], "secret")

    def test_safe_export_never_contains_password_or_keychain_id(self):
        exported = core.config_for_export({"profiles": [{
            "name": "test", "password": "secret", "secret_id": "private",
            "password_store": "keychain",
        }]})
        self.assertEqual(exported["profiles"][0]["password"], "")
        self.assertNotIn("secret_id", exported["profiles"][0])


class NetworkHistoryTests(unittest.TestCase):
    def test_history_is_opt_in_and_has_plain_language_summary(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
                patch.object(core, "HISTORY_PATH", os.path.join(temp_dir, "history.jsonl")):
            self.assertFalse(core.record_network_history({"history_enabled": False}, "online", "正常"))
            cfg = {"history_enabled": True}
            core.record_network_history(cfg, "online", "网络正常")
            core.record_network_history(cfg, "disconnect", "检测到掉线")
            core.record_network_history(cfg, "recovery", "已自动恢复")
            report = core.summarize_network_history()
        self.assertEqual(report["counts"]["disconnect"], 1)
        self.assertEqual(report["counts"]["recovery"], 1)
        self.assertIn("波动", report["summary"])

    def test_notification_master_and_category_switches(self):
        self.assertFalse(core.notification_enabled(
            {"notifications": {"enabled": False, "failure": True}}, "failure"))
        self.assertFalse(core.notification_enabled(
            {"notifications": {"enabled": True, "failure": False}}, "failure"))
        self.assertTrue(core.notification_enabled(
            {"notifications": {"enabled": True, "recovery": True}}, "recovery"))

    def test_disabling_notification_master_clears_every_category(self):
        settings = core.normalized_notification_settings(False, {
            "disconnect": True, "recovery": True, "failure": True, "device": True,
        })
        self.assertFalse(settings["enabled"])
        self.assertFalse(any(value for key, value in settings.items() if key != "enabled"))


class SharedProxySetupTests(unittest.TestCase):
    def test_setup_page_and_pac_are_public_but_proxy_stays_protected(self):
        import time
        asked = []
        proxy = shared_proxy.SharedProxy(port=0, host="127.0.0.1", pac_host="127.0.0.1",
                                         on_ask=lambda ip: asked.append(ip) or False)
        proxy.start()
        try:
            time.sleep(0.3)  # 等待监听线程就绪
            self.assertTrue(shared_proxy.check_setup_page("127.0.0.1", proxy.port))
            # 绕过系统代理(环境可能设置了 http_proxy), 直连本机端口
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open("http://127.0.0.1:%d/proxy.pac" % proxy.port) as response:
                self.assertIn(b"FindProxyForURL", response.read())
            self.assertEqual(asked, [])
        finally:
            proxy.stop()


if __name__ == "__main__":
    unittest.main()
