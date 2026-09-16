# -*- coding: utf-8 -*-
"""v5.4.4 路由器工作台页面回归测试。

为什么需要它
------------
``router_assets/console-index.html`` 曾经**完全不在仓库里**——只存在于路由器上。
后果是后端 ``action.sh`` 陆续新增的 ``enable_transparent`` / ``disable_transparent`` /
``rotate_node`` 三个动作, 在浏览器工作台上一直没有按钮, 而没有任何机制能发现这件事。

这个测试做两件事:
  1. **检查器自检**(关键): ``scripts/console_page_lint.py`` 是静态检查, 它最危险的
     失败模式是"静默报全过"。所以先用夹具断言它**必须抓得到**三类已知问题——
     页面调了后端没有的动作、后端有动作页面没入口、标签不配对。
  2. **真实页面卡口**: 仓库里的页面与 action.sh 必须双向一致, 且三个新动作的按钮
     必须存在(防止以后有人改页面时把入口弄丢)。
"""
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from scripts.console_page_lint import DEFAULT_ACTION, DEFAULT_PAGE, lint  # noqa: E402

# 一个最小的"动作名"取用: 复用真实 action.sh, 因为 case 分支解析依赖它的缩进
ACTION_STUB = """#!/bin/sh
case "$OP" in
  restart_proxy) echo a;;
  rotate_node) echo b;;
  enable_transparent) echo c;;
  *) echo d;;
esac
"""


def _tmp(html, action=ACTION_STUB):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "page.html")
    a = os.path.join(d, "action.sh")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(html)
    with open(a, "w", encoding="utf-8") as fh:
        fh.write(action)
    return d, p, a


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _fails(rows, keyword):
    return [r for r in rows if not r[0] and keyword in r[1]]


class TestLintSelfCheck(unittest.TestCase):
    """夹具自检: 检查器必须抓得到已知问题, 否则形同虚设。"""

    def test_detects_page_action_missing_on_backend(self):
        html = ("<html><body><pre id='logbox'></pre>"
                "<button onclick=\"act('nuke_everything')\">x</button>"
                "<script>const OPNAME={};</script></body></html>")
        d, p, a = _tmp(html)
        try:
            self.assertTrue(_fails(lint(p, a), "都能被后端处理"),
                            "页面调用了后端不存在的动作却没被检出")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_detects_backend_action_without_page_entry(self):
        html = ("<html><body><pre id='logbox'></pre>"
                "<button onclick=\"act('restart_proxy')\">x</button>"
                "<script>const OPNAME={restart_proxy:'重启'};</script></body></html>")
        d, p, a = _tmp(html)
        try:
            rows = _fails(lint(p, a), "都在页面上有入口")
            self.assertTrue(rows, "后端有 enable_transparent/rotate_node 但页面没入口, 未检出")
            self.assertIn("enable_transparent", rows[0][2])
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_detects_unbalanced_tags(self):
        html = "<html><body><div><pre id='logbox'></pre></body></html>"
        d, p, a = _tmp(html)
        try:
            self.assertTrue(_fails(lint(p, a), "标签配对"), "未闭合的 <div> 没被检出")
        finally:
            shutil.rmtree(d, ignore_errors=True)

    def test_detects_missing_element_id(self):
        html = ("<html><body><button onclick=\"act('restart_proxy')\">x</button>"
                "<script>const OPNAME={restart_proxy:'重启'};"
                "$('nope').textContent=1;</script></body></html>")
        d, p, a = _tmp(html)
        try:
            self.assertTrue(_fails(lint(p, a), "元素 id"), "引用不存在的 id 没被检出")
        finally:
            shutil.rmtree(d, ignore_errors=True)


class TestRealConsolePage(unittest.TestCase):
    """真实页面与后端的一致性卡口。"""

    @classmethod
    def setUpClass(cls):
        cls.rows = lint(DEFAULT_PAGE, DEFAULT_ACTION)

    def test_lint_all_pass(self):
        bad = [r for r in self.rows if not r[0]]
        self.assertFalse(bad, "路由器工作台页面检查未通过:\n" + "\n".join(
            "  %s -- %s" % (r[1], r[2]) for r in bad))

    def test_page_covers_every_backend_action(self):
        names = dict((r[1], r) for r in self.rows)
        self.assertIn("后端动作都在页面上有入口", names)
        self.assertTrue(names["后端动作都在页面上有入口"][0],
                        names["后端动作都在页面上有入口"][2])

    def test_three_v544_buttons_present(self):
        html = _read(DEFAULT_PAGE)
        for op, label in (("enable_transparent", "当前设备试用120秒"),
                          ("disable_transparent", "关闭透明接管"),
                          ("rotate_node", "换一个可用节点")):
            self.assertIn("act('" + op + "'", html, "缺少 %s 的按钮" % op)
            self.assertIn(label, html, "缺少按钮文案「%s」" % label)

    def test_no_internal_op_name_leaks_into_confirm(self):
        """确认框要显示中文, 不能露出 enable_transparent 这类内部名。"""
        html = _read(DEFAULT_PAGE)
        self.assertIn("OPNAME", html)
        self.assertNotIn("'确定要执行「'+op+'」", html)

    def test_shows_transparent_state_and_rotation_log(self):
        html = _read(DEFAULT_PAGE)
        self.assertIn("proxy.transparent", html, "未显示透明接管状态")
        self.assertIn("proxy.rotate", html, "未显示节点轮换日志")

    def test_action_file_has_expected_branches(self):
        sh = _read(DEFAULT_ACTION)
        for op in ("enable_transparent", "disable_transparent", "rotate_node",
                   "restart_router", "switch_relay"):
            self.assertIn(op + ")", sh, "action.sh 缺少分支 %s" % op)


if __name__ == "__main__":
    unittest.main()
