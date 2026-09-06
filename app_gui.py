# -*- coding: utf-8 -*-
"""
校园网连接管家 - 桌面端
功能: 多档案配置(按 WiFi 自动匹配) / 环境识别(非校园网自动休眠) / 运行状态 / 实时日志
用法: python app_gui.py
"""
import os
import queue
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox, filedialog

import keepalive_core as core
import shared_proxy
from PIL import Image, ImageDraw, ImageTk

try:
    import pystray
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

try:
    import qrcode
    HAS_QR = True
except Exception:
    HAS_QR = False

from gui.theme import *  # noqa: F401,F403
from gui.profile_form import ProfileFormMixin  # noqa: F401
from gui.router_tools import RouterToolsMixin  # noqa: F401
from gui.router_proxy import RouterProxyMixin  # noqa: F401
from gui.speed_window import SpeedWindowMixin  # noqa: F401
from gui.tunnel_ui import TunnelUiMixin  # noqa: F401
from gui.preferences import PreferencesMixin  # noqa: F401
from gui.tray import TrayMixin  # noqa: F401
from gui.daemon_ctl import DaemonCtlMixin  # noqa: F401
from gui.wizard import WizardMixin  # noqa: F401
from gui.update_ui import UpdateUiMixin  # noqa: F401
from gui.console_ui import ConsoleUiMixin  # noqa: F401
from gui.feature_windows import FeatureWindowsMixin  # noqa: F401


