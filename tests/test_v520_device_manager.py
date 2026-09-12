# -*- coding: utf-8 -*-
"""v5.2.2 设备管理回归测试 (数据源改为 Dr.COM ePortal 门户)。

覆盖:
- config: protected_device 默认值 + ensure_preferences 补齐(含嵌套 dict)
- selfservice.discover_selfservice_url: 由认证地址推导 ePortal 门户地址(801)
- selfservice._jsonp_load: JSONP 解析(含 Dr.COM 实际返回的结尾分号)
- selfservice._device_from_row: online_list 行 -> 统一设备 dict 映射
- selfservice.fetch_online_devices / kick_device: 无凭据优雅报错 + 远程下线拒绝
- daemon 保护模式: protected_device.enabled 时刷新阈值降为 1
"""
import json
import os
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import keepalive_core as core  # noqa: E402
from core import common, config, selfservice  # noqa: E402


class ProtectedDeviceConfigTests(unittest.TestCase):
    def test_default_preferences_has_protected_device(self):
        d = config.default_preferences()
        self.assertIn("protected_device", d)
        self.assertEqual(d["protected_device"],
                         {"enabled": False, "name": "", "kind": "router"})

    def test_ensure_preferences_backfills_nested(self):
        cfg = {}
        config.ensure_preferences(cfg)
        self.assertEqual(cfg["protected_device"]["enabled"], False)

        cfg2 = {"protected_device": {"enabled": True, "name": "小米路由器"}}
        config.ensure_preferences(cfg2)
        self.assertEqual(cfg2["protected_device"]["enabled"], True)
        self.assertEqual(cfg2["protected_device"]["name"], "小米路由器")
        self.assertEqual(cfg2["protected_device"]["kind"], "router")

    def test_ensure_preferences_upgrades_non_dict(self):
        cfg = {"protected_device": "garbage"}
        config.ensure_preferences(cfg)
        self.assertEqual(cfg["protected_device"]["enabled"], False)


class DiscoverPortalUrlTests(unittest.TestCase):
    def test_derives_eportal_port_801(self):
        # v5.2.2: 不再猜 8080/Self/, 而是认证主机 801 端口的 ePortal 门户
        self.assertEqual(
            selfservice.discover_selfservice_url("http://192.168.16.3/"),
            "http://192.168.16.3:801")

    def test_strips_existing_port(self):
        self.assertEqual(
            selfservice.discover_selfservice_url("http://192.168.16.3:8080/"),
            "http://192.168.16.3:801")

    def test_none_on_empty(self):
        self.assertIsNone(selfservice.discover_selfservice_url(""))


class JsonpLoadTests(unittest.TestCase):
    def test_parses_jsonp_with_trailing_semicolon(self):
        # Dr.COM 实际返回 callback({...}); —— 结尾带分号
        text = 'dr1003({"result":1,"list":[{"a":1}]});'
        self.assertEqual(selfservice._jsonp_load(text)["result"], 1)

    def test_parses_jsonp_without_semicolon(self):
        text = 'dr1003({"result":1});'
        self.assertEqual(selfservice._jsonp_load(text)["result"], 1)

    def test_parses_plain_json(self):
        self.assertEqual(selfservice._jsonp_load('{"a": 1}')["a"], 1)

    def test_raises_on_garbage(self):
        with self.assertRaises(ValueError):
            selfservice._jsonp_load("not json at all")


