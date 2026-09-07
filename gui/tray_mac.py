# -*- coding: utf-8 -*-
"""macOS 菜单栏托盘 (NSStatusItem, 主线程安全)。

背景: pystray 在 macOS 上从后台线程运行 NSApplication, 新版系统(15+)会
在 NSUpdateCycleInitialize 处 SIGTRAP 崩溃(关闭窗口→最小化到托盘即崩)。
本模块改用 pyobjc 在 Tk 主线程创建 NSStatusItem, 菜单动作经主线程事件
循环派发(Tk mainloop 本身泵 NSApp runloop), 线程安全且无需额外权限。
"""
from AppKit import NSStatusBar, NSStatusItem, NSMenu, NSMenuItem  # noqa: F401
from Foundation import NSObject


class MacTray:
    """用法: tray = MacTray("🌐 校园网", on_show, on_quit); 退出前 tray.stop()。"""

    def __init__(self, title, on_show, on_quit):
        self._on_show = on_show
        self._on_quit = on_quit
        self._refs = []  # 持引用防 pyobjc 对象被 GC

        tray = self

        class _Handler(NSObject):
            def show_(self, sender):
                try:
                    tray._on_show()
                except Exception:
                    pass

            def quit_(self, sender):
                try:
                    tray._on_quit()
                except Exception:
                    pass

        self._handler = _Handler.alloc().init()
        self._refs.append(self._handler)

        self._bar = NSStatusBar.systemStatusBar()
        self._item = self._bar.statusItemWithLength_(96.0)
        self._item.setTitle_(title)

        menu = NSMenu.alloc().init()
        mi_show = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "打开主界面", "show:", "")
        mi_show.setTarget_(self._handler)
        menu.addItem_(mi_show)
        mi_quit = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "退出", "quit:", "")
        mi_quit.setTarget_(self._handler)
        menu.addItem_(mi_quit)
        menu.addItem_(NSMenuItem.separatorItem())
        self._item.setMenu_(menu)
        self._refs.append(menu)
        self._refs.append(self._item)

    def stop(self):
        """从菜单栏移除图标。必须在主线程调用(Tk 回调上下文)。"""
        try:
            self._bar.removeStatusItem_(self._item)
        except Exception:
            pass
        self._refs = []
