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
        self.assertIn("windows-latest", workflow)

    def test_script_exercises_only_local_wizard_navigation(self):
        script = (ROOT / "scripts/windows_vm_ui_acceptance.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("Click-WizardPlanA -Window $wizard", script)
        self.assertIn("[CampusNetUiWindow]::GetWindowRect", script)
        self.assertIn("[CampusNetUiWindow]::SetCursorPos($x, $y)", script)
        self.assertIn("plan_a_button_click=absolute screen position derived from wizard bounds", script)
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


if __name__ == "__main__":
    unittest.main()
