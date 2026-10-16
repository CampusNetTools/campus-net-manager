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
        self.assertGreater((root / "mobile" / "assets" / "NotoSansSC.ttf").stat().st_size, 10_000_000)
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
