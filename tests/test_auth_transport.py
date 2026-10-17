import unittest
from unittest.mock import patch

from core import auth, common, netinfo


class AuthTransportPrivacyTests(unittest.TestCase):
    PROFILE = {
        "auth_url": "http://192.0.2.10/",
        "username": "privacy-user",
        "password": "privacy-pass",
        "login_type": "teacher",
    }

    def test_curl_login_url_is_sent_via_stdin_not_process_arguments(self):
        response = type("Result", (), {
            "returncode": 0,
            "stdout": b"dr1003\n200",
            "stderr": b"",
        })()
        with patch.object(common, "IS_MACOS", True), \
                patch.object(common, "IS_WINDOWS", False), \
                patch.object(netinfo, "get_physical_interface", return_value="en0"), \
                patch.object(auth.subprocess, "run", return_value=response) as run:
            self.assertTrue(auth.try_login(self.PROFILE))

        args = run.call_args.args[0]
        config = run.call_args.kwargs["input"].decode("ascii")
        self.assertIn("--config", args)
        self.assertEqual(args[-1], "-")
        self.assertNotIn(self.PROFILE["username"], " ".join(args))
        self.assertNotIn(self.PROFILE["password"], " ".join(args))
        self.assertIn("DDDDD=privacy-user", config)
        self.assertIn("upass=privacy-pass", config)
        self.assertIn("referer = \"http://192.0.2.10/\"", config)

    def test_urllib_login_uses_origin_referer_without_credentials(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            @staticmethod
            def read():
                return b"dr1003"

        with patch.object(common, "IS_MACOS", False), \
                patch.object(common, "IS_WINDOWS", False), \
                patch.object(auth._DIRECT_OPENER, "open", return_value=Response()) as open_request:
            self.assertTrue(auth.try_login(self.PROFILE))

        request = open_request.call_args.args[0]
        self.assertIn("upass=privacy-pass", request.full_url)
        self.assertEqual(request.get_header("Referer"), "http://192.0.2.10/")


if __name__ == "__main__":
    unittest.main()
