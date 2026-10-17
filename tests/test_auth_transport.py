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
                patch.object(auth._LOGIN_OPENER, "open", return_value=Response()) as open_request:
            self.assertTrue(auth.try_login(self.PROFILE))

        request = open_request.call_args.args[0]
        self.assertIn("upass=privacy-pass", request.full_url)
        self.assertEqual(request.get_header("Referer"), "http://192.0.2.10/")

    def test_https_portal_is_not_downgraded_on_urllib_path(self):
        class Response:
            status = 200

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            @staticmethod
            def read():
                return b"dr1003"

        profile = dict(self.PROFILE, auth_url="https://campus.example:8443/portal")
        with patch.object(common, "IS_MACOS", False), \
                patch.object(common, "IS_WINDOWS", False), \
                patch.object(auth._LOGIN_OPENER, "open", return_value=Response()) as open_request:
            self.assertTrue(auth.try_login(profile))

        request = open_request.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://campus.example:8443/drcom/login?"))
        self.assertEqual(request.get_header("Referer"), "https://campus.example:8443/")

    def test_https_portal_is_not_downgraded_on_curl_path(self):
        response = type("Result", (), {
            "returncode": 0,
            "stdout": b"dr1003\n200",
            "stderr": b"",
        })()
        profile = dict(self.PROFILE, auth_url="https://[2001:db8::8]:8443/portal")
        with patch.object(common, "IS_MACOS", True), \
                patch.object(common, "IS_WINDOWS", False), \
                patch.object(netinfo, "get_physical_interface", return_value="en0"), \
                patch.object(auth.subprocess, "run", return_value=response) as run:
            self.assertTrue(auth.try_login(profile))

        config = run.call_args.kwargs["input"].decode("ascii")
        self.assertIn('url = "https://[2001:db8::8]:8443/drcom/login?', config)
        self.assertIn('referer = "https://[2001:db8::8]:8443/"', config)

    def test_rejects_unsupported_scheme_and_userinfo_without_request(self):
        with patch.object(auth._LOGIN_OPENER, "open") as open_request:
            for auth_url in ("ftp://campus.example/", "https://user:pass@campus.example/"):
                with self.subTest(auth_url=auth_url):
                    self.assertFalse(auth.try_login(dict(self.PROFILE, auth_url=auth_url)))
        open_request.assert_not_called()

    def test_https_login_refuses_redirect_to_http(self):
        handler = auth._NoHttpsDowngradeRedirect()
        request = auth.urllib.request.Request("https://campus.example/drcom/login")
        with self.assertRaises(auth.urllib.error.HTTPError) as raised:
            handler.redirect_request(
                request, None, 302, "Found",
                {"Location": "http://campus.example/drcom/login"},
                "http://campus.example/drcom/login",
            )
        raised.exception.close()


if __name__ == "__main__":
    unittest.main()
