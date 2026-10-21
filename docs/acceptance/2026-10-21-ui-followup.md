# Cross-platform UI follow-up — 2026-10-21

## Verified

- macOS v5.6.0 is running locally. The read-only proxy egress check displayed success; the app reported zero connected remote clients. No tunnel, hotspot, VPN, or network configuration was changed.
- The macOS first-run wizard opened from the main window using keyboard navigation. Selecting “A：电脑直连” displayed the plan A instructions. The Wi-Fi and hotspot actions were not invoked.
- Windows hosted x64 VM run `39454672425` built the EXE and displayed the main window and first-run wizard. Its alternate keyboard path failed before sending keys: the report artifact says UIA `SetFocus()` raised “Target element cannot receive focus.”
- The new Windows script revision removes that UIA focus call, relies on foregrounding the actual wizard window, and stops after verifying the local plan A view. It no longer sends keys on the plan A page, where the first Tab could focus the hotspot action.
- Run `39456072346` built the EXE and displayed the main window and wizard, then failed because .NET `SendKeys` rejects the `{SPACE}` token. The corrected sequence sends `{TAB}` followed by a literal space; this is the final bounded retry of this keyboard path.
- Run `39456484992` accepted the literal-space sequence but timed out waiting for the A-page title. It did not record which choice, if any, received the key event. The script now uses a bounded Win32 click at a screen position derived from the wizard bounds, targeting its bottom-right plan A button, and verifies the resulting title; no keys are sent on the plan page.
- iPhone USB pairing validates, but iPhone Mirroring currently shows “连接暂停”; Safari Develop lists the iPhone target as “正在连接…” and the PWA target is not inspectable. No iPhone network settings were changed and no offline test was run.

## Earlier limits (superseded where stated below)

- macOS wizard back-navigation was initially inaccessible; later in this session, keyboard navigation returned from a subpage to the choice page without activating system-settings actions.
- Windows UI acceptance was pending before the `ef03a17` VM run recorded below.
- iPhone live DOM, service worker, cache, and offline cold-start checks remain pending until the remote Safari target reconnects.

## Follow-up — 2026-10-21

- Windows x64 VM: commit `ef03a17503403183e6b16c0186e16267d50c67b9`, Desktop candidate run `39460114079`, job `Build and launch smoke (windows)` and UI acceptance step succeeded. The report artifact is `campusnetmanager-windows-vm-ui-acceptance` (ID `12283180619`, Actions digest `sha256:80d0f461194613abd21120d057b787aaa66d9b77366cc6f72dbb47ca2dea3277`). I reviewed the uploaded after-click screenshot: it shows the plan A heading and instructions, the previous-step button, and the Wi-Fi/hotspot actions; the plan-choice body and B/C choices are gone. This verifies first-run wizard navigation only. The script did not open Wi-Fi/hotspot settings or verify physical networking.
- The screenshot review exposed a false positive in run `39458880748`: the native title and A button had changed while the body and B/C buttons were still stale. `gui/wizard.py` now flushes pending Tk idle/layout work after each wizard page transition, and the VM capture waits 1.5 seconds. Five targeted tests, Python compilation, workflow YAML parsing, and `git diff --check` passed before the candidate run.
- macOS: the earlier local UI pass in this session exercised the A/B/C guide pages and returned from a subpage to the choice page; the read-only egress check passed with no remote clients. In this follow-up, the installed v5.6.0 app process/window remains present, but Codex Computer Use reports its runtime app is missing, and macOS accessibility exposes only the window-level sharing button. One system-coordinate click intended for an exposed app control instead focused the ChatGPT window; no text was entered and no project/app setting changed. Per the bounded attempt rule, coordinate clicking stopped here. Remaining native control-by-control coverage is blocked by the UI automation runtime and unreliable coordinate mapping.
- iPhone PWA: USB pairing validates and Safari's Develop menu lists the paired iPhone. A read-only `ios_webkit_debug_proxy` check found the paired device but zero inspectable page targets on its mapped port; `AirplaneMode=true`. The proxy was stopped immediately, its ports no longer listen, and macOS Firewall still reports the proxy blocked for inbound connections. No iPhone Safari DOM or PWA target was read and no network setting was changed. Live page, service worker/cache, offline cold launch, and reconnect checks remain unverified until a Safari/PWA page target is exposed; the cause of the empty target list is not established.

## Independent-work follow-up — 2026-10-21

### Verified

- The public Pages site opened in an isolated in-app browser at `https://campusnettools.github.io/campus-net-manager/`. The page rendered the product overview, Windows/macOS/Android download links, iPhone PWA guidance, privacy notes, and the device-instructions tabs. Each desktop/mobile download link points to the public GitHub Latest Release.
- Responsive browser emulation at 390×844 CSS pixels reported `scrollWidth=390` and no horizontal overflow. The page title, main heading, downloads and guide sections were present.
- Before offline simulation, the page was controlled by an activated Service Worker at scope `https://campusnettools.github.io/campus-net-manager/`; Cache Storage contained `campusnet-pwa-shell-v2`, and the cached root page returned 200.
- With CDP offline emulation enabled only for this in-app browser tab, reloading rendered the complete cached landing page and its visible “浏览器报告离线” state. This is desktop-browser cache evidence, not iPhone offline acceptance. Network emulation was then cleared; the page reloaded online, with `navigator.onLine=true`, the same activated controller/cache, and cached root response 200.
- The public GitHub Latest Release page resolved to v5.6.0, published 2026-10-18. Its release notes list the macOS Apple Silicon ZIP, unsigned Windows x64 EXE, signed Android APK and SHA-256 values; it explicitly states that there is no native iPhone IPA. This confirms the current public distribution description, not a new binary download or local checksum verification in this round.
- Windows x64 hosted VM evidence remains run `39460114079`, artifact `12283180619`: the uploaded screenshot confirms the local first-run wizard reached plan A. It does not verify physical Wi-Fi/hotspot or user-device installation.
- On the Mac, the installed v5.6.0 main window was visible and reported its local guard/network indicators. CUA opened the first-run wizard. The A/B/C choice page rendered, but attempts to activate a plan did not change the page; controls are absent from the accessibility tree. The wizard was closed afterward. No credentials were entered or copied; the profile screenshot was not saved to a project artifact/report. No network setting, hotspot, tunnel, or authorization prompt was changed.
- `idevicepair validate` succeeded, but `ideviceinfo -k AirplaneMode` returned `true`. Safari’s “App and Device Inspection” listed the Mac’s local tabs and no iPhone remote page. No phone network setting was changed; no live iPhone DOM, offline launch, or reconnect check was performed.
- PR #6 remains open and unmerged at `c7ca70a`; its CI run `39462580305` passed Windows/macOS checks and desktop candidate run `39462580253` completed successfully (docs-only candidate build jobs skipped). No PR merge or release change was made.

### Method notes and remaining limits

- The Playwright CLI wrapper failed to start with `Class extends value undefined`; the in-app browser/CDP path completed the site, responsive, and isolated offline checks instead.
- Independent desktop-browser/PWA deployment checks are complete for this round. Remaining work that is not independently executable from the current state: iPhone Safari inspection/offline behavior (phone currently reports Airplane Mode on and no remote Safari target); Mac wizard plan A/B/C interaction (current UI path cannot activate the choices); and any user decision about the system tunnel-sharing authorization. No repeated coordinate clicks, network-setting changes, or authorization decisions were attempted.
