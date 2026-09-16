# -*- coding: utf-8 -*-
"""v5.2.0 路由器工作台运行时诊断测试。

覆盖三块新增纯逻辑 (core.router, 不依赖 tkinter, 本机可直接跑):
  - parse_keeper_log     守护日志解析
  - keeper_log_health    掉线重连风暴识别 + 时钟偏差换算
  - clock_skew_seconds   HTTP Date 头 -> 路由器时钟偏差
  - probe_tcp_port       SSH 等端口连通性自检

另附 GUI 源码断言 (读文件而非导入, 避免本机无 tkinter 时无法运行):
  工作台窗口必须把「深度自检 / 清空日志 / 代理面板 9091 / MLO(hostapd) /
  三套密码说明」等路由器管理界面看不到的能力接进来。
"""
import datetime
import os
import socket
import unittest

import keepalive_core as core  # noqa: F401  (统一入口, 顺带校验导出)
from core import router as core_router

RECONNECT_LINE = "自愈: 中继接口无 IP -> 已尝试重连 (ifup wwan)"


def _log(*timestamps):
    return "~".join("%s %s" % (ts, RECONNECT_LINE) for ts in timestamps)


class TestParseKeeperLog(unittest.TestCase):
    """守护日志解析: 条目切分 / 时间提取 / 重连标记 / 容错。"""

    def test_split_and_flags(self):
        raw = _log("2026-09-11 18:59:48", "2026-09-11 19:05:45") + "~~~"
        entries = core_router.parse_keeper_log(raw)
        self.assertEqual(len(entries), 2)          # 尾部空段被丢弃
        self.assertTrue(all(e["reconnect"] for e in entries))
        self.assertEqual(entries[0]["ts"], datetime.datetime(2026, 9, 11, 18, 59, 48))

    def test_limit_keeps_tail(self):
        raw = _log("2026-09-11 18:00:00", "2026-09-11 19:00:00", "2026-09-11 20:00:00")
        entries = core_router.parse_keeper_log(raw, limit=2)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[-1]["ts"], datetime.datetime(2026, 9, 11, 20, 0, 0))

    def test_newline_separated_and_plain_lines(self):
        entries = core_router.parse_keeper_log("随机文本\n2026-09-11 20:00:00 一切正常")
        self.assertEqual(len(entries), 2)
        self.assertIsNone(entries[0]["ts"])        # 时间无法解析也要保留条目
        self.assertFalse(entries[0]["reconnect"])
        self.assertIsNotNone(entries[1]["ts"])

    def test_empty_input(self):
        self.assertEqual(core_router.parse_keeper_log(""), [])
        self.assertEqual(core_router.parse_keeper_log(None), [])


