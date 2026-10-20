# Cross-platform UI follow-up — 2026-10-21

## Verified

- macOS v5.6.0 is running locally. The read-only proxy egress check displayed success; the app reported zero connected remote clients. No tunnel, hotspot, VPN, or network configuration was changed.
- The macOS first-run wizard opened from the main window using keyboard navigation. Selecting “A：电脑直连” displayed the plan A instructions. The Wi-Fi and hotspot actions were not invoked.
- Windows hosted x64 VM run `39454672425` built the EXE and displayed the main window and first-run wizard. Its alternate keyboard path failed before sending keys: the report artifact says UIA `SetFocus()` raised “Target element cannot receive focus.”
- The new Windows script revision removes that UIA focus call, relies on foregrounding the actual wizard window, and stops after verifying the local plan A view. It no longer sends keys on the plan A page, where the first Tab could focus the hotspot action.
- Run `39456072346` built the EXE and displayed the main window and wizard, then failed because .NET `SendKeys` rejects the `{SPACE}` token. The corrected sequence sends `{TAB}` followed by a literal space; this is the final bounded retry of this keyboard path.
- Run `39456484992` accepted the literal-space sequence but timed out waiting for the A-page title. It did not record which choice, if any, received the key event. The script now uses a bounded Win32 click at a screen position derived from the wizard bounds, targeting its bottom-right plan A button, and verifies the resulting title; no keys are sent on the plan page.
- iPhone USB pairing validates, but iPhone Mirroring currently shows “连接暂停”; Safari Develop lists the iPhone target as “正在连接…” and the PWA target is not inspectable. No iPhone network settings were changed and no offline test was run.

## Limits

- macOS wizard back-navigation could not be activated with the available UI path. The screen showed the “上一步” button, but keyboard focus cycled among the two system-settings actions and a pointer click did not change the page. Neither system-settings action was triggered.
- Windows UI acceptance is still pending a run of the foreground-only keyboard path on GitHub-hosted Windows x64.
- iPhone live DOM, service worker, cache, and offline cold-start checks remain pending until the remote Safari target reconnects.
