# -*- coding: utf-8 -*-
"""网络控制台 UI Mixin: 启停 WebConsole, 展示局域网地址/口令/二维码。"""
import tkinter as tk
from tkinter import ttk

import keepalive_core as core
import shared_proxy
import web_console
from PIL import ImageTk

from gui.theme import *  # noqa: F401,F403

try:
    import qrcode
    HAS_QR = True
except Exception:
    HAS_QR = False

CONSOLE_PORT = 8081


class ConsoleUiMixin:
    def _console_key(self):
        if not self.cfg.get("console_key"):
            self.cfg["console_key"] = core.gen_tunnel_key()
            try:
                core.save_config(self.cfg)
            except Exception:
                pass
        return self.cfg["console_key"]

    def _console_state(self):
        """给 WebConsole 的状态快照。"""
        daemon = getattr(self, "daemon", None)
        running = bool(daemon and daemon.is_alive())
        mode, ssid, gw = "", "", ""
        try:
            mode, ssid = core.get_connection_mode()
            gw = core.get_gateway()
        except Exception:
            pass
        profile = self._current_profile()
        proxy = getattr(self, "proxy", None)
        import platform
        return {
            "version": core.APP_VERSION,
            "platform": "macOS" if core.IS_MACOS else "Windows",
            "hostname": platform.node(),
            "lan_ips": shared_proxy.get_lan_ips(),
            "daemon_running": running,
            "authed": getattr(self, "_last_authed", False),
            "internet": getattr(self, "_last_internet", False),
            "in_campus": getattr(daemon, "_in_campus", None) if running else None,
            "profile": profile.get("name") if profile else None,
            "mode": mode or "—", "ssid": ssid or "", "gateway": gw or "",
            "last_check": getattr(daemon, "last_check", "") if running else "",
            "proxy_running": bool(proxy and proxy.running),
        }

    def _console_action(self, name):
        if name == "toggle_daemon":
            self.after(0, self.toggle_daemon)
            return "已切换守护状态"
        return "未知操作"

    def toggle_console(self):
        console = getattr(self, "_console", None)
        if console and console.running:
            console.stop()
            self._console = None
            self.btn_console.configure(text="网络控制台")
            self._log("Web 控制台已停止")
            return
        key = self._console_key()
        self._console = web_console.WebConsole(
            state_fn=self._console_state, key=key, port=CONSOLE_PORT,
            proxy=getattr(self, "proxy", None),
            action_fn=self._console_action)
        try:
            self._console.start()
        except OSError as e:
            self._console = None
            self._log("Web 控制台启动失败(端口 %d 被占用?): %s" % (CONSOLE_PORT, e))
            return
        self.btn_console.configure(text="控制台·运行中")
        self._show_console_window(key)

    def _show_console_window(self, key):
        ips = shared_proxy.get_lan_ips()
        host = ips[0] if ips else "127.0.0.1"
        url = "http://%s:%d/?key=%s" % (host, CONSOLE_PORT, key)

        win = tk.Toplevel(self)
        win.title("网络控制台")
        win.configure(bg=BG)
        win.transient(self)

        tk.Label(win, text="局域网设备（手机/电脑）浏览器打开以下地址：",
                 bg=BG, fg=FG, font=FONT).pack(anchor="w", padx=16, pady=(16, 6))
        url_lbl = tk.Label(win, text=url, bg=CARD, fg=ACCENT, font=FONT_S,
                           padx=10, pady=8, cursor="hand2")
        url_lbl.pack(fill="x", padx=16)
        url_lbl.bind("<Button-1>", lambda _e: self._copy_text(url))
        tk.Label(win, text="点击地址复制 · 口令已包含在链接中", bg=BG, fg=MUTED,
                 font=FONT_S).pack(anchor="w", padx=16, pady=(4, 8))

        if HAS_QR:
            img = qrcode.make(url)
            img = img.resize((200, 200))
            photo = ImageTk.PhotoImage(img)
            qr_lbl = tk.Label(win, image=photo, bg=BG)
            qr_lbl.image = photo
            qr_lbl.pack(pady=6)
            tk.Label(win, text="手机扫码直达控制台", bg=BG, fg=MUTED, font=FONT_S).pack()

        tk.Label(win, text="访问口令：%s（同局域网无口令无法访问）" % key,
                 bg=BG, fg=MUTED, font=FONT_S).pack(pady=(8, 4))
        btns = tk.Frame(win, bg=BG)
        btns.pack(pady=(4, 16))
        tk.Button(btns, text="复制地址", command=lambda: self._copy_text(url),
                  bg=ACCENT, fg="white", relief="flat", font=FONT).pack(side="left", padx=6)
        tk.Button(btns, text="停止控制台", command=lambda: (win.destroy(), self.toggle_console()),
                  bg=CARD2, fg=FG, relief="flat", font=FONT).pack(side="left", padx=6)