class TestKeeperLogHealth(unittest.TestCase):
    """健康度: 最近 stale_minutes 内仍重连 = 尚未稳定。"""

    def test_recent_reconnect_marks_unhealthy(self):
        now = datetime.datetime(2026, 9, 11, 21, 0, 0)
        entries = core_router.parse_keeper_log(_log("2026-09-11 20:56:00"))
        health = core_router.keeper_log_health(entries, now=now)
        self.assertFalse(health["healthy"])
        self.assertFalse(health["clock_anomaly"])
        self.assertIn("注意", health["summary"])
        self.assertEqual(health["recent_reconnects"], 1)

    def test_stale_reconnect_marks_healthy(self):
        now = datetime.datetime(2026, 9, 11, 21, 0, 0)
        entries = core_router.parse_keeper_log(_log("2026-09-11 19:00:00"))
        health = core_router.keeper_log_health(entries, now=now)
        self.assertTrue(health["healthy"])
        self.assertIn("已稳定", health["summary"])
        self.assertAlmostEqual(health["last_age_min"], 120.0, delta=0.2)

    def test_clock_offset_can_unmask_ongoing_storm(self):
        """路由器时钟偏快时, 未校正会把"正在重连"误判成"已稳定"。

        日志写 22:00, 本机此刻 21:10: 若路由器快 1 小时, 实际发生在本机 21:00 (10 分钟前)。
        """
        now = datetime.datetime(2026, 9, 11, 21, 10, 0)
        entries = core_router.parse_keeper_log(_log("2026-09-11 22:00:00"))
        naive = core_router.keeper_log_health(entries, now=now)
        fixed = core_router.keeper_log_health(entries, now=now, clock_offset_sec=3600)
        self.assertTrue(naive["healthy"])              # 未校正: 时间在未来, 标为时钟异常
        self.assertTrue(naive["clock_anomaly"])
        self.assertIn("时钟偏差", naive["summary"])
        self.assertFalse(fixed["healthy"])             # 校正后: 10 分钟前仍在重连 -> 告警
        self.assertFalse(fixed["clock_anomaly"])

    def test_empty_log_is_healthy_with_no_record(self):
        health = core_router.keeper_log_health([])
        self.assertTrue(health["healthy"])
        self.assertEqual(health["summary"], "无记录")
        self.assertEqual(health["reconnects"], 0)

    def test_unparsable_times_do_not_crash(self):
        entries = core_router.parse_keeper_log("没有时间戳的条目")
        health = core_router.keeper_log_health(entries, now=datetime.datetime(2026, 9, 11, 21, 0, 0))
        self.assertIn("时间无法解析", health["summary"])
        self.assertTrue(health["healthy"])

    def test_clock_corrected_timestamps_do_not_false_alarm(self):
        """时钟漂移期写入的日志, 校正后"看着很新", 但按日志节奏应判为已停息。

        本机实测: 守护每约 6 分钟记一条, 最后一条写于漂移期(标 21:53);
        时钟被 NTP 校正后按本机时间只"过去 14 分钟", 若只看 15 分钟阈值会误报。
        """
        now = datetime.datetime(2026, 9, 11, 22, 8, 0)
        stamps = ["2026-09-11 20:%02d:46" % m for m in (11, 17, 23, 29, 35, 41, 47, 53)]
        stamps += ["2026-09-11 21:47:46", "2026-09-11 21:53:46"]
        health = core_router.keeper_log_health(
            core_router.parse_keeper_log(_log(*stamps)), now=now)
        self.assertAlmostEqual(health["cadence_min"], 6.0, delta=0.5)
        self.assertTrue(health["healthy"])
        self.assertIn("已稳定", health["summary"])

    def test_prev_marker_suppresses_false_alarm(self):
        """与上次检查相比最新条目未变 -> 本轮无新增, 直接判稳定。"""
        now = datetime.datetime(2026, 9, 11, 21, 0, 0)
        entries = core_router.parse_keeper_log(_log("2026-09-11 20:56:00"))
        first = core_router.keeper_log_health(entries, now=now)
        self.assertFalse(first["healthy"])            # 首次: 距今 4 分钟, 疑似仍在重连
        second = core_router.keeper_log_health(entries, now=now, prev=first)
        self.assertTrue(second["no_new_events"])
        self.assertTrue(second["healthy"])
        self.assertIn("无新增", second["summary"])

    def test_new_event_resets_stability(self):
        """出现新条目时, 上一轮的"无新增"不能掩盖本轮的新重连。"""
        now = datetime.datetime(2026, 9, 11, 21, 0, 0)
        prev = core_router.keeper_log_health(
            core_router.parse_keeper_log(_log("2026-09-11 20:30:00")), now=now)
        entries = core_router.parse_keeper_log(_log("2026-09-11 20:30:00", "2026-09-11 20:58:00"))
        health = core_router.keeper_log_health(entries, now=now, prev=prev)
        self.assertFalse(health["no_new_events"])
        self.assertFalse(health["healthy"])
        self.assertIn("注意", health["summary"])
        self.assertIn("持续", health["summary"])


class TestClockSkew(unittest.TestCase):
    """HTTP Date 头 -> 偏差秒数 (正 = 路由器偏快)。"""

    def test_exact_seconds(self):
        now = datetime.datetime(2026, 9, 11, 20, 46, 10, tzinfo=datetime.timezone.utc)
        skew = core_router.clock_skew_seconds("Fri, 11 Sep 2026 20:48:31 GMT", now=now)
        self.assertEqual(skew, 141)

    def test_month_case_insensitive(self):
        now = datetime.datetime(2026, 9, 11, 20, 46, 10, tzinfo=datetime.timezone.utc)
        skew = core_router.clock_skew_seconds("Fri, 11 SEP 2026 20:46:10 GMT", now=now)
        self.assertEqual(skew, 0)

    def test_invalid_headers(self):
        for bad in ("", None, "not-a-date", "Fri, 11 Xxx 2026 20:46:10 GMT"):
            self.assertIsNone(core_router.clock_skew_seconds(bad))

    def test_naive_now_is_treated_as_utc(self):
        now = datetime.datetime(2026, 9, 11, 20, 46, 10)
        self.assertEqual(
            core_router.clock_skew_seconds("Fri, 11 Sep 2026 20:46:10 GMT", now=now), 0)

    def test_local_time_mislabeled_as_gmt(self):
        """busybox 把本地时间标成 GMT: 传入本机时区偏移后可还原真实偏差。

        本机实测: 路由器 Date 写 22:09:54 GMT, 而真实 UTC 是 14:07:32,
        差的 8 小时其实是时区标注问题, 真实偏移只有 142 秒。
        """
        now = datetime.datetime(2026, 9, 11, 14, 7, 32, tzinfo=datetime.timezone.utc)
        skew = core_router.clock_skew_seconds(
            "Fri, 11 Sep 2026 22:09:54 GMT", now=now, tz_offset_sec=8 * 3600)
        self.assertEqual(skew, 142)

    def test_local_utc_offset_seconds_is_int_minutes(self):
        off = core_router.local_utc_offset_seconds()
        self.assertIsInstance(off, int)
        self.assertEqual(off % 60, 0)


