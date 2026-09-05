# -*- coding: utf-8 -*-
"""守护韧性测试: 连续异常告警/退避、健康循环清零、界面回调异常隔离、回调签名防回归。

历史教训: on_status 回调签名从 3 参扩展为 5 参时测试 lambda 未同步,
TypeError 被守护兜底静默捕获导致无限重试(测试卡死 15 分钟+)。
"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keepalive_core as core  # noqa: E402


class _FakeStop:
    """可控的停止事件替身: 前 max_waits 次 wait 立即返回 False, 之后返回 True。"""

    def __init__(self, max_waits):
        self.waits = 0
        self.max_waits = max_waits
        self.wait_seconds = []

    def is_set(self):
        return False

    def set(self):
        pass

    def wait(self, seconds):
        self.waits += 1
        self.wait_seconds.append(seconds)
        return self.waits > self.max_waits


class ConsecutiveErrorTests(unittest.TestCase):
    """守护循环连续抛异常: 计数、告警一次、退避延长, 且最终能退出。"""

    def test_consecutive_errors_alert_once_and_backoff(self):
        cfg = {"profiles": [], "active_profile": ""}
        alerts = []
        daemon = core.KeepAliveDaemon(cfg, on_alert=lambda text, cat: alerts.append((text, cat)))
        daemon._stop = _FakeStop(max_waits=12)
        with patch.object(core, "log", side_effect=lambda text: text), \
                patch.object(core, "get_connection_mode",
                             side_effect=RuntimeError("boom")):
            daemon.run()
        self.assertEqual(daemon._consecutive_errors, 13)  # max_waits 12 + 跳出前最后一轮
        # 连续异常告警只发一次, 类别为 failure
        err_alerts = [a for a in alerts if "守护连续异常" in a[0]]
        self.assertEqual(len(err_alerts), 1)
        self.assertEqual(err_alerts[0][1], "failure")
        # 前 4 次退避 5 秒, 第 5 次起延长到 60 秒
        self.assertEqual(daemon._stop.wait_seconds[:5], [5, 5, 5, 5, 60])

    def test_error_counter_resets_on_healthy_cycle(self):
        profile = core.default_profile("家里WiFi")
        cfg = {"profiles": [profile], "active_profile": profile["name"],
               "history_enabled": False}
        daemon = core.KeepAliveDaemon(cfg)
        daemon._stop = _FakeStop(max_waits=5)
        with patch.object(core, "log", side_effect=lambda text: text), \
                patch.object(core, "get_connection_mode", return_value=("wifi", "HomeWiFi")), \
                patch.object(core, "get_gateway", return_value="192.168.1.1"), \
                patch.object(core, "auth_reachable", return_value=False), \
                patch.object(core, "best_match_profile", return_value=(None, None)), \
                patch.object(core, "check_internet",
                             side_effect=[RuntimeError("抖动"), True]), \
                patch.object(core, "record_network_history"), \
                patch.object(daemon, "_wait_or_break", return_value=True):
            daemon.run()
        # 第一次循环异常(计数1), 第二次健康循环后清零
        self.assertEqual(daemon._consecutive_errors, 0)
        self.assertFalse(daemon._error_alerted)


class CallbackIsolationTests(unittest.TestCase):
    """界面回调抛错: 被隔离记录, 不污染守护异常计数, 守护正常完成一轮。"""

    def _run_daemon(self, on_status):
        profile = core.default_profile("测试档案")
        profile.update({"username": "user", "password": "secret"})
        cfg = {"profiles": [profile], "active_profile": profile["name"],
               "history_enabled": False}
        logs = []
        daemon = core.KeepAliveDaemon(
            cfg,
            on_log=lambda line: logs.append(line),
            on_status=on_status)
        offline = {"vpn": True, "current": True, "physical": True}
        online = {"vpn": True, "current": True, "physical": True}
        with patch.object(core, "log", side_effect=lambda text: text), \
                patch.object(core, "get_connection_mode", return_value=("wired", "")), \
                patch.object(core, "get_gateway", return_value="10.12.255.254"), \
                patch.object(core, "match_profile", return_value=profile), \
                patch.object(core, "auth_reachable", return_value=True), \
                patch.object(core, "check_auth", side_effect=[False, True]), \
                patch.object(core, "check_network_paths", side_effect=[offline, online]), \
                patch.object(core, "ensure_login", return_value=True), \
                patch.object(core, "record_network_history"), \
                patch.object(daemon, "_wait_or_break", return_value=True):
            daemon.run()
        return daemon, logs

    def test_callback_exception_isolated(self):
        def bad_callback(*_args):
            raise TypeError("模拟回调签名失配")
        daemon, _logs = self._run_daemon(bad_callback)
        # 回调异常不计入守护异常, 守护正常结束而不是死循环
        self.assertEqual(daemon._consecutive_errors, 0)

    def test_on_status_signature_five_args(self):
        received = []
        daemon, _logs = self._run_daemon(lambda *args: received.append(args))
        self.assertTrue(received)
        for args in received:
            self.assertEqual(len(args), 5)


if __name__ == "__main__":
    unittest.main()