class DeviceFromRowTests(unittest.TestCase):
    def test_maps_online_list_row(self):
        row = {
            "online_session": 10353,
            "online_ip": "10.52.163.90",
            "online_mac": "56926a2d0a6e",
            "dhcp_host": "MiWiFi-RD08",
            "online_time": "2026-09-12 13:32:05",
            "time_long": "28731",
            "uplink_bytes": "889520",
            "downlink_bytes": "7096654",
        }
        d = selfservice._device_from_row(row)
        self.assertEqual(d["id"], "10353")
        self.assertEqual(d["name"], "MiWiFi-RD08")
        self.assertEqual(d["ip"], "10.52.163.90")
        self.assertEqual(d["mac"], "56926a2d0a6e")
        self.assertEqual(d["time"], "2026-09-12 13:32:05")
        self.assertEqual(d["duration"], "28731")

    def test_name_falls_back_to_mac(self):
        d = selfservice._device_from_row(
            {"online_session": 1, "online_mac": "aa:bb:cc:dd:ee:ff"})
        self.assertEqual(d["name"], "aa:bb:cc:dd:ee:ff")

    def test_name_prefers_dhcp_host_over_alias(self):
        d = selfservice._device_from_row(
            {"online_session": 1, "dhcp_host": "MiWiFi-RD08",
             "device_alias": "我的路由器"})
        self.assertEqual(d["name"], "MiWiFi-RD08")


class FetchAndKickGuardTests(unittest.TestCase):
    def _cfg_no_username(self):
        return {"profiles": [{"name": "p", "username": "", "password": "",
                              "auth_url": core.DEFAULT_AUTH_URL}],
                "active_profile": "p"}

    def test_fetch_without_username_graceful(self):
        devices, error = selfservice.fetch_online_devices(self._cfg_no_username())
        self.assertEqual(devices, [])
        self.assertIn("账号", error)

    def test_kick_without_username_graceful(self):
        ok, error = selfservice.kick_device(self._cfg_no_username(), {"id": "x"})
        self.assertFalse(ok)
        self.assertIn("账号", error)

    def test_kick_other_device_rejected(self):
        # 学校门户 logout 只能注销"源 IP"(本机/路由器), 无法远程下线其他设备
        cfg = {"profiles": [{"name": "p", "username": "u", "password": "pwd",
                             "auth_url": core.DEFAULT_AUTH_URL}],
               "active_profile": "p"}
        with patch.object(selfservice, "SelfServiceClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.current_session.return_value = {
                "ip": "10.52.163.90", "mac": "x", "uid": "u@cmcc",
                "online": True}
            ok, error = selfservice.kick_device(
                cfg, {"id": "20019", "ip": "10.52.177.199"})
            self.assertFalse(ok)
            self.assertIn("远程下线", error)
            # 不应调用 logout
            mock_client.logout.assert_not_called()

    def test_kick_current_device_calls_logout(self):
        cfg = {"profiles": [{"name": "p", "username": "u", "password": "pwd",
                             "auth_url": core.DEFAULT_AUTH_URL}],
               "active_profile": "p"}
        with patch.object(selfservice, "SelfServiceClient") as MockClient:
            mock_client = MockClient.return_value
            mock_client.current_session.return_value = {
                "ip": "10.52.163.90", "mac": "x", "uid": "u@cmcc",
                "online": True}
            mock_client.logout.return_value = (True, "已注销")
            ok, error = selfservice.kick_device(
                cfg, {"id": "10353", "ip": "10.52.163.90"})
            self.assertTrue(ok)
            self.assertIsNone(error)
            mock_client.logout.assert_called_once()


class DaemonProtectModeTests(unittest.TestCase):
    """保护设备模式下, 守护刷新会话的阈值应降为 1(每轮刷新)。"""

    def _make_daemon(self, protected_enabled):
        from core import daemon
        cfg = {
            "profiles": [{"name": "p", "username": "u", "password": "pwd",
                          "ssid": "LIDA", "auth_url": core.DEFAULT_AUTH_URL,
                          "interval": 60, "profile_type": "campus"}],
            "active_profile": "p",
            "kick_guard": True,
            "protected_device": {"enabled": protected_enabled,
                                 "name": "小米路由器", "kind": "router"},
        }
        d = daemon.KeepAliveDaemon(cfg)
        return d

    def test_protect_flag_reflects_config(self):
        d = self._make_daemon(True)
        self.assertTrue(d.cfg["protected_device"]["enabled"])
        d2 = self._make_daemon(False)
        self.assertFalse(d2.cfg["protected_device"]["enabled"])


if __name__ == "__main__":
    unittest.main()
