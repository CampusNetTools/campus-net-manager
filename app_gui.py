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
from gui.speed_window import SpeedWindowMixin  # noqa: F401
from gui.tunnel_ui import TunnelUiMixin  # noqa: F401
from gui.preferences import PreferencesMixin  # noqa: F401
from gui.tray import TrayMixin  # noqa: F401
from gui.daemon_ctl import DaemonCtlMixin  # noqa: F401
from gui.wizard import WizardMixin  # noqa: F401
from gui.update_ui import UpdateUiMixin  # noqa: F401
from gui.console_ui import ConsoleUiMixin  # noqa: F401


class App(ProfileFormMixin, RouterToolsMixin, SpeedWindowMixin, TunnelUiMixin, PreferencesMixin, TrayMixin, DaemonCtlMixin, WizardMixin, UpdateUiMixin, ConsoleUiMixin, tk.Tk):
    def __init__(self):
        super().__init__()
        self._instance_lock_file = None
        if not self._acquire_instance_lock():
            self.destroy()
            raise SystemExit(0)
        self.title("校园网连接管家 v" + core.APP_VERSION)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        width = min(1060, max(860, screen_w - 100))
        height = min(760, max(700, screen_h - 180))
        x = max(20, (screen_w - width) // 2)
        y = max(40, (screen_h - height) // 2)
        self.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self.minsize(min(860, screen_w - 40), min(680, screen_h - 100))
        self.configure(bg=BG)
        self._style()

        self.log_q = queue.Queue()
        self.daemon = None
        self.proxy = None
        self._allow_q = queue.Queue()
        self.cfg = core.load_config()

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
        top = ttk.Frame(self, padding=(20, 14, 20, 5))
        top.pack(fill="x")
        brand = ttk.Frame(top)
        brand.pack(side="left")
        ttk.Label(brand, text="校园网连接管家", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="自动识别网络，保持校园网稳定在线", style="Sub.TLabel").pack(anchor="w", pady=(3, 0))
        ttk.Label(top, text="v" + core.APP_VERSION, style="Sub.TLabel").pack(side="right", anchor="n", pady=(8, 0))

        # 状态卡片
        status = ttk.Frame(self, style="Card.TFrame", padding=(14, 8))
        status.pack(fill="x", padx=20, pady=(5, 8))
        for col in (1, 3, 5):
            status.columnconfigure(col, weight=1)

        self.dot_guard = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=("Arial", 11))
        self.dot_guard.grid(row=0, column=0, padx=(0, 8))
        self.lbl_guard = ttk.Label(status, text="守护：未运行", style="Status.TLabel")
        self.lbl_guard.grid(row=0, column=1, sticky="w")

        self.dot_net = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=("Arial", 11))
        self.dot_net.grid(row=0, column=2, padx=(12, 8))
        self.lbl_net = ttk.Label(status, text="网络：未知", style="Status.TLabel")
        self.lbl_net.grid(row=0, column=3, sticky="w")

        self.dot_env = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=("Arial", 11))
        self.dot_env.grid(row=0, column=4, padx=(12, 8))
        envbox = ttk.Frame(status, style="Inner.TFrame")
        envbox.grid(row=0, column=5, sticky="ew")
        self.lbl_env = ttk.Label(envbox, text="环境：检测中…", style="Status.TLabel")
        self.lbl_env.pack(anchor="w")
        self.lbl_last = ttk.Label(envbox, text="上次检测：—", style="Muted.TLabel")
        self.lbl_last.pack(anchor="w", pady=(2, 0))

        # 主工作区
        body = ttk.Frame(self)
        body.pack(fill="x", padx=20)
        body.columnconfigure(0, weight=7)
        body.columnconfigure(1, weight=3, minsize=270)
        body.rowconfigure(0, weight=1)

        # 左侧：连接档案
        pcfg = ttk.Frame(body, style="Card.TFrame", padding=(16, 12))
        pcfg.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        pcfg.columnconfigure(0, weight=1)
        pcfg.columnconfigure(1, weight=1)
        ttk.Label(pcfg, text="连接档案", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(pcfg, text="按 WiFi 或网关自动匹配", style="Muted.TLabel").grid(row=0, column=1, sticky="e")

        prof_row = ttk.Frame(pcfg, style="Inner.TFrame")
        prof_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 8))
        prof_row.columnconfigure(0, weight=1)
        self.cmb_profile = ttk.Combobox(prof_row, state="readonly")
        self.cmb_profile.grid(row=0, column=0, sticky="ew")
        self.cmb_profile.bind("<<ComboboxSelected>>", self._on_profile_selected)
        ttk.Button(prof_row, text="新建", style="Gray.TButton", command=self.new_profile).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(prof_row, text="删除", style="Quiet.TButton", command=self.del_profile).grid(row=0, column=2, padx=(4, 0))

        def _field_label(row, col, text):
            ttk.Label(pcfg, text=text, style="Field.TLabel").grid(
                row=row, column=col, sticky="w", padx=(0 if col == 0 else 8, 0), pady=(2, 3))

        def _field(widget, row, col):
            widget.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0), pady=(0, 4))

        _field_label(2, 0, "档案类型")
        _field_label(2, 1, "")
        self.cmb_ptype = ttk.Combobox(pcfg, state="readonly",
                                      values=["校园网认证（登录保活）", "普通WiFi/热点（只检测断网）"])
        self.cmb_ptype.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))
        self.cmb_ptype.bind("<<ComboboxSelected>>", self._on_ptype_change)
        self.lbl_ptype_hint = ttk.Label(pcfg, text="此档案会登录校园网并保活，认证服务器必填。",
                                        style="Muted.TLabel", wraplength=520)
        self.lbl_ptype_hint.grid(row=3, column=0, columnspan=2, sticky="w", padx=(0, 8), pady=(0, 6))

        _field_label(4, 0, "档案名称")
        _field_label(4, 1, "运营商")
        self.ent_name = ttk.Entry(pcfg)
        _field(self.ent_name, 5, 0)
        self.cmb_type = ttk.Combobox(pcfg, state="readonly",
                                     values=["移动互联网访问 (cmcc)", "联通互联网访问 (unicom)", "教师登录 (teacher)"])
        _field(self.cmb_type, 5, 1)

        _field_label(6, 0, "校园网账号")
        _field_label(6, 1, "密码（macOS 钥匙串）" if core.IS_MACOS else "密码")
        self.ent_user = ttk.Entry(pcfg)
        _field(self.ent_user, 7, 0)
        pwf = ttk.Frame(pcfg, style="Inner.TFrame")
        pwf.grid(row=7, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))
        pwf.columnconfigure(0, weight=1)
        self.ent_pass = ttk.Entry(pwf, show="●")
        self.ent_pass.grid(row=0, column=0, sticky="ew")
        ttk.Button(pwf, text="显示", style="Quiet.TButton", command=self._toggle_pass).grid(row=0, column=1, padx=(5, 0))

        _field_label(8, 0, "绑定 WiFi（SSID，可留空）")
        _field_label(8, 1, "绑定网关（有线，可留空）")
        self.ent_ssid = ttk.Entry(pcfg)
        _field(self.ent_ssid, 9, 0)
        self.ent_gw = ttk.Entry(pcfg)
        _field(self.ent_gw, 9, 1)

        _field_label(10, 0, "检测间隔（秒）")
        _field_label(10, 1, "认证服务器")
        self.cmb_interval = ttk.Combobox(pcfg, values=["60", "300", "600", "1800", "3600"])
        _field(self.cmb_interval, 11, 0)
        authf = ttk.Frame(pcfg, style="Inner.TFrame")
        authf.grid(row=11, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))
        authf.columnconfigure(0, weight=1)
        self.cmb_auth = ttk.Combobox(authf)
        self.cmb_auth.grid(row=0, column=0, sticky="ew")
        self.btn_detect = ttk.Button(authf, text="探测", style="Gray.TButton", command=self.detect_auth)
        self.btn_detect.grid(row=0, column=1, padx=(6, 0))

        btns = ttk.Frame(pcfg, style="Inner.TFrame")
        btns.grid(row=12, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        self.btn_save = ttk.Button(btns, text="保存档案", style="Accent.TButton", command=self.save_profile)
        self.btn_save.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.btn_check = ttk.Button(btns, text="立即检测", style="Gray.TButton", command=self.check_now)
        self.btn_check.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        ttk.Button(btns, text="导入配置", style="Quiet.TButton", command=self.import_config).grid(row=1, column=0, sticky="ew", padx=(0, 5), pady=(3, 0))
        ttk.Button(btns, text="导出配置", style="Quiet.TButton", command=self.export_config).grid(row=1, column=1, sticky="ew", padx=(5, 0), pady=(3, 0))

        # 右侧：连接控制与工具
        sidebar = ttk.Frame(body, style="Card.TFrame", padding=(14, 12))
        sidebar.grid(row=0, column=1, sticky="nsew")
        sidebar.columnconfigure(0, weight=1)
        sidebar.columnconfigure(1, weight=1)
        ttk.Label(sidebar, text="连接控制", style="Section.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(sidebar, text="自动检测与恢复校园网连接", style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 8))
        self.btn_guard = ttk.Button(sidebar, text="启动守护", style="Green.TButton", command=self.toggle_daemon)
        self.btn_guard.grid(row=2, column=0, columnspan=2, sticky="ew")
        self.var_auto = tk.BooleanVar(value=core.autostart_enabled())
        self.btn_auto = ttk.Button(sidebar, text="开机自启：关闭", style="AutoOff.TButton",
                                   command=self._toggle_autostart)
        self.btn_auto.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        self._update_auto_btn()
        ttk.Frame(sidebar, style="Surface.TFrame", height=1).grid(row=4, column=0, columnspan=2, sticky="ew", pady=10)
        ttk.Label(sidebar, text="共享与工具", style="Section.TLabel").grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.btn_share = ttk.Button(sidebar, text="隧道共享", style="Gray.TButton", command=self.toggle_share)
        self.btn_share.grid(row=6, column=0, columnspan=2, sticky="ew")
        ttk.Button(sidebar, text="热点设置", style="Gray.TButton", command=self.show_hotspot).grid(row=7, column=0, sticky="ew", padx=(0, 3), pady=(4, 0))
        ttk.Button(sidebar, text="路由器检测", style="Gray.TButton", command=self.show_router_assessment).grid(row=7, column=1, sticky="ew", padx=(3, 0), pady=(4, 0))
        self.btn_wizard = ttk.Button(sidebar, text="新手向导", style="Gray.TButton", command=self.show_wizard)
        self.btn_wizard.grid(row=8, column=0, sticky="ew", padx=(0, 3), pady=(4, 0))
        ttk.Button(sidebar, text="导出诊断", style="Gray.TButton", command=self.export_diag).grid(row=8, column=1, sticky="ew", padx=(3, 0), pady=(4, 0))
        ttk.Button(sidebar, text="网络测速", style="Gray.TButton", command=self.show_speed_test).grid(
            row=9, column=0, sticky="ew", padx=(0, 3), pady=(4, 0))
        self.btn_help = ttk.Button(sidebar, text="使用帮助", style="Quiet.TButton", command=self.show_help)
        self.btn_help.grid(row=9, column=1, sticky="ew", padx=(3, 0), pady=(4, 0))
        self.btn_console = ttk.Button(sidebar, text="网络控制台", style="Gray.TButton",
                                      command=self.toggle_console)
        self.btn_console.grid(row=10, column=0, sticky="ew", padx=(0, 3), pady=(3, 0))
        ttk.Button(sidebar, text="偏好设置与网络报告", style="Quiet.TButton",
                   command=self.show_preferences).grid(
                       row=10, column=1, sticky="ew", padx=(3, 0), pady=(3, 0))

        # 日志区
        logf = ttk.Frame(self, style="Card.TFrame", padding=(12, 8))
        logf.pack(fill="both", expand=True, padx=20, pady=(8, 14))
        self.log_card = logf
        headf = ttk.Frame(logf, style="Inner.TFrame")
        headf.pack(fill="x")
        ttk.Label(headf, text="运行日志", style="Section.TLabel").pack(side="left")
        self.btn_log_toggle = ttk.Button(headf, text="展开", style="Quiet.TButton", command=self._toggle_log)
        self.btn_log_toggle.pack(side="right")
        self.log_expanded = True
        self.btn_log_toggle.configure(text="收起")
        log_body = ttk.Frame(logf, style="Inner.TFrame")
        log_body.pack(fill="both", expand=True, pady=(6, 0))
        self.log_body = log_body
        self.txt_log = tk.Text(log_body, bg="#09101c", fg="#b7c4d8", font=("Menlo", 10),
                               relief="flat", height=6, wrap="none", state="disabled",
                               insertbackground=FG, selectbackground=ACCENT)
        self.txt_log.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_body, orient="vertical", command=self.txt_log.yview)
        log_scroll.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=log_scroll.set)
        self.txt_log.bind("<MouseWheel>", self._scroll_log)
        self._load_existing_log()


    def _scroll_log(self, event):
        """鼠标位于日志区时只滚动日志，不移动主界面。"""
        if event.delta:
            self.txt_log.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"


    def _toggle_log(self):
        self.log_expanded = not self.log_expanded
        if self.log_expanded:
            self.log_card.pack_propagate(True)
            self.log_body.pack(fill="both", expand=True, pady=(6, 0))
            self.btn_log_toggle.configure(text="收起")
            self.log_card.pack_configure(fill="both", expand=True)
        else:
            self.log_body.pack_forget()
            self.btn_log_toggle.configure(text="展开")
            self.log_card.configure(height=42)
            self.log_card.pack_propagate(False)
            self.log_card.pack_configure(fill="x", expand=False)


    def _row(self, parent, row, label):
        ttk.Label(parent, text=label, style="Card.TLabel").grid(row=row, column=0, sticky="e", padx=(0, 8), pady=4)
        ent = ttk.Entry(parent, width=24)
        ent.grid(row=row, column=1, sticky="w", pady=4)
        return ent


    def _load_existing_log(self):
        try:
            if os.path.exists(core.LOG_PATH):
                with open(core.LOG_PATH, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                self._append_log("".join(lines[-50:]).rstrip("\n"))
        except Exception:
            pass


    def _append_log(self, text):
        if not text:
            return
        self.txt_log.configure(state="normal")
        self.txt_log.insert("end", text + "\n")
        self.txt_log.see("end")
        if int(self.txt_log.index("end-1c").split(".")[0]) > 500:
            self.txt_log.delete("1.0", "200.0")
        self.txt_log.configure(state="disabled")


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
