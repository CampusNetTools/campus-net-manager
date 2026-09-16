# -*- coding: utf-8 -*-
import base64
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import proxy_subscription as sub
from core import config


class ProxySubscriptionTests(unittest.TestCase):
    def test_base64_vless_and_hysteria2(self):
        lines = [
            "vless://abc@example.com:443?security=reality&type=tcp&pbk=key&sid=12&sni=example.com#A",
            "hysteria2://pass@example.net:8443?sni=example.net&insecure=1#B",
        ]
        raw = base64.b64encode("\n".join(lines).encode())
        nodes, rejected = sub.parse_subscription(raw)
        self.assertEqual(2, len(nodes))
        self.assertEqual(0, rejected)
        self.assertEqual("vless", nodes[0]["type"])
        self.assertEqual("hysteria2", nodes[1]["type"])
        self.assertTrue(nodes[0]["tls"])
        self.assertEqual("key", nodes[0]["reality-opts"]["public-key"])

    def test_duplicate_names_are_unique_and_unsupported_rejected(self):
        raw = ("vless://a@one.test:443#same\n"
               "vless://b@two.test:443#same\n"
               "ss://ignored@three.test:443#same")
        nodes, rejected = sub.parse_subscription(raw)
        self.assertEqual(["same", "same (2)"], [n["name"] for n in nodes])
        self.assertEqual(1, rejected)

    def test_generated_config_contains_no_subscription_url(self):
        nodes, _ = sub.parse_subscription("vless://abc@example.com:443#A")
        config, secret = sub.build_mihomo_config(nodes, "controller")
        self.assertIn("tproxy-port: 7891", config)
        self.assertIn("redir-port: 7892", config)
        self.assertIn("enhanced-mode: redir-host", config)
        self.assertNotIn("enhanced-mode: fake-ip", config)
        self.assertIn('name: "节点选择"', config)
        self.assertIn('DOMAIN-SUFFIX,cn,DIRECT', config)
        self.assertIn('GEOIP,CN,DIRECT', config)
        self.assertIn('MATCH,节点选择', config)
        self.assertIn('secret: "controller"', config)
        self.assertNotIn("subscription", config.lower())
        self.assertEqual("controller", secret)

    def test_rejects_non_https_fetch(self):
        with self.assertRaises(sub.SubscriptionError):
            sub.fetch_subscription("http://example.com/sub")

    def test_export_removes_subscription_and_router_tokens(self):
        exported = config.config_for_export({
            "profiles": [],
            "vpn_subscription": {"url_enc": "cipher"},
            "router_console": {"host": "192.168.31.1", "token_enc": "cipher", "token": "plain"},
        })
        self.assertNotIn("vpn_subscription", exported)
        self.assertEqual({"host": "192.168.31.1"}, exported["router_console"])

    def test_router_health_checks_require_exact_http_204(self):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for name in ("proxy-start.sh", "proxy-guard.sh", "proxy-config.sh"):
            with open(os.path.join(root, "router_assets", name), encoding="utf-8") as fh:
                source = fh.read()
            self.assertIn("%{http_code}", source, name)
            self.assertIn('"204"', source, name)


if __name__ == "__main__":
    unittest.main()
