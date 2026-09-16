# -*- coding: utf-8 -*-
"""v5.4.3 线程安全回归测试。

两件事:
  1. **检查器自检**（关键）: `scripts/thread_safety.py` 是纯静态分析, 它自己出错时
     最危险的表现是"静默报 0 处"——开发过程中就连续踩过两次(漏了嵌套 worker 函数、
     漏了 `Thread(target=self.method)` 这种类方法入口)。所以先用夹具断言它**必须
     抓得到**已知违规, 并且**不能误报**已知合法写法。
  2. **全仓库扫描**: gui/、根目录、mobile 下不允许存在"工作线程里真在碰 tkinter"的地方。
     这类问题在本机 Tk 上只在无 mainloop 或窗口销毁后炸, 生产上表现为界面更新静默丢失,
     很难靠手测发现, 只能靠静态卡口兜住。
"""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from gui.ui_dispatch import post                      # noqa: E402
from scripts.thread_safety import scan, scan_source   # noqa: E402


class TestAnalyzerSelfCheck(unittest.TestCase):
    """夹具自检: 保证检查器既抓得到、也不误报。"""

    def test_detects_nested_worker_touching_widget(self):
        """嵌套函数形式的 worker 直接碰控件 —— 必须抓到。"""
        src = (
            "import threading\n"
            "class App:\n"
            "    def act(self):\n"
            "        def worker():\n"
            "            self.lbl.configure(text='x')\n"
            "        threading.Thread(target=worker, daemon=True).start()\n"
        )
        rows = scan_source(src)
        self.assertTrue(rows, "嵌套 worker 里的控件调用没被检出")
        self.assertIn("configure", rows[0][4])

    def test_detects_class_method_worker(self):
        """Thread(target=self.method) 这种类方法入口 —— 必须抓到。

        检查器第一版只按词法作用域解析, 漏掉了类方法入口(shared_proxy 就属于这种),
        等于漏检一整类写法, 所以专门钉一条。
        """
        src = (
            "import threading\n"
            "class App:\n"
            "    def start(self):\n"
            "        threading.Thread(target=self._loop, daemon=True).start()\n"
            "    def _loop(self):\n"
            "        self.tree.delete('1', 'end')\n"
        )
        rows = scan_source(src)
        self.assertTrue(rows, "类方法入口的 worker 没被检出")

    def test_detects_widget_touch_inside_pool_lambda(self):
        """传给线程池的 lambda 是在池线程里跑的 —— 必须下钻。"""
        src = (
            "import threading\n"
            "from concurrent.futures import ThreadPoolExecutor\n"
            "class App:\n"
            "    def go(self):\n"
            "        def worker():\n"
            "            with ThreadPoolExecutor(max_workers=2) as pool:\n"
            "                pool.map(lambda n: self.lbl.configure(text=str(n)), [1])\n"
            "        threading.Thread(target=worker, daemon=True).start()\n"
        )
        self.assertTrue(scan_source(src), "线程池 lambda 里的控件调用没被检出")

    def test_ignores_callback_deferred_to_main_thread(self):
        """回调交给主线程队列的写法是**正确**的 —— 绝不能误报。"""
        src = (
            "import threading\n"
            "class App:\n"
            "    def act(self):\n"
            "        def worker():\n"
            "            self._ui(lambda: self.lbl.configure(text='x'))\n"
            "        threading.Thread(target=worker, daemon=True).start()\n"
            "    def _ui(self, fn):\n"
            "        pass\n"
        )
        self.assertEqual(scan_source(src), [], "被延迟到主线程的回调被误报了")

    def test_ignores_attribute_call_name_collision(self):
        """socket.bind 不是控件 bind; 属性调用不能解析成同名兄弟函数。"""
        src = (
            "import threading, socket\n"
            "class Srv:\n"
            "    def start(self):\n"
            "        threading.Thread(target=self._loop, daemon=True).start()\n"
            "    def _loop(self):\n"
            "        s = socket.socket()\n"
            "        s.bind(('0.0.0.0', 1))\n"
        )
        self.assertEqual(scan_source(src), [], "socket.bind 被误判成控件调用")

    def test_ignores_post_helper(self):
        """gui.ui_dispatch.post 是受保护的投递入口 —— 不能误报。"""
        src = (
            "import threading\n"
            "from gui.ui_dispatch import post\n"
            "class App:\n"
            "    def act(self):\n"
            "        def worker():\n"
            "            post(self, lambda: self.lbl.configure(text='x'))\n"
            "        threading.Thread(target=worker, daemon=True).start()\n"
        )
        self.assertEqual(scan_source(src), [], "post() 投递被误报了")


class TestRepoIsClean(unittest.TestCase):
    def test_no_worker_thread_touches_tkinter(self):
        rows = scan(ROOT)
        detail = "\n".join(
            "  %s:%d  %s() 在 worker %s(第 %d 行启动) 里调用 %s"
            % (r[0], r[3], r[4], r[2], r[1], r[5]) for r in rows)
        self.assertEqual(rows, [], "工作线程里还在碰 tkinter:\n" + detail)


class FakeWidget:
    def __init__(self, exc=None):
        self.calls = []
        self.exc = exc

    def after(self, ms, fn):
        if self.exc:
            raise self.exc
        self.calls.append((ms, fn))
        return "id1"


class TestPostHelper(unittest.TestCase):
    def test_schedules_on_main_thread(self):
        w = FakeWidget()
        ran = []
        post(w, lambda: ran.append(1))
        self.assertEqual(len(w.calls), 1)
        self.assertEqual(w.calls[0][0], 0)
        w.calls[0][1]()
        self.assertEqual(ran, [1])

    def test_passes_args(self):
        w = FakeWidget()
        got = []
        post(w, got.append, "node-x")
        w.calls[0][1]()
        self.assertEqual(got, ["node-x"])

    def test_never_raises_when_window_gone(self):
        """窗口已销毁 / 没有 mainloop 时必须静默丢弃, 不能把异常冒给工作线程。"""
        for exc in (RuntimeError("main thread is not in main loop"), OSError("bad fd")):
            with self.subTest(exc=type(exc).__name__):
                try:
                    post(FakeWidget(exc=exc), lambda: None)
                except Exception as err:                    # pragma: no cover
                    self.fail("post() 不该抛异常, 却抛了 %r" % (err,))

    def test_never_raises_on_widget_without_after(self):
        class Broken:
            pass

        try:
            post(Broken(), lambda: None)
        except Exception as err:                            # pragma: no cover
            self.fail("缺少 after() 时 post() 不该抛异常, 却抛了 %r" % (err,))


if __name__ == "__main__":
    unittest.main()
