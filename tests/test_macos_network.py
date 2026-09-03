import unittest
import os
import tempfile
from unittest.mock import patch

import keepalive_core as core


class MacNetworkHelpersTests(unittest.TestCase):
    def test_get_ssid_from_macos_networksetup(self):
        def run(cmd, timeout=10):
            if cmd[1] == "-listallhardwareports":
                return "Hardware Port: Wi-Fi\nDevice: en0\nEthernet Address: aa:bb:cc:dd:ee:ff\n"
            if cmd[1] == "-getairportnetwork":
                return "Current Wi-Fi Network: Campus-Router\n"
            return ""

        with patch.object(core, "IS_MACOS", True), patch.object(core, "_run_decode", side_effect=run):
            self.assertEqual(core.get_ssid(), "Campus-Router")

    def test_get_gateway_ignores_vpn_default_route(self):
        routes = """Routing tables
Internet:
Destination        Gateway            Flags               Netif
default            link#25            UCSg                utun8
default            192.168.50.1      UGScIg              en0
"""
        with patch.object(core, "IS_MACOS", True), patch.object(core, "_run_decode", return_value=routes):
            self.assertEqual(core.get_gateway(), "192.168.50.1")
            self.assertEqual(core.get_physical_interface(), "en0")

    def test_auth_check_uses_physical_interface_with_vpn(self):
        response = type("Result", (), {"returncode": 0, "stdout": b"<title>logout</title>\n200"})()
        with patch.object(core, "IS_MACOS", True), \
                patch.object(core, "get_physical_interface", return_value="en0"), \
                patch.object(core.subprocess, "run", return_value=response) as run:
            status, body = core.http_get("http://192.168.16.3/", physical=True)
        self.assertEqual((status, body), (200, b"<title>logout</title>"))
        self.assertIn("--interface", run.call_args.args[0])
        self.assertIn("en0", run.call_args.args[0])

    def test_auth_server_detection_bypasses_vpn(self):
        response = type("Result", (), {
            "returncode": 0,
            "stdout": b"HTTP/1.1 302 Found\r\nLocation: http://192.168.16.3/index.jsp\r\n\r\n",
            "stderr": b""})()
        with patch.object(core, "IS_MACOS", True), \
                patch.object(core, "get_physical_interface", return_value="en0"), \
                patch.object(core.subprocess, "run", return_value=response) as run:
            self.assertEqual(core.detect_auth_server(), "http://192.168.16.3/")
        self.assertIn("--interface", run.call_args.args[0])

    def test_enabling_autostart_does_not_launch_second_instance(self):
        with tempfile.TemporaryDirectory() as temp_home, \
                patch.object(core, "IS_MACOS", True), \
                patch.object(core.os.path, "expanduser", return_value=temp_home), \
                patch.object(core.subprocess, "run") as run:
            self.assertTrue(core.set_autostart(True))
            plist = os.path.join(temp_home, "Library", "LaunchAgents",
                                 "com.campusnettools.campusnetmanager.plist")
            self.assertTrue(os.path.exists(plist))
            run.assert_not_called()

    def test_gateway_mac_uses_macos_arp_format(self):
        arp = "? (192.168.50.1) at d4:46:3a:7b:ee:58 on en0 ifscope [ethernet]\n"
        with patch.object(core, "_run_decode", return_value=arp), patch.object(core, "get_gateway", return_value="192.168.50.1"):
            self.assertEqual(core.get_gateway_mac(), "d4:46:3a:7b:ee:58")


if __name__ == "__main__":
    unittest.main()
