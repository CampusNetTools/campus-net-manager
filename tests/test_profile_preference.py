# -*- coding: utf-8 -*-
"""档案匹配回归测试: 用户显式选中的可登录档案不应被空绑定默认档案抢用(热点事故根因)。"""
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keepalive_core as core  # noqa: E402
from core import auth, config, matching, netinfo, sysutils  # noqa: E402

# 场景还原(2026-09-06 事故): active=立达校园网(SSID 绑 LIDA, 有真实凭据);
# 另有一个旧「陆冠霖的热点」档案(SSID/网关全空, 也有凭据)。当前 SSID 是手机热点,
# 经热点走校园网。此前 match_profile 会命中空绑定默认档案去登录, 而不是用户选中的立达档案。


def _mk(name, **kw):
    p = config.default_profile(name)
    p.update({"username": "24012752", "password": "secret",
              "auth_url": "http://192.168.16.3/"})
    p.update(kw)
    return p


class ActiveProfilePreferenceTests(unittest.TestCase):
    def setUp(self):
        self.campus = _mk("立达校园网", ssid="LIDA-UNIVERSITY", preset="lida-campus")
        self.legacy_hotspot = _mk("陆冠霖的热点")  # ssid/gw 全空
        self.cfg = {"profiles": [self.campus, self.legacy_hotspot],
                    "active_profile": "立达校园网"}

    def test_active_campus_wins_over_empty_default(self):
        """active 立达(绑 LIDA) + 当前连手机热点 → 应返回立达而非空绑定默认档案。"""
        p = matching.match_profile(self.cfg, "陆冠霖的热点", "10.52.191.254")
        self.assertEqual(p["name"], "立达校园网")

    def test_gateway_exact_match_still_works(self):
        self.campus["gateway"] = "10.52.191.254"
        p = matching.match_profile(self.cfg, "陆冠霖的热点", "10.52.191.254")
        self.assertEqual(p["name"], "立达校园网")

    def test_ssid_exact_match_still_works(self):
        # 直连 LIDA: SSID 精确命中
        p = matching.match_profile(self.cfg, "LIDA-UNIVERSITY", "")
        self.assertEqual(p["name"], "立达校园网")

    def test_any_network_user_choice_still_respected(self):
        """active 是「任意网络」(空绑定无凭据) → respect_user_choice 应返回它本身, 不登录。"""
        any_net = config.default_profile("任意网络")
        any_net.update({k: None for k in ("username", "password")})
        cfg = {"profiles": [any_net, self.campus],
               "active_profile": "任意网络"}
        p = matching.match_profile(cfg, "手机热点", "192.168.1.1", respect_user_choice=True)
        self.assertEqual(p["name"], "任意网络")

    def test_empty_default_without_creds_still_falls_back_to_campus(self):
        """空绑定且无凭据的默认档案 + 存在有凭据档案 → 回退到有凭据档案(老行为保留)。"""
        plain = config.default_profile("任意网络")
        plain.update({k: None for k in ("username", "password")})
        cfg = {"profiles": [self.campus, plain], "active_profile": "任意网络"}
        # 用户没真正"选任意网络"(respect=False 默认) → 兜底有凭据校园网档案
        p = matching.match_profile(cfg, "别的WiFi", "10.0.0.1")
        self.assertEqual(p["name"], "立达校园网")


class DaemonNoAutoSwitchTests(unittest.TestCase):
    """守护守卫: active 立达可登录 + 认证可达时, 不被空绑定默认档案自动切换。"""

    def _run_daemon(self, cfg, best_profile, best_reason):
        daemon = core.KeepAliveDaemon(cfg)
        campus = next(p for p in cfg["profiles"] if p["name"] == "立达校园网")
        online = {"vpn": True, "current": True, "physical": True}
        logs = []
        daemon.on_log = lambda line: logs.append(line)
        with patch.object(sysutils, "log", side_effect=lambda msg: msg), \
                patch.object(netinfo, "get_connection_mode", return_value=("wifi", "陆冠霖的热点")), \
                patch.object(netinfo, "get_gateway", return_value="10.52.191.254"), \
                patch.object(matching, "match_profile", return_value=campus), \
                patch.object(auth, "auth_reachable", return_value=True), \
                patch.object(matching, "best_match_profile",
                             return_value=(best_profile, best_reason)), \
                patch.object(auth, "check_auth", return_value=True), \
                patch.object(auth, "check_network_paths", return_value=online), \
                patch.object(daemon, "_wait_or_break", return_value=True):
            daemon.run()
        return daemon, logs

    def test_active_serving_campus_is_not_switched(self):
        """active=立达(有凭据), 认证可达, best=空绑定默认档案(非精确) → 不切换。"""
        campus = _mk("立达校园网", ssid="LIDA-UNIVERSITY", preset="lida-campus")
        legacy = _mk("陆冠霖的热点")
        cfg = {"profiles": [campus, legacy], "active_profile": "立达校园网",
               "history_enabled": False}
        _daemon, logs = self._run_daemon(
            cfg, legacy, "检测到校园网认证可用，切到档案「陆冠霖的热点」")
        self.assertEqual(cfg["active_profile"], "立达校园网")
        self.assertFalse(any("自动切换到档案" in ln for ln in logs))

    def test_precise_match_still_switches(self):
        """best 是 SSID/网关精确匹配(用户明确接入该网络) → 仍允许自动切换。"""
        any_net = config.default_profile("任意网络")
        any_net.update({k: None for k in ("username", "password")})
        campus = _mk("立达校园网", ssid="LIDA-UNIVERSITY", preset="lida-campus")
        cfg = {"profiles": [any_net, campus], "active_profile": "任意网络",
               "history_enabled": False}
        # 用户在非校园网选了「任意网络」→ best 是立达(SSID精确)应允许切
        _daemon, logs = self._run_daemon(cfg, campus, "SSID 精确匹配「LIDA-UNIVERSITY」")
        self.assertEqual(cfg["active_profile"], "立达校园网")
        self.assertTrue(any("自动切换到档案「立达校园网」" in ln for ln in logs))


if __name__ == "__main__":
    unittest.main()
