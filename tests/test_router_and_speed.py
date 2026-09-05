import unittest
from types import SimpleNamespace
from unittest.mock import patch

import keepalive_core as core
from core import auth, common, history, matching, netinfo, speed, sysutils  # noqa: F401



class RouterAssessmentTests(unittest.TestCase):
    def test_parse_upnp_description_extracts_model(self):
        xml = b"""<?xml version='1.0'?>
        <root xmlns='urn:schemas-upnp-org:device-1-0'><device>
          <friendlyName>Living Router</friendlyName>
          <manufacturer>Example</manufacturer><modelName>XR-1000</modelName>
          <modelNumber>v2</modelNumber>
        </device></root>"""
        info = core.parse_upnp_device_description(xml)
        self.assertEqual(info["manufacturer"], "Example")
        self.assertEqual(info["modelName"], "XR-1000")
        self.assertEqual(info["modelNumber"], "v2")

    def test_flash_never_becomes_automatic(self):
        result = core.evaluate_flash_readiness(
            "XR-1000", "v2", official_match=True, checksum_verified=True,
            backup_ready=True, recovery_ready=True)
        self.assertTrue(result["ready_for_confirmation"])
        self.assertFalse(result["automatic_flash_allowed"])

    def test_missing_revision_blocks_confirmation(self):
        result = core.evaluate_flash_readiness("XR-1000", "")
        self.assertFalse(result["ready_for_confirmation"])
        self.assertIn("已确认硬件版本", result["missing"])


class SpeedTestTests(unittest.TestCase):
    def test_timeout_after_useful_transfer_is_kept_as_speed_sample(self):
        output = (b"200\t0.001\t0.010\t0.030\t0.031\t0.050\t25.0\t"
                  b"3012480\t0\t172.66.0.218")
        completed = SimpleNamespace(returncode=28, stdout=output,
                                    stderr=b"curl: (28) Operation timed out")
        with patch.object(core.subprocess, "run", return_value=completed):
            result = core._curl_speed_request(
                "https://speed.cloudflare.com/__down?bytes=10000000",
                timeout=25, allow_timed_sample=True)
        self.assertTrue(result["timed_sample"])
        self.assertEqual(result["downloaded"], 3012480.0)

    def test_speed_plan_automatically_compares_when_vpn_is_active(self):
        with patch.object(common, "IS_MACOS", True), \
                patch.object(netinfo, "vpn_active", return_value=True):
            plan = core.automatic_speed_test_plan()
        self.assertTrue(plan["compare"])
        self.assertEqual(plan["paths"], ("current", "physical"))

    def test_speed_plan_uses_one_path_without_vpn(self):
        with patch.object(common, "IS_MACOS", True), \
                patch.object(netinfo, "vpn_active", return_value=False):
            plan = core.automatic_speed_test_plan()
        self.assertFalse(plan["compare"])
        self.assertEqual(plan["paths"], ("current",))

    def test_speed_calculation_and_vpn_label(self):
        replies = [
            {"ttfb": 0.030, "total": 0.04, "downloaded": 0, "uploaded": 0, "remote_ip": "1.1.1.1"},
            {"ttfb": 0.020, "total": 0.03, "downloaded": 0, "uploaded": 0, "remote_ip": "1.1.1.1"},
            {"ttfb": 0.040, "total": 0.05, "downloaded": 0, "uploaded": 0, "remote_ip": "1.1.1.1"},
            {"ttfb": 0.025, "total": 0.04, "downloaded": 0, "uploaded": 0, "remote_ip": "1.1.1.1"},
            {"ttfb": 0.035, "total": 0.04, "downloaded": 0, "uploaded": 0, "remote_ip": "1.1.1.1"},
            {"ttfb": 0.028, "total": 0.04, "downloaded": 0, "uploaded": 0, "remote_ip": "1.1.1.1"},
            {"ttfb": 0.02, "total": 2.0, "downloaded": 10000000, "uploaded": 0, "remote_ip": "1.1.1.1"},
            {"ttfb": 0.02, "total": 1.0, "downloaded": 0, "uploaded": 2000000, "remote_ip": "1.1.1.1"},
        ]
        with patch.object(speed, "_curl_speed_request", side_effect=replies), \
                patch.object(netinfo, "vpn_active", return_value=True):
            result = core.run_speed_test("current")
        self.assertEqual(result["latency_ms"], 30.0)
        self.assertEqual(result["download_mbps"], 40.0)
        self.assertEqual(result["upload_mbps"], 16.0)
        self.assertEqual(result["success_rate"], 100.0)
        self.assertIn("quality_score", result)
        self.assertIn("经过 VPN", result["path_label"])

    def test_physical_mode_binds_interface(self):
        reply = {"ttfb": 0.01, "total": 1.0, "downloaded": 10000000,
                 "uploaded": 2000000, "remote_ip": "1.1.1.1"}
        with patch.object(common, "IS_MACOS", True), \
                patch.object(speed, "_curl_speed_request", return_value=reply) as request, \
                patch.object(netinfo, "get_physical_interface", return_value="en0"):
            result = core.run_speed_test("physical")
        self.assertEqual(result["interface"], "en0")
        self.assertTrue(all(call.kwargs.get("physical") for call in request.call_args_list))

    def test_latency_uses_connect_time_not_slow_first_byte(self):
        sample = {"lookup": 0.010, "connect": 0.035, "appconnect": 0.080, "ttfb": 1.2}
        self.assertAlmostEqual(core._latency_from_timing(sample), 25.0)

    def test_latency_corrects_local_tun_connect_time(self):
        sample = {"lookup": 0.002, "connect": 0.0025, "appconnect": 0.4025, "ttfb": 1.2}
        self.assertAlmostEqual(core._latency_from_timing(sample), 200.0)

    def test_network_paths_separate_vpn_and_physical(self):
        with patch.object(common, "IS_MACOS", True), \
                patch.object(netinfo, "vpn_active", return_value=True), \
                patch.object(auth, "check_internet", side_effect=lambda physical=False: physical):
            paths = core.check_network_paths()
        self.assertEqual(paths, {"vpn": True, "current": False, "physical": True})


