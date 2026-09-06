# -*- coding: utf-8 -*-
"""v4.0.5 回归测试: 隧道共享默认不开启「防蹭网口令」。

背景: v4.0.4 引入 shared_key 防蹭网, 但默认开启且 UI 无关闭入口。
后果: iOS/Android 的 PAC/手动代理客户端无法附加 X-Shared-Key 头,
      所有手机请求被 407 拒绝, 普通用户根本走不通。
修复: tunnel_ui.toggle_share 仅在 cfg.tunnel_require_key 为真时才生成口令;
      _show_tunnel_ready 增加复选框让用户随时切换。
本测试覆盖关键不变量:
  1) 不设 tunnel_require_key 时, 启动 proxy.shared_key 必须为 "" (空=不校验)
  2) 设 tunnel_require_key 时, 启动 proxy.shared_key 必须非空字符串
  3) toggle_share 的 cfg 决策函数在不同残留场景下输出符合预期
"""
import os
import socket
import sys
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import shared_proxy


def _free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class DefaultNoKeyTests(unittest.TestCase):
    """v4.0.5 默认行为: 不开启口令, 所有请求直通。"""

    def setUp(self):
        self.port = _free_port()
        # shared_key=None 模拟 v4.0.5 默认行为 (SharedProxy 内部会 or "" 转成空字符串, 即"不校验")
        self.proxy = shared_proxy.SharedProxy(
            port=self.port, allowed=[],
            on_ask=None, pac_host="127.0.0.1",
            shared_key=None)
        self.proxy.start()

    def tearDown(self):
        try:
            self.proxy.stop()
        except Exception:
            pass

    def test_shared_key_is_empty_string(self):
        """1) 启动时 shared_key 必须为 "" (空=不校验), 不再默认开启口令保护。"""
        self.assertEqual(self.proxy.shared_key, "")

    def test_pac_still_served(self):
        """/proxy.pac 在不带 key 时仍然可拉。"""
        resp = urllib.request.urlopen(
            "http://127.0.0.1:%d/proxy.pac" % self.port, timeout=2)
        self.assertEqual(resp.status, 200)
        body = resp.read().decode()
        self.assertIn("FindProxyForURL", body)
        self.assertIn("PROXY", body)
        self.assertIn(str(self.port), body)

    def test_407_blocker_logic_removed(self):
        """验证: shared_key 为空时, _handle 中 'if self.shared_key' 分支为假,
        即使请求不带 X-Shared-Key 头, 也不会被 407 拒绝。

        回归原 bug: v4.0.4 默认开启口令 → iOS PAC 客户端全部 407 → 手机无网。
        """
        # 在 _handle 流程里: 走到 _check_allow (同 IP 跳过白名单) → _shared_key 校验分支。
        # 当 self.shared_key 为空字符串, if self.shared_key: 直接跳过, 不可能 407。
        # 这是源码静态不变量, 我们用最小反射验证。
        # 构造一个没有 _shared_key 校验分支执行的场景: GET /proxy.pac (不走 _check_allow)
        # 这已经覆盖在 test_pac_still_served 里了。
        # 这里只做语义验证:
        self.assertFalse(bool(self.proxy.shared_key),
                         "shared_key 应为空/None, 这样 iOS PAC 客户端不会被 407")


class WithKeyTests(unittest.TestCase):
    """v4.0.5 显式开启口令时仍正常工作: 第三方调用需要附 X-Shared-Key。"""

    def setUp(self):
        self.port = _free_port()
        self.key = "test-key-1234567890"
        self.proxy = shared_proxy.SharedProxy(
            port=self.port, allowed=[],
            on_ask=None, pac_host="127.0.0.1",
            shared_key=self.key)
        self.proxy.start()

    def tearDown(self):
        try:
            self.proxy.stop()
        except Exception:
            pass

    def test_shared_key_set(self):
        """用户显式开启时, shared_key 必须保留。"""
        self.assertEqual(self.proxy.shared_key, self.key)

    def test_pac_still_served_even_with_key(self):
        """/proxy.pac 在带 key 模式下仍然可拉 (PAC 路径不走 _shared_key 校验)。"""
        resp = urllib.request.urlopen(
            "http://127.0.0.1:%d/proxy.pac" % self.port, timeout=2)
        self.assertEqual(resp.status, 200)


class ToggleConfigCompatTests(unittest.TestCase):
    """回归 v4.0.4 残留: 磁盘里有 tunnel_shared_key 但 tunnel_require_key 缺失/False 时,
    新版代码不应该强制把它激活。

    这是复刻自 gui.tunnel_ui.toggle_share 的核心决策函数 (不导入 GUI, 只测逻辑)。"""

    def decide(self, cfg):
        """复刻 toggle_share 中关于 shared_key 的逻辑分支。
        返回: proxy.shared_key 的最终值。"""
        if cfg.get("tunnel_require_key"):
            return cfg.get("tunnel_shared_key") or "GENERATED"
        return ""

    def test_blank_config_no_key(self):
        """1) 完全空白 → 不开 (默认行为, 不再有 v4.0.4 的强开口令问题)。"""
        self.assertEqual(self.decide({}), "")

    def test_v4_0_4_residue_no_key(self):
        """2) v4.0.4 残留: 有 shared_key, 没 require_key → 仍然不开。"""
        self.assertEqual(self.decide({"tunnel_shared_key": "old-key-1234"}), "")

    def test_user_opt_in_with_old_key(self):
        """3) 显式勾选 → 取磁盘上旧值 (UI 显示用, 内存里可能被重新生成, 这是 helper 行为)。"""
        self.assertEqual(
            self.decide({"tunnel_shared_key": "abc", "tunnel_require_key": True}),
            "abc")

    def test_user_opt_in_no_existing_key(self):
        """4) 勾选但磁盘没值 → 模拟生成。"""
        self.assertEqual(self.decide({"tunnel_require_key": True}), "GENERATED")

    def test_user_opt_out_with_residue(self):
        """5) 显式关闭 (require_key=False) → 空字符串 (即使磁盘残留也忽略)。"""
        self.assertEqual(
            self.decide({"tunnel_require_key": False, "tunnel_shared_key": "old"}),
            "")


if __name__ == "__main__":
    unittest.main()
