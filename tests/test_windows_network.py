import unittest
from unittest.mock import patch

import keepalive_core as core


class WindowsNetworkHelpersTests(unittest.TestCase):
    def test_physical_route_ignores_on_link_vpn_default(self):
        routes = """Network Destination Netmask Gateway Interface Metric
0.0.0.0 0.0.0.0 192.168.31.1 192.168.31.145 1000
0.0.0.0 0.0.0.0 On-link 10.20.228.45 2
"""
        with patch.object(core.netinfo.common, "IS_MACOS", False), \
                patch.object(core.netinfo.common, "IS_WINDOWS", True), \
                patch.object(core.netinfo, "_run_decode", return_value=routes):
            self.assertEqual(core.get_physical_route(),
                             ("192.168.31.1", "192.168.31.145"))
            self.assertEqual(core.get_gateway(), "192.168.31.1")

    def test_http_get_binds_windows_interface(self):
        response = type("Result", (), {"returncode": 0,
                        "stdout": b"<title>logout</title>\n200", "stderr": b""})()
        with patch.object(core.netinfo.common, "IS_MACOS", False), \
                patch.object(core.netinfo.common, "IS_WINDOWS", True), \
                patch.object(core.netinfo, "get_physical_interface", return_value="192.168.31.145"), \
                patch.object(core.subprocess, "run", return_value=response) as run:
            status, body = core.http_get("http://192.168.16.3/", physical=True)
        self.assertEqual((status, body), (200, b"<title>logout</title>"))
        self.assertIn("--interface", run.call_args.args[0])
        self.assertIn("192.168.31.145", run.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
