import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "mobile"))
from android_acceptance import run_profile_store_probe  # noqa: E402


FIXTURE = ROOT / "scripts/android_emulator_profile_fixture.json"


class AndroidAcceptanceProbeTests(unittest.TestCase):
    def test_fixture_is_synthetic_empty_and_loopback_only(self):
        data = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual(data["username"], "")
        self.assertEqual(data["password"], "")
        self.assertEqual(data["auth_url"], "http://127.0.0.1:9/")

    def test_first_run_encrypts_and_reads_back_profile(self):
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as user_data_dir:
            Path(user_data_dir, "acceptance-profile.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )
            encrypted_path = Path(user_data_dir) / "profile.enc"

            def encrypt(path, profile):
                encrypted_path.write_text("v1:synthetic-ciphertext", encoding="utf-8")

            with mock.patch("android_acceptance.write_profile", side_effect=encrypt), \
                    mock.patch("android_acceptance.load_profile_data", return_value=expected):
                marker = run_profile_store_probe(user_data_dir)

            self.assertEqual(marker, "CNM_ANDROID_PROFILE_STORE_WRITE_PASS")
            self.assertEqual(encrypted_path.read_text(encoding="utf-8"), "v1:synthetic-ciphertext")

    def test_restart_decrypts_existing_profile(self):
        expected = json.loads(FIXTURE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as user_data_dir:
            Path(user_data_dir, "acceptance-profile.json").write_text(
                json.dumps(expected), encoding="utf-8"
            )
            Path(user_data_dir, "profile.enc").write_text("v1:ciphertext", encoding="utf-8")
            with mock.patch("android_acceptance.load_profile_data", return_value=expected), \
                    mock.patch("android_acceptance.write_profile") as write:
                marker = run_profile_store_probe(user_data_dir)
            self.assertEqual(marker, "CNM_ANDROID_PROFILE_STORE_RESTART_PASS")
            write.assert_not_called()

    def test_probe_rejects_credentials_and_non_loopback_endpoints(self):
        for patch_data in ({"username": "should-never-run"},
                           {"auth_url": "https://example.com/"}):
            with self.subTest(patch_data=patch_data), tempfile.TemporaryDirectory() as root:
                data = json.loads(FIXTURE.read_text(encoding="utf-8"))
                data.update(patch_data)
                Path(root, "acceptance-profile.json").write_text(
                    json.dumps(data), encoding="utf-8"
                )
                with self.assertRaises(ValueError):
                    run_profile_store_probe(root)

    def test_workflow_and_emulator_script_keep_probe_isolated(self):
        workflow = (ROOT / ".github/workflows/mobile.yml").read_text(encoding="utf-8")
        script = (ROOT / "scripts/android_emulator_smoke.sh").read_text(encoding="utf-8")
        main = (ROOT / "mobile/main.py").read_text(encoding="utf-8")
        self.assertIn("RUN_EMULATOR_ACCEPTANCE_PROBE", workflow)
        self.assertIn("pull_request:", workflow)
        self.assertIn("github.event_name == 'push'", workflow)
        self.assertIn("github.event_name == 'pull_request'", workflow)
        self.assertIn("POST_NOTIFICATIONS", script)
        self.assertIn("am force-stop", script)
        self.assertIn("svc wifi disable", script)
        self.assertIn("restore_emulator_wifi", script)
        self.assertIn("assert_wifi_state", script)
        self.assertIn("isForeground=true|foregroundId=", script)
        self.assertIn("pm clear", script)
        self.assertIn("_start_android_acceptance_guard", main)
        self.assertIn("CNM_ANDROID_FOREGROUND_SERVICE_START_REQUESTED", main)

    def test_fixture_transfer_uses_direct_run_as_commands(self):
        script = (ROOT / "scripts/android_emulator_smoke.sh").read_text(encoding="utf-8")
        self.assertIn('adb shell run-as "$package_name" mkdir -p files/app', script)
        self.assertIn(
            'adb shell run-as "$package_name" tee files/app/acceptance-profile.json', script
        )
        self.assertIn(
            'adb shell run-as "$package_name" tee files/acceptance-profile.json', script
        )
        self.assertNotIn(
            'run-as "$package_name" sh -c \'mkdir -p files/app', script
        )

    def test_foreground_service_assertion_waits_for_startup_and_reports_state(self):
        script = (ROOT / "scripts/android_emulator_smoke.sh").read_text(encoding="utf-8")
        assertion = script.split("assert_service_running() {", 1)[1].split("\n}", 1)[0]
        self.assertIn('for attempt in $(seq 1 30)', assertion)
        self.assertIn('isForeground=true|foregroundId=[1-9][0-9]*', assertion)
        self.assertIn("did not reach foreground state", assertion)
        self.assertIn('tee -a "$log_file" >&2', assertion)


if __name__ == "__main__":
    unittest.main()
