# -*- coding: utf-8 -*-
"""工作线程 → 主线程的 UI 更新入口（v5.4.3）。

tkinter 不是线程安全的: 只有创建解释器的那个线程(主线程)才能安全地碰控件。
本机实测(Tk 8.6 / Python 3.11):

  | 场景                          | 工作线程里调 widget.after / widget.configure |
  |-------------------------------|---------------------------------------------|
  | mainloop 正在跑(窗口开着)      | 不抛异常(200 次全过) —— 但这是"碰巧能用", |
  |                               | 不构成线程安全保证                        |
  | 没有 mainloop(初始化阶段/测试) | RuntimeError: main thread is not in main loop |
  | 窗口已 destroy() 之后          | RuntimeError: main thread is not in main loop |

也就是说它**有时能用、有时直接抛**, 取决于主线程当时在不在事件循环里。一旦撞上,
轻则这次界面更新被静默丢掉, 重则异常顺着工作线程冒出去, 把业务逻辑也带崩
(v5.4.2 的 Clash 节点窗口就栽在这里)。

所以: 工作线程里不要直接调 ``widget.after`` / 碰控件, 一律用 ``post()``。
它只做一次受保护的投递, 绝不抛异常; 窗口已关或没有事件循环时, 这次更新就放弃 ——
反正那种状态下也没有界面可以更新。

⚠️ 给写测试的人: 用 ``root.update()`` 手动泵事件(不跑 mainloop)时, ``post()`` 的投递
**会被按设计丢弃**, 断言就会莫名失败。那不是产品缺陷, 是测试环境不真实 —— 请用
``root.after(...)`` + ``root.mainloop()`` + 到点 ``root.quit()`` 的方式驱动。
走"队列 + 主线程泵"的窗口(如 ``gui/clash_nodes_ui.py``)不受此限, 因为泵是由主线程
自己排的, ``update()`` 也能跑到。
"""
import tkinter as tk


def post(widget, fn, *args):
    """把 ``fn(*args)`` 排到主线程执行; 失败时静默丢弃, 绝不抛异常。

    ``widget`` 可以是任意 tkinter 控件(通常传 ``self``), 只要有 ``after``。
    """
    try:
        widget.after(0, lambda: fn(*args))
    except (tk.TclError, RuntimeError, AttributeError, OSError):
        pass
