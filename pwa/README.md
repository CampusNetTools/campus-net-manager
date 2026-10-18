# CampusNetManager PWA

This is a static, installable browser companion for iPhone and Mac. It is intentionally not a VPN client and does not expose the authenticated LAN console.

## Included features

- A stable link to the GitHub latest-release page, where platform assets and checksums are listed.
- iPhone Home Screen and macOS Dock installation instructions.
- Offline-cached installation and troubleshooting guidance.
- A browser `navigator.onLine` indicator, labeled as a browser hint rather than an internet, Wi-Fi, campus-login, or VPN test.
- A non-sensitive reading checklist stored only in the current browser's local storage.

## Kept native or local

The PWA cannot run the desktop keepalive daemon, log into Dr.COM, read Wi-Fi SSID/ARP/gateway information, operate router/NAS controls, or manage an iOS system VPN. Those capabilities remain in the desktop app or the operating system/provider VPN settings.

Do not place account credentials, enrollment JSON, private keys, or per-device `.mobileconfig` files in this directory. The static page has no API, login form, analytics, third-party scripts, or external font dependencies.

## Hosting

GitHub Pages deployment is defined in `.github/workflows/pwa-pages.yml` and only deploys from `main`. Repository Pages must use the GitHub Actions publishing source. The intended project URL is `https://campusnettools.github.io/campus-net-manager/` after the first successful deployment. A missing Pages site or failed deployment must not be reported as live.

The page is public static project documentation/download navigation, not a hosted software service. GitHub Pages has limits and is not a permanence or uptime guarantee.
