import json
import os
import tempfile
import unittest
from unittest.mock import patch

import keepalive_core as core
from core import common, config  # noqa: F401



class LidaProfileTests(unittest.TestCase):
    def test_new_config_contains_lida_preset(self):
        with tempfile.TemporaryDirectory() as temp_dir, \
                patch.object(common, "CONFIG_PATH", os.path.join(temp_dir, "config.json")):
            cfg = core.load_config()
        profile = cfg["profiles"][0]
        self.assertEqual(profile["name"], "立达校园网")
        self.assertEqual(profile["preset"], core.LIDA_PROFILE_ID)
        self.assertEqual(profile["ssid"], "LIDA-UNIVERSITY")
        self.assertEqual(profile["auth_url"], "http://192.168.16.3/")
        self.assertEqual(profile["username"], "")
        self.assertEqual(profile["password"], "")

    def test_legacy_profile_is_upgraded_without_overwriting_credentials(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "config.json")
            with open(path, "w", encoding="utf-8") as handle:
                json.dump({"profiles": [{
                    "name": "校园网", "ssid": "", "username": "student",
                    "password": "secret", "login_type": "unicom",
                    "auth_url": core.DEFAULT_AUTH_URL, "interval": 300,
                }], "active_profile": "校园网"}, handle)
            with patch.object(common, "CONFIG_PATH", path), \
                    patch.object(config, "keychain_set", return_value=True):
                cfg = core.load_config()
        self.assertEqual(len(cfg["profiles"]), 1)
        profile = cfg["profiles"][0]
        self.assertEqual(profile["username"], "student")
        self.assertEqual(profile["password"], "secret")
        self.assertEqual(profile["login_type"], "unicom")
        self.assertEqual(profile["ssid"], core.LIDA_SSID)
        self.assertEqual(cfg["active_profile"], core.LIDA_PROFILE_NAME)

    def test_existing_custom_profiles_are_preserved(self):
        cfg = {"profiles": [{"name": "家里", "ssid": "Home", "auth_url": "http://10.0.0.1/"}],
               "active_profile": "家里"}
        self.assertTrue(core.ensure_lida_profile(cfg))
        self.assertEqual(len(cfg["profiles"]), 2)
        self.assertEqual(cfg["profiles"][1]["name"], "家里")
        self.assertEqual(cfg["active_profile"], "家里")


if __name__ == "__main__":
    unittest.main()
