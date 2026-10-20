from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class WindowsVmUiAcceptanceTests(unittest.TestCase):
    def test_desktop_candidate_runs_the_windows_ui_acceptance_script(self):
        workflow = (ROOT / ".github/workflows/desktop-candidate.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("windows_vm_ui_acceptance.ps1", workflow)
        self.assertIn("windows-ui-acceptance.txt", workflow)
        self.assertIn("windows-ui-wizard-before.png", workflow)
        self.assertIn("windows-ui-wizard-after.png", workflow)
        self.assertIn("windows-latest", workflow)

    def test_script_exercises_only_local_wizard_navigation(self):
        script = (ROOT / "scripts/windows_vm_ui_acceptance.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Click-WizardPlanA -Window $wizard", script)
        self.assertIn("[CampusNetUiWindow]::GetWindowRect", script)
        self.assertIn("[CampusNetUiWindow]::SetCursorPos($x, $y)", script)
        self.assertIn("plan_a_button_click=absolute screen position derived from wizard bounds", script)
        self.assertIn("Capture-WindowScreenshot", script)
        self.assertIn('wizard_screenshot_before=', script)
        self.assertIn('wizard_screenshot_after=', script)
        self.assertIn('[CampusNetUiWindow]::SetForegroundWindow($handle)', script)
        self.assertNotIn("$Window.SetFocus()", script)
        self.assertNotIn('Send-KeyboardToWindow -Window $planA', script)
        self.assertNotIn("SendKeys", script)
        self.assertIn('network_settings_actions=not_invoked', script)
        self.assertIn('hotspot_and_wifi_actions=not_invoked', script)
        self.assertNotIn('Open WiFi Settings', script)
        self.assertNotIn('Open mobile hotspot', script)

    def test_tracks_pyinstaller_onefile_child_process_windows(self):
        script = (ROOT / "scripts/windows_vm_ui_acceptance.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Get-ApplicationProcessIds", script)
        self.assertIn("Win32_Process", script)
        self.assertIn("ParentProcessId", script)
        self.assertIn("-RootProcessId", script)
        self.assertIn("TreeScope]::Descendants", script)

    def test_wizard_window_title_tracks_the_visible_plan_for_accessibility(self):
        wizard = (ROOT / "gui/wizard.py").read_text(encoding="utf-8")
        self.assertIn('win.title("新手向导")', wizard)
        self.assertIn('win.title("方式 A：电脑直连校园网")', wizard)
        self.assertIn('win.title("方式 B：副路由器中继扩展信号")', wizard)
        self.assertIn('win.title("方式 C：隧道共享上网")', wizard)

    def test_wizard_flushes_pending_page_redraws_after_state_changes(self):
        wizard = (ROOT / "gui/wizard.py").read_text(encoding="utf-8")
        self.assertIn("def refresh_wizard_view():", wizard)
        self.assertIn("win.update_idletasks()", wizard)
        self.assertGreaterEqual(wizard.count("refresh_wizard_view()"), 6)


if __name__ == "__main__":
    unittest.main()
