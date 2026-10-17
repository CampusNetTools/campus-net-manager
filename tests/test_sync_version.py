import tempfile
import unittest
from pathlib import Path

from scripts import sync_version


class SyncAndroidVersionTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.spec_path = Path(self.temp_dir.name) / "buildozer.spec"
        self.readme_path = Path(self.temp_dir.name) / "README.md"
        self.previous_path = sync_version.MOBILE_SPEC_FILE
        self.previous_readme_path = sync_version.README_FILE
        sync_version.MOBILE_SPEC_FILE = str(self.spec_path)
        sync_version.README_FILE = str(self.readme_path)

    def tearDown(self):
        sync_version.MOBILE_SPEC_FILE = self.previous_path
        sync_version.README_FILE = self.previous_readme_path
        self.temp_dir.cleanup()

    def test_syncs_android_version_and_preserves_comment(self):
        original = "[app]\nversion = 1.0.0  # Android build metadata\n"
        self.spec_path.write_text(original, encoding="utf-8")

        self.assertTrue(sync_version.sync_mobile_spec("5.6.0", check_only=False))

        self.assertEqual(
            self.spec_path.read_text(encoding="utf-8"),
            "[app]\nversion = 5.6.0  # Android build metadata\n",
        )

    def test_check_only_reports_mismatch_without_writing(self):
        original = "[app]\nversion = 1.0.0\n"
        self.spec_path.write_text(original, encoding="utf-8")

        self.assertFalse(sync_version.sync_mobile_spec("5.6.0", check_only=True))
        self.assertEqual(self.spec_path.read_text(encoding="utf-8"), original)

    def test_accepts_already_synchronized_version(self):
        self.spec_path.write_text("[app]\nversion = 5.6.0\n", encoding="utf-8")

        self.assertTrue(sync_version.sync_mobile_spec("5.6.0", check_only=True))

    def test_rejects_missing_or_duplicate_version_entries(self):
        for content in ("[app]\n", "[app]\nversion = 1.0.0\nversion = 2.0.0\n"):
            with self.subTest(content=content):
                self.spec_path.write_text(content, encoding="utf-8")
                self.assertFalse(sync_version.sync_mobile_spec("5.6.0", check_only=True))

    def test_syncs_candidate_badge_without_changing_latest_release_badge(self):
        original = (
            "[![Latest Release](https://img.shields.io/badge/Latest%20Release-v5.5.0-green)](release) "
            "[![PR Candidate](https://img.shields.io/badge/PR%20Candidate-v5.5.0-blue)](pull)")
        self.readme_path.write_text(original, encoding="utf-8")

        self.assertTrue(sync_version.sync_readme("5.6.0", check_only=False))

        updated = self.readme_path.read_text(encoding="utf-8")
        self.assertIn("Latest%20Release-v5.5.0-green", updated)
        self.assertIn("PR%20Candidate-v5.6.0-blue", updated)

    def test_check_only_rejects_outdated_candidate_badge(self):
        original = "PR%20Candidate-v5.5.0-blue"
        self.readme_path.write_text(original, encoding="utf-8")

        self.assertFalse(sync_version.sync_readme("5.6.0", check_only=True))
        self.assertEqual(self.readme_path.read_text(encoding="utf-8"), original)

    def test_readme_requires_exactly_one_candidate_badge(self):
        for content in ("no badge", "PR%20Candidate-v1.0.0-blue PR%20Candidate-v2.0.0-blue"):
            with self.subTest(content=content):
                self.readme_path.write_text(content, encoding="utf-8")
                self.assertFalse(sync_version.sync_readme("5.6.0", check_only=True))


if __name__ == "__main__":
    unittest.main()
