import unittest

from gui.preferences import PreferencesMixin


class _Widget:
    def __init__(self):
        self.options = {}
        self.hidden = False
        self.destroyed = False

    def configure(self, **options):
        self.options.update(options)

    def pack_forget(self):
        self.hidden = True

    def destroy(self):
        self.destroyed = True


class _Harness:
    def __init__(self):
        self.update_text = ""
        self.pref_update_text = ""
        self._btn_update_now = _Widget()
        self._btn_pref_check = _Widget()
        self._btn_pref_update_now = _Widget()
        self._pref_update_info = object()

    def _set_update_text(self, text):
        self.update_text = text

    def _set_pref_upd_text(self, text):
        self.pref_update_text = text

    def _pref_check_update(self):
        return None


class UpdateUiStateTests(unittest.TestCase):
    def test_network_failure_is_not_shown_as_latest(self):
        harness = _Harness()
        update_button = harness._btn_pref_update_now
        info = {"status": "error", "error": "无法读取 GitHub 最新版本"}

        PreferencesMixin._render_update_result(harness, info)
        PreferencesMixin._render_pref_update_result(harness, info)

        self.assertIn("失败", harness.update_text)
        self.assertIn("失败", harness.pref_update_text)
        self.assertTrue(harness._btn_update_now.hidden)
        self.assertTrue(update_button.destroyed)
        self.assertIsNone(harness._btn_pref_update_now)
        self.assertIsNone(harness._pref_update_info)
        self.assertEqual(harness._btn_pref_check.options["text"], "立即检查")

    def test_ahead_candidate_is_distinguished_from_latest_release(self):
        harness = _Harness()
        update_button = harness._btn_pref_update_now
        info = {"status": "ahead", "latest_tag": "v5.5.0"}

        PreferencesMixin._render_update_result(harness, info)
        PreferencesMixin._render_pref_update_result(harness, info)

        self.assertIn("高于最新公开版", harness.update_text)
        self.assertIn("v5.5.0", harness.pref_update_text)
        self.assertTrue(harness._btn_update_now.hidden)
        self.assertTrue(update_button.destroyed)
        self.assertIsNone(harness._btn_pref_update_now)
        self.assertEqual(harness._btn_pref_check.options["text"], "立即检查")

    def test_current_version_remains_reported_as_latest(self):
        harness = _Harness()
        update_button = harness._btn_pref_update_now
        info = {"status": "current", "tag": "v5.6.0"}

        PreferencesMixin._render_update_result(harness, info)
        PreferencesMixin._render_pref_update_result(harness, info)

        self.assertIn("已是最新版本", harness.update_text)
        self.assertIn("已是最新版本", harness.pref_update_text)
        self.assertTrue(harness._btn_update_now.hidden)
        self.assertTrue(update_button.destroyed)
        self.assertIsNone(harness._btn_pref_update_now)


if __name__ == "__main__":
    unittest.main()
