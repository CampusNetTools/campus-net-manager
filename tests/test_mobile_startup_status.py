"""Initial Android network status must always reach a user-visible result."""
import unittest
from unittest.mock import Mock

from mobile.startup_status import initial_network_status


class MobileStartupStatusTests(unittest.TestCase):
    def _auth(self, *, reachable=True, authenticated=True, internet=True):
        auth = Mock()
        auth.auth_reachable.return_value = reachable
        auth.check_auth.return_value = authenticated
        auth.check_internet.return_value = internet
        return auth

    def test_outside_campus_returns_terminal_status_without_extra_probes(self):
        auth = self._auth(reachable=False)

        status = initial_network_status(auth, "http://portal.invalid/")

        self.assertEqual(status, ("非校园网环境（认证服务器不可达）", None, None))
        auth.check_auth.assert_not_called()
        auth.check_internet.assert_not_called()

    def test_online_authenticated_status(self):
        self.assertEqual(
            initial_network_status(self._auth(), "http://portal.invalid/"),
            ("校园网在线（已认证 · 可上网）", True, None),
        )

    def test_authenticated_without_internet_status(self):
        self.assertEqual(
            initial_network_status(
                self._auth(internet=False), "http://portal.invalid/"),
            ("已认证但外网不通", False, None),
        )

    def test_unauthenticated_status(self):
        self.assertEqual(
            initial_network_status(
                self._auth(authenticated=False), "http://portal.invalid/"),
            ("校园网未认证（需要登录）", False, None),
        )

    def test_probe_exception_returns_visible_error_instead_of_staying_loading(self):
        auth = self._auth()
        auth.auth_reachable.side_effect = TimeoutError

        status = initial_network_status(auth, "http://portal.invalid/")

        self.assertEqual(status, ("网络状态检测失败，请稍后重试", False, "TimeoutError"))


if __name__ == "__main__":
    unittest.main()
