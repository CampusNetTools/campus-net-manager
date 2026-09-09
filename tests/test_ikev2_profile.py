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
        self.assertEqual(vpn["IKEv2"]["AuthenticationMethod"], "Certificate")
        self.assertEqual(vpn["IKEv2"]["ExtendedAuthEnabled"], 1)
        self.assertEqual(vpn["IKEv2"]["AuthName"], profile.username)
        self.assertEqual(vpn["IKEv2"]["AuthPassword"], profile.password)
        self.assertEqual(vpn["IKEv2"]["IncludeAllNetworks"], 1)
        self.assertIn(profile.username, profile.swanctl_secret)
        self.assertIn(profile.password, profile.swanctl_secret)
        self.assertNotIn("校园网密码", profile.mobileconfig.decode("utf-8"))

    def test_ca_certificate_is_required(self):
        controller = IKEv2ProfileController(
            "10.12.72.55", "vpn.campusnet.local", b"", gateway_ready=True, swanctl_available=True,
        )
        with self.assertRaisesRegex(IKEv2GatewayNotReady, "CA 证书"):
            controller.create_device_profile("my_iphone")
