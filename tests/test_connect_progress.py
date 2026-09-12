# -*- coding: utf-8 -*-
"""v5.3.0「连接进度」测试。

覆盖两块 (都不依赖 tkinter, 本机可直接跑):
  - core.recovery: 启动时长解析 / 阶段判定 / 进度与加速建议
另附 GUI 源码断言 (读文件而非导入), 确认新窗口已接进主界面。
"""
import os
import unittest

import keepalive_core as core  # noqa: F401
from core import recovery as core_recovery

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _snap(relay_ip="", auth="", net="", ssid="LIDA-UNIVERSITY", uptime="24 min"):
    return {
        "relay": {"ssid": ssid, "signal": "-49", "ip": relay_ip},
        "ap": {"ssid": "Xiaomi"},
        "auth": auth,
        "net": net,
        "sys": {"uptime": uptime},
    }


class TestParseUptime(unittest.TestCase):
    """busybox / procps 常见 uptime 写法都要能解析。"""

    def test_minutes(self):
        self.assertEqual(core_recovery.parse_uptime_seconds("24 min"), 24 * 60)

    def test_hh_mm(self):
        self.assertEqual(core_recovery.parse_uptime_seconds("20:23"), 20 * 3600 + 23 * 60)

    def test_hh_mm_ss(self):
        self.assertEqual(core_recovery.parse_uptime_seconds("1:02:03"), 3723)

    def test_days_singular(self):
        self.assertEqual(core_recovery.parse_uptime_seconds("1 day, 2:03"), 86400 + 7380)

    def test_days_plural(self):
        self.assertEqual(core_recovery.parse_uptime_seconds("3 days, 04:05"), 3 * 86400 + 14700)

    def test_garbage_returns_none(self):
        for bad in ("", None, "junk", "  "):
            self.assertIsNone(core_recovery.parse_uptime_seconds(bad))


class TestDetectStage(unittest.TestCase):
    """阶段从"工作台可达"一路到"外网连通"。"""

    def test_unreachable_is_stage0(self):
        self.assertEqual(core_recovery.detect_stage(None, reachable=False), 0)
        self.assertEqual(core_recovery.detect_stage(_snap(), reachable=False), 0)

    def test_boot_stage_when_no_relay_ip(self):
        self.assertEqual(core_recovery.detect_stage(_snap(), reachable=True), 1)

    def test_relay_stage_when_ip_present(self):
        self.assertEqual(core_recovery.detect_stage(_snap(relay_ip="10.0.0.2")), 2)

    def test_auth_stage(self):
        self.assertEqual(
            core_recovery.detect_stage(_snap(relay_ip="10.0.0.2", auth="已登录在线")), 3)

    def test_net_stage_wins_over_auth(self):
        self.assertEqual(
            core_recovery.detect_stage(
                _snap(relay_ip="10.0.0.2", auth="已登录在线", net="正常")), 4)


class TestEvaluateProgress(unittest.TestCase):
    """进度单调、不越级, 卡住时给出加速建议。"""

    def test_online_is_100(self):
        info = core_recovery.evaluate_progress(
            _snap(relay_ip="10.0.0.2", auth="已登录在线", net="正常"))
        self.assertEqual(info["progress"], 100.0)
        self.assertEqual(info["stage_key"], "net")
        self.assertIsNone(info["advice"])

    def test_creep_never_crosses_next_stage(self):
        """阶段内爬升必须留有余量, 不能假装已完成下一阶段。"""
        info = core_recovery.evaluate_progress(_snap(), reachable=True, stage_seconds=600)
        self.assertEqual(info["stage_key"], "boot")
        self.assertLess(info["progress"], 45)

    def test_advice_after_threshold_on_boot(self):
        early = core_recovery.evaluate_progress(_snap(), stage_seconds=5)
        self.assertIsNone(early["advice"])
        late = core_recovery.evaluate_progress(_snap(), stage_seconds=21)
        self.assertEqual(late["advice"], "reconnect_relay")
        self.assertTrue(late["stalled"])

    def test_advice_after_threshold_on_auth(self):
        snap = _snap(relay_ip="10.0.0.2", auth="未登录")
        self.assertIsNone(core_recovery.evaluate_progress(snap, stage_seconds=9)["advice"])
        self.assertEqual(
            core_recovery.evaluate_progress(snap, stage_seconds=11)["advice"], "relogin")

    def test_stage_flags(self):
        info = core_recovery.evaluate_progress(_snap(relay_ip="10.0.0.2"))
        flags = [(s["key"], s["done"], s["active"]) for s in info["stages"]]
        self.assertEqual(flags[0], ("wait", True, False))
        self.assertEqual(flags[1], ("boot", True, False))
        self.assertEqual(flags[2], ("relay", False, True))
        self.assertIn("中继已连上", info["detail"])


class TestConnectProgressUiSource(unittest.TestCase):
    """GUI 源码断言: 窗口与主界面入口都必须存在。"""

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(ROOT, "gui", "connect_progress_ui.py"),
                  "r", encoding="utf-8") as fh:
            cls.src = fh.read()
        with open(os.path.join(ROOT, "app_gui.py"), "r", encoding="utf-8") as fh:
            cls.app = fh.read()

    def test_window_and_mixin(self):
        self.assertIn("class ConnectProgressMixin", self.src)
        self.assertIn("def show_connect_progress_window", self.src)

    def test_progressbar_and_auto_accel(self):
        self.assertIn("ttk.Progressbar", self.src)
        self.assertIn("自动加速", self.src)
        self.assertIn("core_recovery.evaluate_progress", self.src)
        self.assertIn("reconnect_relay", self.src)
        self.assertIn("relogin", self.src)

    def test_registered_in_app(self):
        self.assertIn("ConnectProgressMixin", self.app)
        self.assertIn("show_connect_progress_window", self.app)
        self.assertIn("连接进度", self.app)


if __name__ == "__main__":
    unittest.main()
