# -*- coding: utf-8 -*-
"""系统托盘 Mixin (自 app_gui.py 拆分)"""
import os  # noqa: F401
import queue  # noqa: F401
import threading  # noqa: F401
import webbrowser  # noqa: F401
import tkinter as tk  # noqa: F401
from tkinter import ttk, messagebox, filedialog  # noqa: F401

import keepalive_core as core  # noqa: F401
import shared_proxy  # noqa: F401
from PIL import Image, ImageDraw, ImageTk  # noqa: F401

from gui.theme import *  # noqa: F401,F403

try:
    import pystray  # noqa: F401
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

try:
    import qrcode  # noqa: F401
    HAS_QR = True
except Exception:
    HAS_QR = False


class TrayMixin:
    def _make_tray_icon(self):
        img = Image.new("RGB", (64, 64), "#1e1e2e")
        d = ImageDraw.Draw(img)
        d.ellipse([6, 6, 58, 58], fill="#4cc38a")
        d.text((17, 18), "网", fill="#ffffff")
        return img

    def _make_tray(self):
        """创建托盘。macOS 用 NSStatusItem(pyobjc, 主线程安全)——
        pystray 在 macOS 新版上后台线程跑 NSApplication 会 SIGTRAP
        (NSUpdateCycleInitialize, v5.0.3 及之前每次最小化到托盘都崩)。
        返回 True 表示托盘可用。"""
        if core.IS_MACOS:
            try:
                from gui.tray_mac import MacTray
                self._tray = MacTray("🌐 校园网管家",
                                     self._show_from_tray, self._quit_from_tray)
                return True
            except Exception as e:
                try:
                    self._log("菜单栏托盘创建失败: %r" % e)
                except Exception:
                    pass
                return False
        if HAS_TRAY:
            menu = pystray.Menu(
                pystray.MenuItem("打开主界面", self._show_from_tray),
                pystray.MenuItem("退出", self._quit_from_tray))
            self._tray = pystray.Icon("CampusNetManager", self._make_tray_icon(),
                                      "校园网连接管家", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
            return True
        return False

    def _hide_to_tray(self):
        self.withdraw()
        if not getattr(self, "_tray", None):
            if not self._make_tray():
                # 托盘不可用: 不能让窗口凭空消失, 恢复显示
                self.deiconify()
                try:
                    self._log("托盘不可用, 窗口保持显示")
                except Exception:
                    pass

    def _show_from_tray(self):
        if getattr(self, "_tray", None):
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))

    def _quit_from_tray(self):
        if getattr(self, "_tray", None):
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        self.stop_daemon()
        console = getattr(self, "_console", None)
        if console and getattr(console, "running", False):
            try:
                console.stop()
            except Exception:
                pass
        self.destroy()
        # macOS: Tk 销毁后 AppKit/线程残留偶发 SIGTRAP 假崩溃;
        # 清理已全部完成(守护/代理/控制台/配置), 硬退出保平安。
        if core.IS_MACOS:
            os._exit(0)

    def on_close(self):
        if self.daemon and self.daemon.is_alive():
            if self._make_tray() or getattr(self, "_tray", None):
                self.withdraw()
                self._log("已最小化到菜单栏，守护继续运行（点菜单栏 🌐 图标可恢复）")
                return
            if not messagebox.askyesno("停止守护?", "守护正在运行。\n关闭窗口将停止连接管家，确定关闭吗？"):
                return
            self.stop_daemon()
        console = getattr(self, "_console", None)
        if console and console.running:
            console.stop()
        self.destroy()
        # macOS: 同 _quit_from_tray, 避免退出阶段 AppKit 假崩溃弹窗
        if core.IS_MACOS:
            os._exit(0)