class TestProbeTcpPort(unittest.TestCase):
    """端口自检: 只做连通性判断, 不发送任何协议数据。"""

    def test_open_port_true(self):
        srv = socket.socket()
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        port = srv.getsockname()[1]
        try:
            self.assertTrue(core_router.probe_tcp_port("127.0.0.1", port, timeout=1.0))
        finally:
            srv.close()

    def test_closed_port_false(self):
        probe = socket.socket()
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
        probe.close()
        self.assertFalse(core_router.probe_tcp_port("127.0.0.1", port, timeout=0.8))

    def test_invalid_port_returns_false(self):
        """非法端口 / 异常目标必须立即返回 False, 不向外抛异常。

        (不用不可达主机名做用例: 校园网 DNS 解析失败要 10s+, 会拖慢整个测试套件)
        """
        self.assertFalse(core_router.probe_tcp_port("127.0.0.1", "not-a-port", timeout=0.3))


class TestRouterConsoleUiSource(unittest.TestCase):
    """GUI 源码断言: 路由器侧"管理界面看不到"的能力必须都接进工作台窗口。"""

    @classmethod
    def setUpClass(cls):
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(root, "gui", "router_console_ui.py")
        with open(path, "r", encoding="utf-8") as fh:
            cls.src = fh.read()

    def test_deep_check_button_and_method(self):
        self.assertIn("def _rc_deep_check", self.src)
        self.assertIn("深度自检", self.src)
        self.assertIn("probe_tcp_port", self.src)          # SSH 端口自检
        self.assertIn("portal?action=status", self.src)    # 校园网认证台探测

    def test_clearlog_and_proxy_panel(self):
        self.assertIn('"clearlog"', self.src)
        self.assertIn('"enable_transparent"', self.src)
        self.assertIn('"disable_transparent"', self.src)
        self.assertIn("清空守护日志", self.src)
        self.assertIn("RC_PROXY_PANEL_PORT = 9091", self.src)
        self.assertIn("def _rc_open_proxy_panel", self.src)
        self.assertIn('proxy.get("transparent")', self.src)

    def test_runtime_diagnostics_rendered(self):
        for token in ("parse_keeper_log", "keeper_log_health", "clock_skew_seconds",
                      "_rc_fmt_skew", "自愈守护", "路由器时钟", "mlo_enable"):
            self.assertIn(token, self.src)

    def test_server_date_sourced_from_panel_root(self):
        """工作台 CGI 不返回 Date 头, 必须从面板根取并做时区校正, 否则时钟显示恒定偏差 8 小时。"""
        self.assertIn("def rc_server_date", self.src)
        self.assertIn("def rc_clock_skew", self.src)
        self.assertIn("local_utc_offset_seconds", self.src)
        self.assertIn("_rc_prev_health", self.src)     # 跨次对比, 抑制时钟漂移误报

    def test_router_requests_bypass_system_proxy(self):
        """局域网工作台不得被系统里失效的 VPN/代理地址劫持。"""
        self.assertIn("def rc_urlopen", self.src)
        self.assertIn("ProxyHandler({})", self.src)

    def test_password_relationship_hint(self):
        """窗口内必须说明管理密码 / SSH 密码 / 校园网密码是三套。"""
        self.assertIn("关于密码", self.src)
        self.assertIn("passwd", self.src)
        self.assertIn("三套互不影响", self.src)


if __name__ == "__main__":
    unittest.main()
