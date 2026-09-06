# -*- coding: utf-8 -*-
"""v4.0.3 偏好设置扩展测试: 历史路径可选 + 软件更新内联入口。

覆盖:
- core.history.effective_log_path: 绝对路径优先 / 相对路径拼 BASE_DIR / 空字符串走默认
- core.history.set_log_path: 同步后 summarize/analyze 都用新路径
- core.history.record_network_history: 关闭时不写 / 开启时写到自定义路径
- core.config.ensure_preferences: history_log_path 默认值存在
"""
import json
import os
import tempfile
import unittest

import keepalive_core as core
from core import history


class TestHistoryLogPath(unittest.TestCase):
    def setUp(self):
        # 重置模块变量 + 准备临时目录 + 隔离默认路径(避免本地残留数据干扰)
        history.set_log_path(None)
        self._tmpdir = tempfile.mkdtemp(prefix="cnm_pref_test_")
        self._default_path = os.path.join(core.common.BASE_DIR, "network_history.jsonl")
        self._default_existed = os.path.exists(self._default_path)
        if self._default_existed:
            import shutil
            shutil.move(self._default_path, self._default_path + ".bak_test")
        # 让 summarize/analyze 也读不到任何东西
        history.set_log_path(os.path.join(self._tmpdir, "_empty.jsonl"))

    def tearDown(self):
        if getattr(self, "_default_existed", False):
            src = self._default_path + ".bak_test"
            if os.path.exists(src):
                import shutil
                shutil.move(src, self._default_path)
        history.set_log_path(None)

    def test_default_when_empty(self):
        self.assertEqual(history.effective_log_path({}),
                         os.path.join(core.common.BASE_DIR, "network_history.jsonl"))

    def test_absolute_path_used(self):
        custom = os.path.join(self._tmpdir, "my_history.jsonl")
        self.assertEqual(history.effective_log_path({"history_log_path": custom}), custom)

    def test_relative_path_joined_to_base(self):
        out = history.effective_log_path({"history_log_path": "subdir/x.jsonl"})
        self.assertTrue(out.endswith(os.path.join("subdir", "x.jsonl")))
        self.assertTrue(os.path.isabs(out))

    def test_record_writes_to_custom_path(self):
        custom = os.path.join(self._tmpdir, "custom.jsonl")
        cfg = {"history_enabled": True, "history_log_path": custom}
        ok = history.record_network_history(cfg, "online", "测试",
                                             net="wifi", ip="10.0.0.1")
        self.assertTrue(ok)
        self.assertTrue(os.path.exists(custom))
        with open(custom, "r", encoding="utf-8") as fh:
            line = json.loads(fh.readline())
        self.assertEqual(line["event"], "online")
        self.assertEqual(line["details"]["ip"], "10.0.0.1")
        # reader 也能读到(同步切换了模块变量)
        summary = history.summarize_network_history(7)
        self.assertEqual(summary["events"], 1)
        self.assertEqual(summary["counts"]["online"], 1)

    def test_record_skipped_when_disabled(self):
        custom = os.path.join(self._tmpdir, "skipped.jsonl")
        cfg = {"history_enabled": False, "history_log_path": custom}
        self.assertFalse(history.record_network_history(cfg, "online", "应被忽略"))
        self.assertFalse(os.path.exists(custom))

    def test_cfg_history_log_path_overrides_module_var(self):
        """record_network_history 始终用 cfg['history_log_path'], 不被默认污染。"""
        new_path = os.path.join(self._tmpdir, "explicit.jsonl")
        cfg = {"history_enabled": True, "history_log_path": new_path}
        history.record_network_history(cfg, "online", "显式路径")
        self.assertTrue(os.path.exists(new_path))
        with open(new_path, "r", encoding="utf-8") as fh:
            line = json.loads(fh.readline())
        self.assertEqual(line["event"], "online")

    def test_set_log_path_synchronizes_reader(self):
        """set_log_path 后, summarize/analyze 立即用新路径(用户偏好保存场景)。"""
        new_path = os.path.join(self._tmpdir, "switched.jsonl")
        cfg = {"history_enabled": True, "history_log_path": new_path}
        history.record_network_history(cfg, "disconnect", "偏好切到新路径")
        history.set_log_path(new_path)  # 模拟 save_preferences 后同步
        summary = history.summarize_network_history(7)
        self.assertEqual(summary["events"], 1)
        self.assertEqual(summary["counts"]["disconnect"], 1)
        # analyze_outage_timeline 读到 1 条未恢复的 disconnect
        out = history.analyze_outage_timeline(7)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["message"], "偏好切到新路径")
        self.assertIn("至今未恢复", out[0]["end"])

    def test_analyze_outage_uses_custom_path(self):
        """analyze_outage_timeline 读 get_log_path()(已 set_log_path 切过的)。"""
        new_path = os.path.join(self._tmpdir, "outage.jsonl")
        # 直接写入一行 disconnect
        with open(new_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"time": "2099-01-01 00:00:00",
                                  "event": "disconnect",
                                  "message": "测试",
                                  "details": {}}, ensure_ascii=False) + "\n")
        history.set_log_path(new_path)
        out = history.analyze_outage_timeline(7)
        self.assertEqual(len(out), 1)
        self.assertIn("至今未恢复", out[0]["end"])


class TestConfigDefaultHistoryPath(unittest.TestCase):
    def test_history_log_path_default_added(self):
        cfg = {}
        changed = core.ensure_preferences(cfg)
        self.assertTrue(changed)
        self.assertIn("history_log_path", cfg)
        self.assertEqual(cfg["history_log_path"], "")
        self.assertFalse(cfg["history_enabled"])
        self.assertTrue(cfg["kick_guard"])
        self.assertTrue(cfg["auto_update_check"])

    def test_existing_history_log_path_preserved(self):
        cfg = {"history_log_path": "/tmp/already_set.jsonl"}
        core.ensure_preferences(cfg)
        self.assertEqual(cfg["history_log_path"], "/tmp/already_set.jsonl")


if __name__ == "__main__":
    unittest.main()
