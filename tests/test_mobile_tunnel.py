import datetime as dt
import json
import unittest
import urllib.parse
import base64

from mobile_tunnel import PairingController, GatewayNotReady


class MobileTunnelTests(unittest.TestCase):
    def test_no_qr_before_safe_gateway_is_ready(self):
        pair = PairingController("10.12.72.55")
        with self.assertRaisesRegex(GatewayNotReady, "尚未安装"):
            pair.create_qr_url()

    def test_pairing_token_is_short_lived_and_one_time(self):
        pin = "a" * 64
        pair = PairingController("10.12.72.55", certificate_pin=pin, gateway_ready=True)
        now = dt.datetime(2026, 9, 8, tzinfo=dt.timezone.utc)
        url = pair.create_qr_url(now)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        payload = json.loads(base64.b64decode(query["payload"][0]))
        self.assertEqual(payload["gatewayHost"], "10.12.72.55")
        self.assertNotIn("username", payload)
        self.assertNotIn("password", payload)
        self.assertTrue(pair.redeem(payload["enrollmentToken"], now))
        self.assertFalse(pair.redeem(payload["enrollmentToken"], now))
        expired = pair.create_qr_url(now)
        old_token = json.loads(base64.b64decode(urllib.parse.parse_qs(urllib.parse.urlsplit(expired).query)["payload"][0]))["enrollmentToken"]
        self.assertFalse(pair.redeem(old_token, now + dt.timedelta(seconds=61)))
