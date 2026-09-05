import unittest
from unittest.mock import patch

import keepalive_core as core
from core import portal  # noqa: F401



class PortalDiscoveryTests(unittest.TestCase):
    def test_extracts_http_meta_and_javascript_redirects(self):
        source = "http://connectivitycheck.gstatic.com/generate_204"
        headers = "HTTP/1.1 302 Found\r\nLocation: http://10.0.0.2/eportal/?wlanac=1\r\n"
        body = "<meta http-equiv='refresh' content='0;url=http://10.0.0.3/login'>" \
               "<script>window.location='http://10.0.0.4/portal'</script>"
        urls = core._extract_redirect_urls(source, headers, body)
        self.assertIn("http://10.0.0.2/eportal/?wlanac=1", urls)
        self.assertIn("http://10.0.0.3/login", urls)
        self.assertIn("http://10.0.0.4/portal", urls)

    def test_discovers_multiple_private_portal_origins(self):
        def probe(item, physical=True):
            suffix = list(core.CAPTIVE_PROBES).index(item) % 2 + 2
            return {"probe": item, "status": 302,
                    "headers": "Location: http://192.168.16.%d/eportal/login\r\n" % suffix,
                    "body": "Dr.COM eportal"}
        with patch.object(portal, "_run_captive_probe", side_effect=probe):
            report = core.discover_auth_servers([])
        urls = [item["url"] for item in report["candidates"]]
        self.assertEqual(urls, ["http://192.168.16.2/", "http://192.168.16.3/"])
        self.assertFalse(report["online"])

    def test_expected_204_means_online_without_portal(self):
        def probe(item, physical=True):
            return {"probe": item, "status": item["status"], "headers": "",
                    "body": item.get("body", "")}
        with patch.object(portal, "_run_captive_probe", side_effect=probe):
            report = core.discover_auth_servers([])
        self.assertTrue(report["online"])
        self.assertEqual(report["candidates"], [])


if __name__ == "__main__":
    unittest.main()
