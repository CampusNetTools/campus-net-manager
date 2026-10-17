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
- Rejects enrollment files larger than 64 KiB before parsing to keep imported input bounded.
- Stores the EAP password in Keychain and configures iOS IKEv2 with server-certificate name validation.
- Loads the saved configuration after relaunch, reports system VPN status, and supports connect, disconnect, re-import, and removal.
- Uses the IKEv2 server's normal routing and NAT. It does not depend on the old Packet Tunnel protocol or an unimplemented TLS/TUN service.

## Verification boundary

An unsigned iOS Simulator build succeeded in GitHub Actions run `38852926224`. The expanded workflow's first install attempt (`38853483784`) found that the app plist lacked `CFBundleExecutable`; after adding Xcode's executable and product-name settings, run `38853975796` compiled, installed, and launched the app in an iPhone Simulator and uploaded the unsigned `.app` artifact (ID `12026980614`). These runs did not verify signing, a real iPhone, certificate trust, IKEv2 negotiation, or bidirectional traffic. This Mac lacks full Xcode and an Apple Developer provisioning profile. Real iPhone upgrade and App Store review remain unverified. VPN App Store distribution also requires an eligible organization developer account and Apple's review of the VPN service and privacy disclosures.

Latest source verification: Actions run `39013104364` on head `32c9a9ebb7d3041d3e15f2f086b0a4123731b3e0` completed successfully. All 6 enrollment XCTest cases passed; the Simulator app then built, installed, launched, packaged, and uploaded. Artifact `12093464420` (5,156,249 bytes) SHA-256 matched the Actions digest (`efb55215d65a18c5cfb83b78ebaa67a33ef208cb98302e6dd262be7df862b54d`), and the outer artifact ZIP passed CRC. The nested `CampusNetCompanion-Simulator.app.zip` SHA-256 is `fcf580d68acd1dab2e881c3179b611e3f6c1b82bd5bc430adbdbb1e9ac4a04aa`; its ZIP CRC passed and it retains `CampusNetCompanion.app/`. Bundle id is `com.campusnettools.companion`, version `0.2.0 (3)`, platform `iPhoneSimulator`, and executable architecture x86_64/arm64. The executable has an adhoc linker signature; the app bundle has no distribution signature or Team ID (`CODE_SIGNING_ALLOWED=NO`). XCTest covers enrollment parsing only. No real-device signing, Keychain lifecycle, system VPN authorization, IKEv2 connection, or bidirectional traffic is proven.
