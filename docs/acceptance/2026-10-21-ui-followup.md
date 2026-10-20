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
