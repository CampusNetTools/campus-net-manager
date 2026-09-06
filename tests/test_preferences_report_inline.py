# -*- coding: utf-8 -*-
"""v4.0.3 网络报告段融入偏好设置 + _pref_refresh_report 实现正确性。"""
import json
import os
import tempfile
import unittest

import keepalive_core as core
from core import history


class TestPrefReportRendering(unittest.TestCase):
    """_pref_refresh_report 的核心逻辑: 同步路径 + 调 summarize/analyze 渲染结果。

    这里只覆盖 pure 函数级别(不弹 Tkinter 窗口), GUI 渲染顺序在手工冒烟里覆盖。
    """

    def setUp(self):
        history.set_log_path(None)
        self._tmpdir = tempfile.mkdtemp(prefix="cnm_rep_test_")
        self._default_path = os.path.join(core.common.BASE_DIR, "network_history.jsonl")
        self._default_existed = os.path.exists(self._default_path)
        if self._default_existed:
            import shutil
            shutil.move(self._default_path, self._default_path + ".bak_report_test")
        # reader 切到一个不存在文件, 避免污染
        history.set_log_path(os.path.join(self._tmpdir, "_empty.jsonl"))

    def tearDown(self):
        if getattr(self, "_default_existed", False):
            src = self._default_path + ".bak_report_test"
            if os.path.exists(src):
                import shutil
                shutil.move(src, self._default_path)
        history.set_log_path(None)

    def _render_summary(self, path):
        """模拟 _pref_refresh_report 内部数据生成步骤。"""
        history.set_log_path(path)
        data = core.summarize_network_history(7)
        outages = core.analyze_outage_timeline(7)
        return data, outages

    def test_empty_when_no_history(self):
        """未启用 → 0 事件 + 0 断网时间线。"""
        data, outages = self._render_summary(os.path.join(self._tmpdir, "empty.jsonl"))
        self.assertEqual(data["events"], 0)
        self.assertEqual(outages, [])

    def test_summary_counts_online(self):
        new_path = os.path.join(self._tmpdir, "report.jsonl")
        cfg = {"history_enabled": True, "history_log_path": new_path}
        history.record_network_history(cfg, "online", "ok")
        history.record_network_history(cfg, "online", "ok2")
        history.record_network_history(cfg, "disconnect", "掉了")
        history.record_network_history(cfg, "recovery", "恢复了")
        data, outages = self._render_summary(new_path)
        self.assertEqual(data["events"], 4)
        self.assertEqual(data["counts"]["online"], 2)
        self.assertEqual(data["counts"]["disconnect"], 1)
        self.assertEqual(data["counts"]["recovery"], 1)
        # 1 次未恢复的(因为 disconnect 后没跟 recovery)
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0]["message"], "掉了")

    def test_paired_outages_get_duration(self):
        """disconnect + recovery 配对 → outages 含 duration。"""
        new_path = os.path.join(self._tmpdir, "paired.jsonl")
        with open(new_path, "w", encoding="utf-8") as fh:
            fh.write(json.dumps({"time": "2099-01-01 10:00:00",
                                  "event": "disconnect", "message": "掉",
                                  "details": {}}, ensure_ascii=False) + "\n")
            fh.write(json.dumps({"time": "2099-01-01 10:05:00",
                                  "event": "recovery", "message": "回",
                                  "details": {}}, ensure_ascii=False) + "\n")
        data, outages = self._render_summary(new_path)
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0]["duration_s"], 300)
        self.assertEqual(outages[0]["message"], "掉")

    def test_summary_text_contains_users(self):
        """生成的 summary 文本含人类可读字段, 而不是空 / 错误码。"""
        new_path = os.path.join(self._tmpdir, "ok.jsonl")
        cfg = {"history_enabled": True, "history_log_path": new_path}
        history.record_network_history(cfg, "online", "ok")
        data, _ = self._render_summary(new_path)
        self.assertIn("网络", data["summary"])
        self.assertIn("events", data)
        self.assertIn("counts", data)


if __name__ == "__main__":
    unittest.main()
