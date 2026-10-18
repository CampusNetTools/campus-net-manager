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

## Long-term option without Xcode or app signing

For a device that must keep working without periodic free-profile re-signing, install the generated complete `<device>.mobileconfig` as an iOS system profile instead of installing this companion app. Apple says Personal Team provisioning profiles for free on-device testing expire after 7 days, so that app-signing path does not meet the long-term requirement: [Apple Developer account overview](https://developer.apple.com/help/account/basics/about-your-developer-account). The system profile configures iOS's built-in IKEv2 VPN; it does not provide this app's connect/status screen, and the VPN is managed in iOS Settings. Apple allows users to install a configuration profile downloaded from a webpage, then review and install it in Settings: [Apple Support: install or remove configuration profiles](https://support.apple.com/guide/iphone/iph6c493b19/ios).

The complete profile contains that device's EAP username and password in the profile payload. Generate it only on the authorized gateway Mac and transfer it privately (AirDrop or USB); do not put a real profile on a public website or shared desktop. After installation, delete the transferred profile file. A downloaded-but-not-installed profile is automatically removed by iOS after 8 minutes, so install it promptly: [Apple Support: install a downloaded profile](https://support.apple.com/102400).

The generated profile has no profile-expiration field, but the VPN still depends on the gateway and its certificates: this project creates a 10-year CA certificate and an 825-day server certificate. Plan to renew the server certificate before it expires and replace the CA/profile before the CA expires. This is long-lived, not permanent. Current source verification for the profile schema is covered by `tests.test_ikev2_profile`; it does not replace installation and VPN traffic checks on a real iPhone.

A Safari Home Screen web app can provide instructions and setup forms, but it cannot call the native [`NEVPNManager`](https://developer.apple.com/documentation/networkextension/nevpnmanager) API or control the system VPN. The persistent no-Xcode VPN path is the installed system profile, not a web app impersonating the native VPN controls. See [Apple's IKEv2 VPN payload reference](https://developer.apple.com/documentation/devicemanagement/vpn/ikev2-data.dictionary).

## App behavior

- Imports and validates a per-device enrollment file.
- Rejects enrollment files larger than 64 KiB before parsing to keep imported input bounded.
- Stores the EAP password in Keychain and configures iOS IKEv2 with server-certificate name validation.
- Loads the saved configuration after relaunch, reports system VPN status, and supports connect, disconnect, re-import, and removal.
- Uses the IKEv2 server's normal routing and NAT. It does not depend on the old Packet Tunnel protocol or an unimplemented TLS/TUN service.

## Verification boundary

An unsigned iOS Simulator build succeeded in GitHub Actions run `38852926224`. The expanded workflow's first install attempt (`38853483784`) found that the app plist lacked `CFBundleExecutable`; after adding Xcode's executable and product-name settings, run `38853975796` compiled, installed, and launched the app in an iPhone Simulator and uploaded the unsigned `.app` artifact (ID `12026980614`). These runs did not verify signing, a real iPhone, certificate trust, IKEv2 negotiation, or bidirectional traffic. This Mac lacks full Xcode and an Apple Developer provisioning profile. Real iPhone upgrade and App Store review remain unverified. VPN App Store distribution also requires an eligible organization developer account and Apple's review of the VPN service and privacy disclosures.

Latest iOS-specific source verification: Simulator run `39015990577` on head `927c142f1eb88013b02b5ebe42a8e8a57e7ac2c1` completed successfully. All 8 enrollment XCTest cases passed, including the 64 KiB input bound; the unsigned Simulator app then built, installed, launched, packaged, and uploaded. Artifact `12095062191` SHA-256 matched the Actions digest (`a0a78aedd68c57a759df29b135436cea2085c9cb66e82348eea9f80acad50742`), and the outer ZIP CRC passed. The nested app ZIP SHA-256 is `3c94533bd5f0a9b24e2b6d616470ef3b298111e75e838dd8a05d42b39a74cf90`; its ZIP CRC passed and it retains the complete `CampusNetCompanion.app/` bundle. Bundle id is `com.campusnettools.companion`, version `0.2.0 (3)`, platform `iPhoneSimulator`, architectures x86_64/arm64. The executable has an adhoc linker signature; there is no Team ID or distribution signature. XCTest covers enrollment parsing only. No real-device signing, Keychain lifecycle, system VPN authorization, IKEv2 connection, or bidirectional traffic is proven.

The later Android-only `core/auth.py` HTTPS transport change (`f9c6d73`) did not modify iOS files. The latest iOS-specific build remains the 927c142 run above; it does not validate iOS behavior against the later shared core login implementation.
