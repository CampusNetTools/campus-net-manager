# -*- coding: utf-8 -*-
"""v4.0.4: 偏好设置软件更新段「立即更新」按钮 bug 修复回归。

Bug: 用户偏好设置里点"立即检查"查到新版本后, 找不到"立即更新"按钮。
根因: _render_pref_update_result 把按钮 parent 设成 self (App 根窗口),
pack 到根窗口会被埋在底层不可见。
修复:
  1. 保存 _pref_card 引用 (preferences 的 card Frame)
  2. 把 _btn_pref_update_now parent 改到 _pref_card
  3. 把 _btn_pref_check (立即检查) 自动变成 _btn_pref_update_now (立即更新) — 一键触达
"""
import inspect
import unittest


class TestPrefUpdateButtonFix(unittest.TestCase):
    """v4.0.4 修复: 偏好设置查到新版本时立即更新按钮必须可见。"""

    def test_pref_card_stored(self):
        """show_preferences 必须把 card Frame 保存到 self._pref_card."""
        from gui.preferences import PreferencesMixin
        src = inspect.getsource(PreferencesMixin.show_preferences)
        self.assertIn("self._pref_card", src)

    def test_render_uses_pref_card_parent(self):
        """_render_pref_update_result 创建按钮时 parent 必须用 _pref_card 不是 self."""
        from gui.preferences import PreferencesMixin
        src = inspect.getsource(PreferencesMixin._render_pref_update_result)
        # 必须读 _pref_card 而不是 self
        self.assertIn('getattr(self, "_pref_card"', src)
        # 不能直接 parent=self 创建按钮 (修复前的 bug)
        # 出现位置: ttk.Button(parent, ...) 里的 parent 是局部变量
        self.assertIn("parent = getattr(self, \"_pref_card\", None) or self", src)

    def test_check_button_auto_switches_to_update(self):
        """_render_pref_update_result 必须把 _btn_pref_check 改名为 '立即更新' + 换 command."""
        from gui.preferences import PreferencesMixin
        src = inspect.getsource(PreferencesMixin._render_pref_update_result)
        # 立即检查按钮被重新配置 text="立即更新"
        self.assertIn('text="立即更新"', src)
        # command 重新指派为 _do_update
        self.assertIn("_do_update(self._pref_update_info)", src)
        # 文案说明检查按钮已切换
        self.assertIn("已自动切换", src)


if __name__ == "__main__":
    unittest.main()