# CampusNet Companion for iPhone

The app manages iOS Personal VPN through `NEVPNManager` and the built-in `NEVPNProtocolIKEv2`, connecting to the project's existing strongSwan gateway. It does not use the unfinished custom Packet Tunnel or claim that a Mac TUN/NAT gateway exists.

## Local enrollment

On a Mac with the authorized IKEv2 gateway installed, run `scripts/create_ikev2_device_profile.py`. It creates four private files under the gateway state directory:

- `<device>.mobileconfig`: the complete iOS system profile for users who prefer the Settings-based route.
- `<device>-ca.mobileconfig`: the gateway root certificate only; install this before using the app so iOS can validate the IKEv2 server certificate.
- `<device>.ikev2.json`: the app enrollment file containing this device's EAP username and password.
- `devices/<device>.conf`: the matching server-side EAP credential fragment.

Transfer the CA profile and app enrollment file only by local AirDrop or USB. Install and trust the CA profile in iOS Settings, import the `.ikev2.json` from Files into this app, and delete the transferred JSON after import. The app stores the password in Keychain and passes its persistent reference to the system VPN configuration; the password is not logged or embedded in the app's QR code. The first save asks iOS to approve adding a VPN configuration.

Do not install both the complete `.mobileconfig` and the app-managed VPN at the same time. The complete profile is an alternative to using this app.

## App behavior

- Imports and validates a per-device enrollment file.
- Stores the EAP password in Keychain and configures iOS IKEv2 with server-certificate name validation.
- Loads the saved configuration after relaunch, reports system VPN status, and supports connect, disconnect, re-import, and removal.
- Uses the IKEv2 server's normal routing and NAT. It does not depend on the old Packet Tunnel protocol or an unimplemented TLS/TUN service.

## Verification boundary

An unsigned iOS Simulator build succeeded in GitHub Actions run `38852926224`; it did not verify signing, a real iPhone, certificate trust, IKEv2 negotiation, or bidirectional traffic. The follow-up workflow now also installs and launches the simulator app and uploads the `.app` artifact; that expanded workflow still needs a successful run. This Mac lacks full Xcode and an Apple Developer provisioning profile. Real iPhone upgrade and App Store review remain unverified. VPN App Store distribution also requires an eligible organization developer account and Apple's review of the VPN service and privacy disclosures.
