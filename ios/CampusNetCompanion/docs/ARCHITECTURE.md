# iOS IKEv2 client architecture

```text
Mac enrollment generator
  ├─ private .ikev2.json ── local AirDrop/USB ──> iPhone app ──> Keychain password reference
  ├─ root-only .mobileconfig ──> iOS certificate trust
  └─ devices/<name>.conf ──> strongSwan EAP credentials

iPhone app ── NEVPNManager / NEVPNProtocolIKEv2 ──> Mac strongSwan ──> campus network
```

## Trust boundaries

- The `.ikev2.json` contains one device's EAP username and password. The Mac generator writes it with owner-only permissions under the private gateway profiles directory. It is intended only for local AirDrop/USB delivery and must be removed from transfer locations after import.
- The separate `-ca.mobileconfig` contains only the gateway root certificate. The user installs and trusts it in iOS Settings before creating the app-managed VPN. The IKEv2 config also requires the server certificate common name to match the enrolled server identifier.
- The App stores the EAP password as a generic Keychain item with a persistent reference and `ThisDeviceOnly` accessibility. The system VPN configuration receives only that persistent reference. Re-import creates a new credential first and removes the previous one only after preferences save succeeds.
- The Mac-side EAP secret is independent from the campus Wi-Fi account/password. No campus credential is copied to the iPhone app.

## VPN configuration

The app uses Personal VPN entitlement `com.apple.developer.networking.vpn.api = allow-vpn` and iOS `NEVPNManager` with `NEVPNProtocolIKEv2`. It enables extended authentication with EAP-MSCHAPv2, validates the server certificate common name, enables PFS, uses medium dead-peer detection, and routes all networks through the VPN. iOS prompts the user when the app first saves the system VPN configuration.

The app reloads the saved configuration after relaunch and observes `NEVPNStatusDidChange`. It distinguishes disconnected, connecting/reasserting, connected, disconnecting, and invalid/error states. Removing the device removes the Personal VPN configuration and its Keychain credential reference.

## Acceptance still required

- Generate the Xcode project and compile/sign with an organization account that has Personal VPN capability.
- Install and trust the root profile on a real iPhone; import one device file; confirm the iOS VPN authorization prompt.
- Verify IKE_AUTH succeeds, the phone gets expected routes/DNS, and bidirectional traffic passes through the Mac gateway.
- Verify disconnect, remove, re-import, expired/revoked EAP credential, and upgrade/recovery paths.
- Verify App Store privacy disclosures and organizational VPN service review requirements.

No source-level or Swift parser check is equivalent to these runtime and release gates.
