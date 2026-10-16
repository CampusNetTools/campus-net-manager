import json
import os
import tempfile
import threading
import unittest
from unittest.mock import Mock

from mobile.guard_service import (check_once, load_profile_data, read_profile,
                                  run_guard_service, state_is_fresh, write_profile)


class MobileGuardServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.profile_path = os.path.join(self.tmp.name, "profile.json")
        self.state_path = os.path.join(self.tmp.name, "guard-state.json")
        with open(self.profile_path, "w", encoding="utf-8") as stream:
            json.dump({"username": "student@example", "password": "secret-value",
                       "method": "cmcc", "auth_url": "http://campus.test/"}, stream)

    def tearDown(self):
        self.tmp.cleanup()

    def read_state(self):
        with open(self.state_path, encoding="utf-8") as stream:
            return json.load(stream)

    def test_profile_maps_mobile_method_to_core_auth_field(self):
        profile = read_profile(self.profile_path)
        self.assertEqual(profile["login_type"], "cmcc")
        self.assertEqual(profile["username"], "student@example")

    def test_profile_write_is_atomic_and_private(self):
        os.unlink(self.profile_path)
        write_profile(self.profile_path, {"username": "student@example", "password": "secret-value"})
        with open(self.profile_path, encoding="utf-8") as stream:
            self.assertEqual(json.load(stream)["password"], "secret-value")
        self.assertFalse(os.path.exists(self.profile_path + ".tmp"))
        if os.name == "posix":
            self.assertEqual(os.stat(self.profile_path).st_mode & 0o777, 0o600)

    def test_android_profile_is_encrypted_before_atomic_write(self):
        from unittest.mock import patch
        encrypted_path = os.path.join(self.tmp.name, "profile.enc")
        profile = {"username": "student@example", "password": "secret-value"}
        serialized = json.dumps(profile, ensure_ascii=False)
        with patch("mobile.guard_service._android_encrypt", return_value="v1:opaque-ciphertext") as encrypt:
            write_profile(encrypted_path, profile)
        encrypt.assert_called_once_with(serialized)
        with open(encrypted_path, encoding="utf-8") as stream:
            stored = stream.read()
        self.assertEqual(stored, "v1:opaque-ciphertext")
        self.assertNotIn("student@example", stored)
        self.assertNotIn("secret-value", stored)

    def test_android_profile_load_decrypts_before_json_parse(self):
        from unittest.mock import patch
        encrypted_path = os.path.join(self.tmp.name, "profile.enc")
        with open(encrypted_path, "w", encoding="utf-8") as stream:
            stream.write("v1:opaque-ciphertext")
        plaintext = json.dumps({"username": "student@example", "password": "secret-value"})
        with patch("mobile.guard_service._android_decrypt", return_value=plaintext) as decrypt:
            profile = load_profile_data(encrypted_path)
        decrypt.assert_called_once_with("v1:opaque-ciphertext")
        self.assertEqual(profile["username"], "student@example")

    def test_online_status_does_not_write_credentials(self):
        client = Mock(auth_reachable=Mock(return_value=True),
                      check_auth=Mock(return_value=True),
                      check_internet=Mock(return_value=True))
        state = check_once(self.profile_path, self.state_path, auth_client=client)
        self.assertEqual(state["status"], "online")
        self.assertNotIn("username", state)
        self.assertNotIn("password", state)
        with open(self.state_path, encoding="utf-8") as stream:
            raw = stream.read()
        self.assertNotIn("student@example", raw)
        self.assertNotIn("secret-value", raw)

    def test_outside_campus_suspends_without_attempting_login(self):
        client = Mock(auth_reachable=Mock(return_value=False))
        state = check_once(self.profile_path, self.state_path, auth_client=client)
        self.assertEqual(state["status"], "outside-campus")
        client.ensure_login.assert_not_called()

    def test_disconnect_relogin_is_serial_and_rechecked(self):
        client = Mock(auth_reachable=Mock(return_value=True),
                      check_auth=Mock(side_effect=[False, True]),
                      check_internet=Mock(return_value=True),
                      ensure_login=Mock(return_value=True))
        state = check_once(self.profile_path, self.state_path, auth_client=client)
        self.assertEqual(state["status"], "online")
        client.ensure_login.assert_called_once()
        self.assertEqual(client.check_auth.call_count, 2)

    def test_service_checks_immediately_and_stops_cleanly(self):
        client = Mock(auth_reachable=Mock(return_value=True),
                      check_auth=Mock(return_value=True),
                      check_internet=Mock(side_effect=lambda: (stop.set() or True)))
        stop = threading.Event()
        run_guard_service(self.profile_path, self.state_path, stop_event=stop,
                          auth_client=client)
        client.auth_reachable.assert_called_once()
        self.assertEqual(self.read_state()["status"], "stopped")

    def test_stale_or_disabled_state_is_not_reported_as_running(self):
        self.assertFalse(state_is_fresh({"enabled": False, "checked_at": "2026-10-16T00:00:00Z"}))
        self.assertFalse(state_is_fresh({"enabled": True, "checked_at": "invalid"}))


if __name__ == "__main__":
    unittest.main()
