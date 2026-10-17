import json
import plistlib
import unittest

from ikev2_profile import IKEv2GatewayNotReady, IKEv2ProfileController


class IKEv2ProfileTests(unittest.TestCase):
    def test_refuses_profile_without_authorized_gateway(self):
        controller = IKEv2ProfileController("10.12.72.55", "vpn.campusnet.local", b"certificate")
        with self.assertRaisesRegex(IKEv2GatewayNotReady, "尚未"):
            controller.create_device_profile("my_iphone")

    def test_profile_uses_ios_builtin_ikev2_and_unique_eap_credential(self):
        controller = IKEv2ProfileController(
            "10.12.72.55", "vpn.campusnet.local", b"der-ca-certificate",
            gateway_ready=True, swanctl_available=True, dns_servers=("1.1.1.1",),
        )
        profile = controller.create_device_profile("my_iphone")
        parsed = plistlib.loads(profile.mobileconfig)
        certificate, vpn = parsed["PayloadContent"]
        self.assertEqual(certificate["PayloadType"], "com.apple.security.root")
        self.assertEqual(vpn["PayloadType"], "com.apple.vpn.managed")
        self.assertEqual(vpn["VPNType"], "IKEv2")
        self.assertEqual(vpn["IKEv2"]["RemoteAddress"], "10.12.72.55")
        self.assertEqual(vpn["IKEv2"]["RemoteIdentifier"], "vpn.campusnet.local")
        self.assertEqual(vpn["IKEv2"]["AuthenticationMethod"], "None")
        self.assertEqual(vpn["IKEv2"]["ExtendedAuthEnabled"], 1)
        self.assertEqual(vpn["IKEv2"]["ServerCertificateCommonName"], "vpn.campusnet.local")
        self.assertEqual(vpn["IKEv2"]["AuthName"], profile.username)
        self.assertEqual(vpn["IKEv2"]["AuthPassword"], profile.password)
        self.assertEqual(vpn["IKEv2"]["IncludeAllNetworks"], 1)
        self.assertIn(profile.username, profile.swanctl_secret)
        self.assertIn(profile.password, profile.swanctl_secret)
        self.assertNotIn("校园网密码", profile.mobileconfig.decode("utf-8"))

        ca_profile = plistlib.loads(profile.ca_mobileconfig)
        self.assertEqual(len(ca_profile["PayloadContent"]), 1)
        self.assertEqual(ca_profile["PayloadContent"][0]["PayloadType"], "com.apple.security.root")
        self.assertNotIn("AuthPassword", repr(ca_profile))

        app_configuration = json.loads(profile.app_configuration)
        self.assertEqual(app_configuration["serverAddress"], "10.12.72.55")
        self.assertEqual(app_configuration["serverIdentifier"], "vpn.campusnet.local")
        self.assertEqual(app_configuration["username"], profile.username)
        self.assertEqual(app_configuration["password"], profile.password)
        self.assertNotIn(profile.password, repr(profile))

    def test_ca_certificate_is_required(self):
        controller = IKEv2ProfileController(
            "10.12.72.55", "vpn.campusnet.local", b"", gateway_ready=True, swanctl_available=True,
        )
        with self.assertRaisesRegex(IKEv2GatewayNotReady, "CA 证书"):
            controller.create_device_profile("my_iphone")

    def test_rejects_malformed_numeric_addresses_instead_of_treating_them_as_hosts(self):
        for host in ("999.1.1.1", "1..2.3", "2001::gg", "2001:db8::1%en0"):
            controller = IKEv2ProfileController(
                host, "vpn.campusnet.local", b"der-ca-certificate",
                gateway_ready=True, swanctl_available=True,
            )
            with self.subTest(host=host):
                self.assertFalse(controller.readiness()[0])

    def test_accepts_ipv6_and_rejects_non_ascii_dns_names(self):
        valid_controller = IKEv2ProfileController(
            "2001:db8::42", "vpn.campusnet.local", b"der-ca-certificate",
            gateway_ready=True, swanctl_available=True,
        )
        invalid_controller = IKEv2ProfileController(
            "10.12.72.55", "vṕn.campusnet.local", b"der-ca-certificate",
            gateway_ready=True, swanctl_available=True,
        )

        self.assertTrue(valid_controller.readiness()[0])
        self.assertFalse(invalid_controller.readiness()[0])