class App(ProfileFormMixin, RouterToolsMixin, RouterProxyMixin, SpeedWindowMixin, TunnelUiMixin, PreferencesMixin, TrayMixin, DaemonCtlMixin, WizardMixin, UpdateUiMixin, ConsoleUiMixin, FeatureWindowsMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self._instance_lock_file = None
        if not self._acquire_instance_lock():
            self.destroy()
            raise SystemExit(0)
        self.title("校园网连接管家 v" + core.APP_VERSION)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1080, max(960, screen_w - 100))
        height = min(820, max(740, screen_h - 160))
        x = max(20, (screen_w - width) // 2)
        y = max(40, (screen_h - height) // 2)
        self.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self.minsize(min(960, screen_w - 40), min(740, screen_h - 100))
        self.configure(bg=BG)
        self._style()

        self.log_q = queue.Queue()
        self.daemon = None
        self.proxy = None
        self._allow_q = queue.Queue()
        self.cfg = core.load_config()
        self._init_fwin_map()

        self._build_ui()
        self._refresh_profile_list()
        self._load_form_from_current()

        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(200, self._poll_log)
        self.after(400, self._poll_allow)
        self.after(600, self._auto_start)
        self.after(800, self._refresh_env)
        self.after(3000, self._watchdog)


    def _acquire_instance_lock(self):
        """macOS 单实例保护，避免自启或重复双击产生多个窗口。"""
        if not core.IS_MACOS:
            return True
        try:
            import fcntl
            path = os.path.join(core.BASE_DIR, "app.instance.lock")
            handle = open(path, "a+")
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._instance_lock_file = handle
            return True
        except Exception:
            try:
                handle.close()
            except Exception:
                pass
            return False

    # ---------- 样式 ----------

    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD, bordercolor=BORDER, borderwidth=1, relief="solid")
        s.configure("Inner.TFrame", background=CARD)
        s.configure("Surface.TFrame", background=CARD2)
        s.configure("Surface.TLabel", background=CARD2, foreground=FG, font=FONT)
        s.configure("SurfaceMuted.TLabel", background=CARD2, foreground=MUTED, font=FONT_S)
        s.configure("SurfaceSection.TLabel", background=CARD2, foreground=FG, font=FONT_M)
        s.configure("Metric.TFrame", background=METRIC)
        s.configure("MetricTitle.TLabel", background=METRIC, foreground=MUTED,
                    font=("PingFang SC", 10))
        s.configure("MetricValue.TLabel", background=METRIC, foreground=FG,
                    font=("PingFang SC", 18, "bold"))
        s.configure("MetricSub.TLabel", background=METRIC, foreground="#7890ad",
                    font=("PingFang SC", 9))
        s.configure("DialogTitle.TLabel", background=CARD, foreground=FG,
                    font=("PingFang SC", 18, "bold"))
        s.configure("TLabel", background=BG, foreground=FG, font=FONT)
        s.configure("Card.TLabel", background=CARD, foreground=FG, font=FONT)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=FONT_S)
        s.configure("Title.TLabel", background=BG, foreground=FG, font=FONT_L)
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=FONT_S)
        s.configure("Section.TLabel", background=CARD, foreground=FG, font=FONT_M)
        s.configure("Field.TLabel", background=CARD, foreground=MUTED, font=FONT_S)
        s.configure("Status.TLabel", background=CARD, foreground=FG, font=FONT_S)
        s.configure("TEntry", fieldbackground=CARD2, foreground=FG, insertcolor=FG,
                    font=FONT, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    padding=(8, 5), relief="flat")
        s.configure("TCombobox", fieldbackground=CARD2, foreground=FG, background=CARD2,
                    arrowcolor=MUTED, font=FONT, bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, padding=(8, 5), relief="flat")
        s.map("TCombobox",
              fieldbackground=[("readonly", CARD2), ("disabled", CARD2)],
              background=[("readonly", CARD2), ("active", CARD2)],
              foreground=[("readonly", FG)],
              selectbackground=[("readonly", CARD2)],
              selectforeground=[("readonly", FG)],
              arrowcolor=[("readonly", MUTED)])
        s.configure("TCombobox.Listbox", background=CARD2, foreground=FG,
                    bordercolor=CARD, selectbackground=ACCENT, selectforeground="#ffffff")
        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=FONT,
                    borderwidth=0, padding=(12, 7), anchor="center")
        s.map("Accent.TButton", background=[("active", ACCENT_HOVER), ("pressed", "#355bc8")])
        s.configure("Green.TButton", background="#238b68", foreground="#ffffff", font=FONT,
                    borderwidth=0, padding=(12, 7), anchor="center")
        s.map("Green.TButton", background=[("active", "#1e7c5c"), ("pressed", "#196b50")])
        s.configure("Gray.TButton", background=CARD2, foreground=FG, font=FONT,
                    borderwidth=1, bordercolor=BORDER, padding=(12, 7), anchor="center")
        s.map("Gray.TButton", background=[("active", "#243653"), ("pressed", "#17243a")])
        s.configure("Quiet.TButton", background=CARD, foreground=MUTED, font=FONT_S,
                    borderwidth=0, padding=(6, 4), anchor="center")
        s.map("Quiet.TButton", background=[("active", CARD2)], foreground=[("active", FG)])
        s.configure("Feature.TButton", background=CARD2, foreground=FG,
                    font=("PingFang SC", 14), borderwidth=1, bordercolor=BORDER,
                    padding=(10, 11), anchor="w")
        s.map("Feature.TButton", background=[("active", "#243653"), ("pressed", "#17243a")],
              foreground=[("active", FG)])
        s.configure("Danger.TButton", background="#8f4051", foreground="#ffffff", font=FONT,
                    borderwidth=0, padding=(12, 7), anchor="center")
        s.map("Danger.TButton", background=[("active", "#a64a5d"), ("pressed", "#793645")])
        s.configure("AutoOn.TButton", background="#173c34", foreground="#8de5c3", font=FONT,
                    borderwidth=1, bordercolor="#276b58", padding=(12, 7), anchor="center")
        s.configure("AutoOff.TButton", background=CARD2, foreground=MUTED, font=FONT,
                    borderwidth=1, bordercolor=BORDER, padding=(12, 7), anchor="center")
        s.configure("Vertical.TScrollbar", background=CARD2, troughcolor=CARD,
                    bordercolor=CARD, arrowcolor=MUTED, relief="flat")
        s.configure("TRadiobutton", background=CARD, foreground=FG, font=FONT_S,
                    indicatorcolor=CARD2, focuscolor=CARD)
        s.map("TRadiobutton", background=[("active", CARD)], foreground=[("active", FG)],
              indicatorcolor=[("selected", ACCENT)])
        s.configure("TCheckbutton", background=CARD, foreground=FG, font=FONT_S,
                    indicatorcolor=CARD2, focuscolor=CARD)
        s.map("TCheckbutton", background=[("active", CARD)], foreground=[("active", FG)],
              indicatorcolor=[("selected", ACCENT)])
        unchecked = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
        unchecked_draw = ImageDraw.Draw(unchecked)
        unchecked_draw.rounded_rectangle((1, 1, 16, 16), radius=3, fill=CARD2,
                                         outline="#71839c", width=1)
        checked = Image.new("RGBA", (18, 18), (0, 0, 0, 0))
        checked_draw = ImageDraw.Draw(checked)
        checked_draw.rounded_rectangle((1, 1, 16, 16), radius=3, fill=GREEN, outline=GREEN)
        checked_draw.line((4, 9, 7, 12, 14, 5), fill="#ffffff", width=2, joint="curve")
        self._checkmark_images = (ImageTk.PhotoImage(unchecked), ImageTk.PhotoImage(checked))
        s.element_create("Campus.Checkmark.indicator", "image", self._checkmark_images[0],
                         ("selected", self._checkmark_images[1]), sticky="")
        s.layout("Checkmark.TCheckbutton", [
            ("Checkbutton.padding", {"sticky": "nswe", "children": [
                ("Campus.Checkmark.indicator", {"side": "left", "sticky": ""}),
                ("Checkbutton.focus", {"side": "left", "sticky": "w", "children": [
                    ("Checkbutton.label", {"sticky": "nswe"})]}),
            ]}),
        ])
        s.configure("Checkmark.TCheckbutton", background=CARD, foreground=FG, font=FONT_S,
                    padding=(0, 2))
        s.map("Checkmark.TCheckbutton", background=[("active", CARD)],
              foreground=[("active", FG), ("disabled", MUTED)])

    # ---------- UI ----------

    def _build_ui(self):
        # 顶栏: 品牌在左 + 版本在右。  内边距 24/18/24/12 让上方留点呼吸。
        top = ttk.Frame(self, padding=(24, 16, 24, 10))
        top.pack(fill="x")
        brand = ttk.Frame(top)
        brand.pack(side="left")
        ttk.Label(brand, text="校园网连接管家", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="自动识别网络 · 保持校园网稳定在线", style="Sub.TLabel").pack(
            anchor="w", pady=(4, 0))
        ttk.Label(top, text="v" + core.APP_VERSION, style="Sub.TLabel").pack(
            side="right", anchor="n", pady=(10, 0))

        # 状态条 (总览, 不归属任何功能窗口) —— 16/12 内边距, 卡片间间隔 12
        status = ttk.Frame(self, style="Card.TFrame", padding=(20, 14))
        status.pack(fill="x", padx=24, pady=(4, 12))
        for col in (1, 3, 5):
            status.columnconfigure(col, weight=1)

        self.dot_guard = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=("Arial", 12))
        self.dot_guard.grid(row=0, column=0, padx=(0, 10))
        self.lbl_guard = ttk.Label(status, text="守护：未运行", style="Status.TLabel")
        self.lbl_guard.grid(row=0, column=1, sticky="w")

        self.dot_net = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=("Arial", 12))
        self.dot_net.grid(row=0, column=2, padx=(20, 10))
        self.lbl_net = ttk.Label(status, text="网络：未知", style="Status.TLabel")
        self.lbl_net.grid(row=0, column=3, sticky="w")

        self.dot_env = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=("Arial", 12))
        self.dot_env.grid(row=0, column=4, padx=(20, 10))
        envbox = ttk.Frame(status, style="Inner.TFrame")
        envbox.grid(row=0, column=5, sticky="ew")
        self.lbl_env = ttk.Label(envbox, text="环境：检测中…", style="Status.TLabel")
        self.lbl_env.pack(anchor="w")
        self.lbl_last = ttk.Label(envbox, text="上次检测：—", style="Muted.TLabel")
        self.lbl_last.pack(anchor="w", pady=(2, 0))

        # 守护控制带 —— 16/14 内边距
        ctl = ttk.Frame(self, style="Card.TFrame", padding=(18, 14))
        ctl.pack(fill="x", padx=24, pady=(0, 14))
        ctl.columnconfigure(1, weight=1)
        self.btn_guard = ttk.Button(ctl, text="启动守护", style="Green.TButton",
                                    command=self.toggle_daemon)
        self.btn_guard.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 14))
        self.var_auto = tk.BooleanVar(value=core.autostart_enabled())
        self.btn_auto = ttk.Button(ctl, text="开机自启：关闭", style="AutoOff.TButton",
                                   command=self._toggle_autostart)
        self.btn_auto.grid(row=0, column=1, sticky="ew", padx=(0, 4), pady=(0, 4))
        ttk.Button(ctl, text="立即检测", style="Gray.TButton",
                   command=self.check_now).grid(row=1, column=1, sticky="ew", padx=(0, 4))
        self._update_auto_btn()
        ttk.Label(ctl, text="守护 = 自动检测并恢复校园网登录。掉线自动重登、防踢保活、唤醒即检。",
                  style="Muted.TLabel", wraplength=360, justify="right").grid(
            row=0, column=2, rowspan=2, sticky="e", padx=(14, 0))

        # 功能宫格: 4×3 (8 项) + 底部实时运行日志
        grid_host = ttk.Frame(self)
        grid_host.pack(fill="x", padx=24, pady=(0, 12))
        grid_host.columnconfigure(0, weight=1)
        grid_host.rowconfigure(0, weight=1)
        grid = ttk.Frame(grid_host)
        grid.grid(row=0, column=0, sticky="nsew")
        for c in range(3):
            grid.columnconfigure(c, weight=1)
        self._build_feature_grid(grid)

        # 底部运行日志：实时滚动，无需另开窗口
        log_card = ttk.Frame(self, style="Card.TFrame", padding=(18, 14))
        log_card.pack(fill="both", expand=True, padx=24, pady=(0, 18))
        log_card.columnconfigure(0, weight=1)
        log_card.rowconfigure(1, weight=1)
        log_head = ttk.Frame(log_card, style="Inner.TFrame")
        log_head.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(log_head, text="运行日志", style="DialogTitle.TLabel").pack(side="left")
        ttk.Label(log_head, text="守护与网络事件实时记录（也会写入日志文件，重启不丢失）",
                  style="Muted.TLabel").pack(side="left", padx=(12, 0))
        log_body = ttk.Frame(log_card, style="Inner.TFrame")
        log_body.grid(row=1, column=0, sticky="nsew")
        log_body.columnconfigure(0, weight=1)
        log_body.rowconfigure(0, weight=1)
        self.txt_log = tk.Text(log_body, bg="#09101c", fg="#b7c4d8",
                               font=("Menlo", 10), relief="flat", wrap="none",
                               state="disabled", insertbackground=FG,
                               selectbackground=ACCENT, height=10,
                               padx=8, pady=6)
        self.txt_log.grid(row=0, column=0, sticky="nsew")
        self._scroll_log_bar = ttk.Scrollbar(log_body, orient="vertical",
                                             command=self.txt_log.yview)
        self._scroll_log_bar.grid(row=0, column=1, sticky="ns")
        self.txt_log.configure(yscrollcommand=self._scroll_log_bar.set)
        self.txt_log.bind("<MouseWheel>", self._scroll_log)
        self._load_existing_log()

    def _feature_card(self, parent, row, col, title, desc, command, attr=None):
        cell = ttk.Frame(parent, style="Card.TFrame", padding=(14, 12))
        cell.grid(row=row, column=col, sticky="nsew", padx=6, pady=6)
        btn = ttk.Button(cell, text=title, style="Feature.TButton", command=command)
        btn.pack(fill="x")
        if attr:
            setattr(self, attr, btn)
        ttk.Label(cell, text=desc, style="Muted.TLabel", wraplength=220,
                  justify="left").pack(anchor="w", pady=(6, 0))
        return btn

    def _build_feature_grid(self, grid):
        """主界面 10 项功能宫格 (v4.0.4: 路由器三件套展开为中继/代理/检测)。"""
        self.btn_share = None
        self.btn_console = None
        # 第 1 行: 连接档案 / 隧道共享 / 热点分享 (核心接入)
        self._feature_card(grid, 0, 0, "连接档案",
                        "多网络账号配置，按 WiFi/网关自动匹配",
                        self.open_profile_window)
        self._feature_card(grid, 0, 1, "隧道共享",
                        "一个账号带全部设备（代理 / PAC / 扫码一键配置）",
                        self.toggle_share, attr="btn_share")
        self._feature_card(grid, 0, 2, "热点分享",
                        "电脑开系统热点，设备连接即上网（只占 1 名额）",
                        self.open_hotspot_window)
        # 第 2 行: 路由器三件套 + 网络控制台
        self._feature_card(grid, 1, 0, "路由器中继",
                        "路由器连校园网 → 家里 WiFi 不刷固件（按品牌分步）",
                        lambda: self._fwin_open_legacy("router_relay", self.show_router_relay_window))
        self._feature_card(grid, 1, 1, "路由器代理",
                        "路由器自身开 HTTP 代理 → 手机不认证走代理到路由器",
                        lambda: self._fwin_open_legacy("router_proxy", self.show_router_proxy_window))
        self._feature_card(grid, 1, 2, "路由器检测",
                        "识别品牌 / 型号 / 管理页 + 官方固件查询",
                        lambda: self._fwin_open_legacy("router", self.show_router_assessment))
        self._feature_card(grid, 1, 3, "网络控制台",
                        "手机浏览器远程看状态 / 日志 / 管授权设备",
                        self.toggle_console, attr="btn_console")
        # 第 3 行: 网络测速 / 新手向导 / 偏好设置
        self._feature_card(grid, 2, 0, "网络测速",
                        "VPN 对比测速 / 延迟抖动 / 质量评分",
                        lambda: self._fwin_open_legacy("speed", self.show_speed_test))
        self._feature_card(grid, 2, 1, "新手向导",
                        "三种上网方式分步引导（直连 / 中继 / 隧道）",
                        lambda: self._fwin_open_legacy("wizard", self.show_wizard))
        self._feature_card(grid, 2, 2, "偏好设置",
                        "网络历史 / 报告 / 自动更新 / 诊断 / 帮助 / 通知 / 保活",
                        lambda: self._fwin_open_legacy("prefs", self.show_preferences))


    def _scroll_log(self, event):
        """鼠标位于日志窗口时只滚动日志，不移动主界面。"""
        txt = getattr(self, "txt_log", None)
        if txt is None:
            return
        try:
            if not txt.winfo_exists():
                return
        except Exception:
            return
        if event.delta:
            txt.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"


    def _toggle_log(self):
        pass


    def _row(self, parent, row, label):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
        ent = ttk.Entry(parent, width=24)
        ent.grid(row=row, column=1, sticky="w", pady=4)
        return ent


    def _load_existing_log(self):
        txt = getattr(self, "txt_log", None)
        if txt is None:
            return
        try:
            if not txt.winfo_exists():
                return
        except Exception:
            return
        try:
            if os.path.exists(core.LOG_PATH):
                with open(core.LOG_PATH, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                self._append_log("".join(lines[-50:]).rstrip("\n"))
        except Exception:
            pass


    def _append_log(self, text):
        txt = getattr(self, "txt_log", None)
        if txt is None:
            return
        try:
            if not txt.winfo_exists():
                return
        except Exception:
            return
        if not text:
            return
        txt.configure(state="normal")
        txt.insert("end", text + "\n")
        txt.see("end")
        if int(txt.index("end-1c").split(".")[0]) > 500:
            txt.delete("1.0", "200.0")
        txt.configure(state="disabled")


    def _poll_log(self):
        try:
            while True:
                line = self.log_q.get_nowait()
                self._append_log(line)
        except queue.Empty:
            pass
        self.after(300, self._poll_log)

    # ---------- 档案管理 ----------

    def _log(self, msg):
        line = core.log(msg)
        self.log_q.put(line)

    # ---------- 状态 ----------


if __name__ == "__main__":
    App().mainloop()
