# -*- coding: utf-8 -*-
"""v5.0.7 回归: 功能窗口禁止 grab_set 模态劫持。

背景: 隧道共享就绪窗口曾 grab_set() 抢全局事件, 用户把它留在后台再去开
「路由器代理」等窗口时, 新窗口看得见却点不动(滚动/按钮全部失灵)。
功能窗口是并列工具窗, 一律不允许抢全局事件。
"""
import os
import unittest

GUI_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "gui")


class TestNoGrabInFeatureWindows(unittest.TestCase):
    def test_no_grab_set_anywhere_in_gui(self):
        """gui/ 下所有源码不得出现 grab_set。"""
        for fn in sorted(os.listdir(GUI_DIR)):
            if not fn.endswith(".py"):
                continue
            with open(os.path.join(GUI_DIR, fn), encoding="utf-8") as f:
                src = f.read()
            self.assertNotIn("grab_set", src,
                             f"{fn} 仍在使用 grab_set 模态劫持全局事件")


if __name__ == "__main__":
    unittest.main()
