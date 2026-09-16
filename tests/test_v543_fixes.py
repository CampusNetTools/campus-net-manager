# -*- coding: utf-8 -*-
"""v5.4.3 缺陷修复的回归测试。

本轮修掉的问题（都不是"新功能", 全是行为不正确）:

  1. 下载测速没吃忙闲闸 —— 能和批量测速叠着跑, 结果互相覆盖；
  2. 下载测速的标题会撒谎 —— 列表里高亮的是 A, 但流量走的是当前出口 B,
     标题却写 A, 用户会把测得的带宽记到 A 头上；
  3. 探活失败(None)时把整行状态标红 —— 节点列表明明读到了, 却看起来像全挂了；
  4. 导出诊断报告时在工作线程里操作剪贴板 —— 失败被静默吞掉, 但提示语照样
     宣称"已复制到剪贴板"；
  5. 新手向导的"检测副路由器"在工作线程里直接改 Text 控件和按钮。

1~3 在 gui/clash_nodes_ui.py, 4 在 gui/daemon_ctl.py, 5 在 gui/wizard.py。
断言读源码而不是导入 —— 与 test_clash_nodes.py 的做法一致(无 tkinter 环境也能跑)。
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def read(rel):
    with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
        return fh.read()


def strip_docs(text):
    """去掉 docstring 与注释, 只留会执行的代码。

    注释里解释"为什么不能这么写"是应该存在的, 不能因此判失败。
    """
    out, in_doc = [], False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.count('"""') >= 2:
            continue
        if stripped.count('"""') == 1:
            in_doc = not in_doc
            continue
        if in_doc or stripped.startswith("#"):
            continue
        out.append(line)
    return "\n".join(out)


class SourceHelpers(unittest.TestCase):
    def body(self, rel, fn):
        """截出某个函数/方法的源码(带左括号, 避免前缀函数名误匹配)。"""
        raw = read(rel).split("def %s(" % fn)[1]
        raw = raw.split("\n    def ")[0]
        return strip_docs("\n    def " + raw)


class TestSpeedTestBusyGate(SourceHelpers):
    def test_speed_test_takes_busy_gate(self):
        """下载测速必须占忙闲闸, 否则会和批量测速叠跑。"""
        body = self.body("gui/clash_nodes_ui.py", "_clash_speed_test")
        self.assertIn("_clash_begin_busy", body)
        self.assertIn("_clash_end_busy", body)

    def test_busy_released_before_refresh(self):
        """必须先松闸再排队刷新。

        否则 _clash_refresh 会被"正在忙"挡掉, 头部状态行会永远卡在
        「正在下载测速…」——这正是"状态行不恢复"那类问题的成因。
        """
        body = self.body("gui/clash_nodes_ui.py", "_clash_speed_test")
        i_end = body.index("_clash_end_busy")
        i_refresh = body.index("_clash_refresh")
        self.assertLess(i_end, i_refresh, "松闸必须排在刷新之前")

    def test_fails_fast_when_busy(self):
        """闸被占住时要立刻返回, 不能继续把 worker 拉起来。"""
        body = self.body("gui/clash_nodes_ui.py", "_clash_speed_test")
        seg = body.split("_clash_begin_busy")[1]
        self.assertIn("return", seg.split("def worker")[0],
                      "闸被占用时必须提前 return")


class TestSpeedTestLabelHonesty(SourceHelpers):
    def test_reports_current_exit_not_selection(self):
        """标题必须报"当前出口" —— 下载测速走的是 mihomo 的当前选择, 与高亮行无关。"""
        body = self.body("gui/clash_nodes_ui.py", "_clash_speed_test")
        self.assertIn("当前出口", body)

    def test_warns_when_selection_differs(self):
        """高亮节点 ≠ 当前出口时必须显式提醒, 否则用户会把结果记错节点。"""
        body = self.body("gui/clash_nodes_ui.py", "_clash_speed_test")
        self.assertIn('node["name"] != current', body)
        self.assertIn("切换到选中节点", body)

    def test_result_log_names_the_measured_exit(self):
        body = self.body("gui/clash_nodes_ui.py", "_clash_speed_test")
        self.assertIn("出口 %s", body)


class TestProbeFailureRendering(SourceHelpers):
    def test_none_probe_is_spelled_out(self):
        """探活拿不到状态码时要写明"不可用", 不能只显示 HTTP None 或者干脆不写。"""
        body = self.body("gui/clash_nodes_ui.py", "_clash_render")
        self.assertIn("probe_code is None", body)
        self.assertIn("代理探活不可用", body)

    def test_none_probe_does_not_turn_header_red(self):
        """探活失败不该把整行标红: 节点列表和 mihomo 版本都是好的。"""
        body = self.body("gui/clash_nodes_ui.py", "_clash_render")
        self.assertNotIn("self._clash_set_head(head, probe_code == 204)", body)
        self.assertIn("None if probe_code is None", body)


class TestClipboardOnMainThread(SourceHelpers):
    def test_clipboard_not_touched_in_worker(self):
        """剪贴板是 tkinter 操作, 不能出现在工作线程函数体里。"""
        body = self.body("gui/daemon_ctl.py", "_do")
        # _do 里会定义 done() 并把它投递回主线程; 剪贴板只能出现在 done 里
        worker_part = body.split("def done(")[0]
        self.assertNotIn("clipboard_clear", worker_part)
        self.assertNotIn("clipboard_append", worker_part)

    def test_success_message_only_when_copied(self):
        """复制失败时不许再说"已复制到剪贴板"。"""
        body = self.body("gui/daemon_ctl.py", "_do")
        self.assertIn("copied", body)
        self.assertIn("剪贴板复制未成功", body)

    def test_uses_guarded_post(self):
        body = self.body("gui/daemon_ctl.py", "_do")
        self.assertIn("post(self,", body)


class TestWizardDetectDispatch(SourceHelpers):
    def test_detect_dispatches_ui_to_main_thread(self):
        """detect() 在工作线程里跑, 所以 set_body / 按钮 configure 必须投递回主线程。"""
        body = self.body("gui/wizard.py", "detect")
        self.assertIn("post(self, apply)", body)
        # 控件操作要在 apply() 里, 不能在 detect() 里直接做
        worker_part = body.split("def apply(")[0]
        self.assertNotIn("set_body(", worker_part)
        self.assertNotIn("btn_act2.configure", worker_part)

    def test_apply_contains_widget_updates(self):
        body = self.body("gui/wizard.py", "detect")
        apply_part = body.split("def apply(")[1]
        self.assertIn("set_body(", apply_part)
        self.assertIn("btn_act2.configure", apply_part)


class TestUiDispatchModule(unittest.TestCase):
    def test_post_is_importable_and_used_where_needed(self):
        src = read("gui/ui_dispatch.py")
        self.assertIn("def post(", src)
        for rel in ("gui/daemon_ctl.py", "gui/wizard.py"):
            self.assertIn("from gui.ui_dispatch import post", read(rel))

    def test_audit_script_present(self):
        src = read("scripts/thread_safety.py")
        self.assertIn("def scan(", src)
        self.assertIn("tk_call_reason", src)


if __name__ == "__main__":
    unittest.main()