class KeepAliveStatusTests(unittest.TestCase):
    def test_successful_auto_login_immediately_rechecks_dashboard_status(self):
        profile = core.default_profile("测试档案")
        profile.update({"username": "user", "password": "secret"})
        cfg = {"profiles": [profile], "active_profile": profile["name"],
               "history_enabled": False}
        statuses = []
        environments = []
        daemon = core.KeepAliveDaemon(
            cfg,
            on_status=lambda paths, authed, checked, *rest: statuses.append((paths, authed, checked)),
            on_env=lambda *args: environments.append(args))
        offline = {"vpn": True, "current": True, "physical": True}
        online = {"vpn": True, "current": True, "physical": True}
        with patch.object(sysutils, "log", side_effect=lambda text: text), \
                patch.object(netinfo, "get_connection_mode", return_value=("wired", "")), \
                patch.object(netinfo, "get_gateway", return_value="10.12.255.254"), \
                patch.object(matching, "match_profile", return_value=profile), \
                patch.object(auth, "auth_reachable", return_value=True), \
                patch.object(auth, "check_auth", side_effect=[False, True]), \
                patch.object(auth, "check_network_paths", side_effect=[offline, online]), \
                patch.object(auth, "ensure_login", return_value=True), \
                patch.object(history, "record_network_history"), \
                patch.object(daemon, "_wait_or_break", return_value=True):
            daemon.run()
        self.assertEqual(len(statuses), 2)
        self.assertFalse(statuses[0][1])
        self.assertTrue(statuses[1][1])
        self.assertGreaterEqual(len(environments), 2)


if __name__ == "__main__":
    unittest.main()
