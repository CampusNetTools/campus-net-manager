# -*- coding: utf-8 -*-
"""断网时间线 / 隧道口令 / 中继伪装检测 测试"""
import os
import sys
import json
import tempfile
import unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keepalive_core as core
import shared_proxy as sp


class OutageTimelineTests(unittest.TestCase):
    """断网时间线: 断/恢复配对 + 时长计算"""

    def _write(self, events):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False, encoding="utf-8")
        for e in events:
            tmp.write(json.dumps(e, ensure_ascii=False) + "\n")
        tmp.close()
        return tmp.name

    def _patch_history(self, path):
        self._orig = core.HISTORY_PATH
        core.HISTORY_PATH = path

    def tearDown(self):
        if hasattr(self, "_orig"):
            core.HISTORY_PATH = self._orig
        for f in getattr(self, "_files", []):
            try:
                os.unlink(f)
            except Exception:
                pass

    def test_pairing_and_duration(self):
        ev = [
            {"time": "2026-09-04 10:00:00", "event": "disconnect", "message": "掉线"},
            {"time": "2026-09-04 10:05:00", "event": "recovery", "message": "恢复"},
            {"time": "2026-09-04 11:00:00", "event": "disconnect", "message": "掉线2"},
            {"time": "2026-09-04 11:30:00", "event": "recovery", "message": "恢复2"},
        ]
        p = self._write(ev)
        self._patch_history(p)
        self._files = [p]
        outages = core.analyze_outage_timeline(days=7)
        self.assertEqual(len(outages), 2)
        self.assertEqual(outages[0]["duration_s"], 300)
        self.assertEqual(outages[1]["duration_s"], 1800)

    def test_unrecovered_outage(self):
        ev = [{"time": "2026-09-04 10:00:00", "event": "disconnect", "message": "未恢复"}]
        p = self._write(ev)
        self._patch_history(p)
        self._files = [p]
        outages = core.analyze_outage_timeline(days=7)
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0]["end"], "至今未恢复")

    def test_fmt_duration(self):
        self.assertEqual(core._fmt_duration(45), "45秒")
        self.assertEqual(core._fmt_duration(90), "1分30秒")
        self.assertEqual(core._fmt_duration(3600), "1小时0分")
        self.assertEqual(core._fmt_duration(90000), "1天1小时")


class TunnelKeyTests(unittest.TestCase):
    """隧道共享口令"""

    def test_gen_tunnel_key(self):
        k1 = core.gen_tunnel_key()
        k2 = core.gen_tunnel_key()
        self.assertEqual(len(k1), 16)
        self.assertNotEqual(k1, k2)
        # 不含易混淆字符
        for ch in k1:
            self.assertNotIn(ch, "0O1lI")


class RelayStealthTests(unittest.TestCase):
    """中继伪装检测"""

    def test_vender_lookup(self):
        self.assertEqual(core.vender_lookup("d4:46:3a:7b:ee:58"), "华为")
        self.assertEqual(core.vender_lookup("50:fa:84:11:22:33"), "TP-LINK")
        self.assertEqual(core.vender_lookup("ff:ff:ff:ff:ff:ff"), "")

    def test_risk_levels(self):
        # count<=0 low, <=2 mid, >2 high
        self.assertEqual(core.relay_stealth_check()["risk"] in ("low", "mid", "high"), True)


class SharedProxyKeyTests(unittest.TestCase):
    """隧道口令校验 (共享代理)"""

    def _make_proxy(self, shared_key="secret123"):
        p = sp.SharedProxy(port=0, host="127.0.0.1", shared_key=shared_key)
        return p

    def test_shared_key_stored(self):
        p = self._make_proxy("abc")
        self.assertEqual(p.shared_key, "abc")
        p2 = sp.SharedProxy()
        self.assertEqual(p2.shared_key, "")  # 未设置则空(兼容旧)


if __name__ == "__main__":
    unittest.main()
