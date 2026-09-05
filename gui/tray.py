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


    def _hide_to_tray(self):
        self.withdraw()
        if HAS_TRAY and not getattr(self, "_tray", None):
            menu = pystray.Menu(
                pystray.MenuItem("打开主界面", self._show_from_tray),
                pystray.MenuItem("退出", self._quit_from_tray))
            self._tray = pystray.Icon("CampusNetManager", self._make_tray_icon(),
                                      "校园网连接管家", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()


    def _show_from_tray(self):
        if getattr(self, "_tray", None):
            self._tray.stop()
            self._tray = None
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))


    def _quit_from_tray(self):
        if getattr(self, "_tray", None):
            self._tray.stop()
            self._tray = None
        self.stop_daemon()
        self.destroy()


    def on_close(self):
        if self.daemon and self.daemon.is_alive():
            if HAS_TRAY:
                self._hide_to_tray()
                self._log("已最小化到托盘，守护继续运行（点托盘图标可恢复）")
                return
            if not messagebox.askyesno("停止守护?", "守护正在运行。\n关闭窗口将停止连接管家，确定关闭吗？"):
                return
            self.stop_daemon()
        self.destroy()


