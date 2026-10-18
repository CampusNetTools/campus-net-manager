import configparser
import tempfile
import unittest
from pathlib import Path

from scripts.patch_p4a_special_use import (
    MARKER,
    OLD_VENV,
    VENV_MARKER,
    patch_build,
    patch_template,
)


class P4aSpecialUsePatchTests(unittest.TestCase):
    def test_buildozer_uses_the_supported_services_setting(self):
        spec = configparser.ConfigParser()
        spec.read_string(
            (Path(__file__).parents[1] / "mobile" / "buildozer.spec").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            spec.get("app", "services"),
            "campusguard:services/campusguard.py:foreground:sticky:foregroundServiceType=specialUse",
        )
        self.assertFalse(spec.has_option("app", "android.services"))

    def test_buildozer_packages_device_and_emulator_abis(self):
        spec = configparser.ConfigParser()
        spec.read_string(
            (Path(__file__).parents[1] / "mobile" / "buildozer.spec").read_text(
                encoding="utf-8"
            )
        )
        archs = {item.strip() for item in spec.get("app", "android.archs").split(",")}
        self.assertEqual(archs, {"arm64-v8a", "armeabi-v7a", "x86_64"})

    def test_android_package_includes_simplified_chinese_font_and_license(self):
        root = Path(__file__).parents[1]
        spec = configparser.ConfigParser()
        spec.read_string((root / "mobile" / "buildozer.spec").read_text(encoding="utf-8"))
        included = {item.strip() for item in spec.get("app", "source.include_exts").split(",")}
        self.assertIn("ttf", included)
        self.assertIn("txt", included)
        font_path = root / "mobile" / "assets" / "NotoSansSC.ttf"
        self.assertGreater(font_path.stat().st_size, 8_000_000)
        font_data = font_path.read_bytes()
        table_count = int.from_bytes(font_data[4:6], "big")
        table_tags = {font_data[12 + index * 16:16 + index * 16].decode("ascii")
                      for index in range(table_count)}
        self.assertNotIn("fvar", table_tags)
        self.assertNotIn("gvar", table_tags)
        license_text = (root / "mobile" / "assets" / "OFL-NotoSansSC.txt").read_text(encoding="utf-8")
        self.assertIn("SIL OPEN FONT LICENSE Version 1.1", license_text)
        app_source = (root / "mobile" / "main.py").read_text(encoding="utf-8")
        self.assertIn('"assets", "NotoSansSC.ttf"', app_source)
        self.assertGreaterEqual(app_source.count("font_name=_FONT_NAME"), 6)

    def test_android_emulator_workflow_enables_kvm_before_launch(self):
        workflow = (Path(__file__).parents[1] / ".github" / "workflows" / "mobile.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("branches: [codex/full-project-closure]", workflow)
        self.assertIn("- mobile/**", workflow)
        self.assertIn("- scripts/android_emulator_smoke.sh", workflow)
        self.assertIn("cp -r mobile/assets build_mobile/", workflow)
        self.assertIn("cp mobile/startup_status.py build_mobile/", workflow)
        self.assertIn("assets/NotoSansSC.ttf", workflow)
        self.assertIn("assets/private.tar", workflow)
        kvm_step = workflow.index("启用 GitHub runner 的 KVM 权限")
        emulator_step = workflow.index("reactivecircus/android-emulator-runner@")
        self.assertLess(kvm_step, emulator_step)
        self.assertIn('GROUP="kvm", MODE="0666"', workflow[kvm_step:emulator_step])
        self.assertIn("set -euxo pipefail", workflow[kvm_step:emulator_step])
        self.assertIn("test -c /dev/kvm", workflow[kvm_step:emulator_step])
        self.assertIn("sudo chmod a+rw /dev/kvm", workflow[kvm_step:emulator_step])
        self.assertIn("test -r /dev/kvm && test -w /dev/kvm", workflow[kvm_step:emulator_step])
        self.assertIn("disable-linux-hw-accel: false", workflow[emulator_step:])

    def test_android_release_uses_verified_api36_apk_for_direct_download(self):
        root = Path(__file__).parents[1]
        mobile_workflow = (root / ".github" / "workflows" / "mobile.yml").read_text(
            encoding="utf-8"
        )
        release_workflow = (root / ".github" / "workflows" / "ci.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("workflow_call:", mobile_workflow)
        self.assertIn("sign_for_direct_download:", mobile_workflow)
        self.assertIn("|| inputs.sign_for_direct_download", mobile_workflow)
        self.assertIn("aapt\" dump badging \"$apk\" | grep -F \"versionName='$app_version'\"", mobile_workflow)
        self.assertIn("CampusNetManager-Android-${app_version}.apk", mobile_workflow)
        self.assertIn('"$GITHUB_REF_NAME" != "v$app_version"', mobile_workflow)
        self.assertIn(
            "tar -tf /tmp/campusnet-private.tar > /tmp/campusnet-private-members.txt",
            mobile_workflow,
        )
        self.assertIn(
            "grep -Fxq 'assets/NotoSansSC.ttf' /tmp/campusnet-private-members.txt",
            mobile_workflow,
        )
        self.assertNotIn(
            "tar -tf /tmp/campusnet-private.tar | grep -Fxq",
            mobile_workflow,
        )
        self.assertIn("sha256sum \"$release_apk\"", mobile_workflow)
        self.assertIn("api-level: 36", mobile_workflow)
        self.assertIn("CNM_NETWORK_STATUS_READY:", (root / "scripts" / "android_emulator_smoke.sh").read_text(encoding="utf-8"))
        self.assertIn("softprops/action-gh-release@v2", mobile_workflow)
        self.assertIn("if: startsWith(github.ref, 'refs/tags/v')", mobile_workflow)
        for secret in (
            "ANDROID_KEYSTORE_BASE64",
            "ANDROID_KEYSTORE_PASSWORD",
            "ANDROID_KEY_ALIAS",
            "ANDROID_KEY_PASSWORD",
        ):
            self.assertIn("secrets." + secret, mobile_workflow)
        self.assertIn('"$build_tools/apksigner" sign', mobile_workflow)
        self.assertIn("--ks-type PKCS12", mobile_workflow)
        self.assertIn('"$build_tools/apksigner" verify --verbose', mobile_workflow)
        self.assertIn("Signer #1 certificate SHA-256 digest: a6a3451d09b6ec3b34f12ee07193233b812a04acd2ba711ab56dd466bb6aa613", mobile_workflow)
        self.assertIn("needs: [test, release]", release_workflow)
        self.assertIn("uses: ./.github/workflows/mobile.yml", release_workflow)
        self.assertIn("secrets: inherit", release_workflow)

    def test_emulator_smoke_runs_as_one_shell_script(self):
        root = Path(__file__).parents[1]
        workflow = (root / ".github" / "workflows" / "mobile.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("script: bash scripts/android_emulator_smoke.sh", workflow)
        smoke = (root / "scripts" / "android_emulator_smoke.sh").read_text(
            encoding="utf-8"
        )
        self.assertIn("set -euo pipefail", smoke)
        self.assertIn('apk="$(find "$artifact_dir/bin"', smoke)
        self.assertIn('pid="$(adb shell pidof "$package_name"', smoke)
        self.assertIn("trap capture_evidence EXIT", smoke)
        self.assertIn("scripts/check_android_screenshot.py", smoke)
        self.assertIn("CNM_NETWORK_STATUS_READY:", smoke)
        self.assertIn("seq 1 30", smoke)
        self.assertLess(
            smoke.index("network_status_ready=1"),
            smoke.index("scripts/check_android_screenshot.py"),
        )
        self.assertIn("seq 1 10", smoke)

    def test_inserts_android_special_use_subtype_for_campusguard(self):
        template = '''<service android:name="{{ args.package }}.Service{{ name|capitalize }}"
                 {% if foreground_type %}
                 android:foregroundServiceType="{{ foreground_type }}"
                 {% endif %}
                 android:process=":service_{{ name }}" />'''
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AndroidManifest.tmpl.xml"
            path.write_text(template, encoding="utf-8")
            self.assertTrue(patch_template(path))
            patched = path.read_text(encoding="utf-8")
            self.assertIn('{% if name == "campusguard" %}', patched)
            self.assertIn(MARKER, patched)
            self.assertIn('android:value="User-enabled periodic campus-network authentication keepalive."', patched)

    def test_patch_is_idempotent(self):
        template = '''<service android:name="{{ args.package }}.Service{{ name|capitalize }}"
                 {% if foreground_type %}
                 android:foregroundServiceType="{{ foreground_type }}"
                 {% endif %}
                 android:process=":service_{{ name }}" />'''
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AndroidManifest.tmpl.xml"
            path.write_text(template, encoding="utf-8")
            patch_template(path)
            self.assertFalse(patch_template(path))

    def test_refuses_unrecognized_template(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "AndroidManifest.tmpl.xml"
            path.write_text("<manifest />", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                patch_template(path)

    def test_p4a_venv_patch_clears_stale_pip_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "build.py"
            path.write_text(OLD_VENV + "\n", encoding="utf-8")
            self.assertTrue(patch_build(path))
            self.assertEqual(path.read_text(encoding="utf-8"), VENV_MARKER + "\n")
            self.assertFalse(patch_build(path))

    def test_p4a_venv_patch_refuses_unknown_source(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "build.py"
            path.write_text("def run(): pass\n", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                patch_build(path)


if __name__ == "__main__":
    unittest.main()
