# -*- coding: utf-8 -*-
"""
校园网连接管家 - 桌面端 (v5.0.0 双栏版)
排版: v2 双栏(左=连接档案内嵌表单 / 右=功能导航) + v4 全功能整合
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
        # v5: 双栏布局需要更宽; 高度给足, 保证默认尺寸下左栏表单完整可见(无文字截断)
        width = min(1140, max(1040, screen_w - 80))
        height = min(880, max(812, screen_h - 100))
        x = max(20, (screen_w - width) // 2)
        y = max(40, (screen_h - height) // 2)
        self.geometry("%dx%d+%d+%d" % (width, height, x, y))
        self.minsize(min(1020, screen_w - 40), min(780, screen_h - 60))
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
        self._refresh_vpn_status()

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
        s.configure("CardSubTitle.TLabel", background=CARD, foreground=FG,
                    font=("PingFang SC", 12, "bold"))
        s.configure("Field.TLabel", background=CARD, foreground=MUTED, font=FONT_S)
        s.configure("Status.TLabel", background=CARD, foreground=FG, font=FONT_S)
        s.configure("NavSep.TLabel", background=CARD, foreground=MUTED,
                    font=("PingFang SC", 10, "bold"))
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
        # ===== 顶栏: 品牌在左 + 版本/检查更新在右 =====
        top = ttk.Frame(self, padding=(24, 16, 24, 8))
        top.pack(fill="x")
        brand = ttk.Frame(top)
        brand.pack(side="left")
        ttk.Label(brand, text="校园网连接管家", style="Title.TLabel").pack(anchor="w")
        ttk.Label(brand, text="自动识别网络 · 保持校园网稳定在线", style="Sub.TLabel").pack(
            anchor="w", pady=(3, 0))
        verbox = ttk.Frame(top)
        verbox.pack(side="right", anchor="n", pady=(8, 0))
        ttk.Label(verbox, text="v" + core.APP_VERSION, style="Sub.TLabel").pack(side="left")
        ttk.Button(verbox, text="检查更新", style="Quiet.TButton",
                   command=lambda: self._bg_check_update(manual=True)).pack(
                       side="left", padx=(10, 0))

        # ===== 状态条: 守护 / 网络 / 环境 =====
        status = ttk.Frame(self, style="Card.TFrame", padding=(20, 12))
        status.pack(fill="x", padx=24, pady=(2, 12))
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

        # ===== 主体双栏: 左=连接档案(内嵌动态表单) / 右=功能导航 =====
        body = ttk.Frame(self)
        body.pack(fill="both", expand=True, padx=24)
        body.columnconfigure(0, weight=3, minsize=520)
        body.columnconfigure(1, weight=2, minsize=336)
        body.rowconfigure(0, weight=1)

        # ---- 左栏: 连接档案 ----
        pcard = ttk.Frame(body, style="Card.TFrame", padding=(18, 14))
        pcard.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        pcard.columnconfigure(0, weight=1)
        pcard.columnconfigure(1, weight=1)

        head = ttk.Frame(pcard, style="Inner.TFrame")
        head.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Label(head, text="连接档案", style="Section.TLabel").pack(side="left")
        ttk.Label(head, text="按 WiFi / 网关自动匹配, 换网自动切换", style="Muted.TLabel").pack(
            side="left", padx=(12, 0))

        prof_row = ttk.Frame(pcard, style="Inner.TFrame")
        prof_row.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        prof_row.columnconfigure(0, weight=1)
        self.cmb_profile = ttk.Combobox(prof_row, state="readonly")
        self.cmb_profile.grid(row=0, column=0, sticky="ew")
        self.cmb_profile.bind("<<ComboboxSelected>>", self._on_profile_selected)
        ttk.Button(prof_row, text="新建", style="Gray.TButton",
                   command=self.new_profile).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(prof_row, text="删除", style="Quiet.TButton",
                   command=self.del_profile).grid(row=0, column=2, padx=(4, 0))

        type_row = ttk.Frame(pcard, style="Inner.TFrame")
        type_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(12, 0))
        ttk.Label(type_row, text="档案类型", style="Field.TLabel").pack(side="left")
        self.cmb_ptype = ttk.Combobox(
            type_row, state="readonly", width=30,
            values=["校园网认证（登录保活）", "普通WiFi/热点（只检测断网）"])
        self.cmb_ptype.pack(side="left", padx=(12, 0))
        self.cmb_ptype.bind("<<ComboboxSelected>>",
                            lambda e: self._profile_rebuild_form())
        ttk.Button(type_row, text="自动探查当前网络", style="Gray.TButton",
                   command=self._profile_auto_probe).pack(side="right")

        self.lbl_ptype_hint = ttk.Label(pcard, text="", style="Muted.TLabel",
                                        wraplength=520, justify="left")
        self.lbl_ptype_hint.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        # 动态字段容器 (由 _profile_rebuild_form 填充)
        self._profile_form_host = ttk.Frame(pcard, style="Inner.TFrame")
        self._profile_form_host.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(4, 0))
        pcard.rowconfigure(4, weight=1)

        btns = ttk.Frame(pcard, style="Inner.TFrame")
        btns.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)
        btns.columnconfigure(3, weight=1)
        self.btn_save = ttk.Button(btns, text="保存档案", style="Accent.TButton",
                                   command=self.save_profile)
        self.btn_save.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self.btn_check = ttk.Button(btns, text="立即检测", style="Gray.TButton",
                                    command=self.check_now)
        self.btn_check.grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(btns, text="导入配置", style="Quiet.TButton",
                   command=self.import_config).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(btns, text="导出配置", style="Quiet.TButton",
                   command=self.export_config).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        # ---- 右栏: 功能导航 ----
        nav = ttk.Frame(body, style="Card.TFrame", padding=(16, 14))
        nav.grid(row=0, column=1, sticky="nsew")
        nav.columnconfigure(0, weight=1)
        nav.columnconfigure(1, weight=1)

        ttk.Label(nav, text="功能导航", style="Section.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(nav, text="按场景分组, 点按钮直达", style="Muted.TLabel").grid(
            row=0, column=1, columnspan=1, sticky="e")

        def _sep(row, text):
            ttk.Label(nav, text="—— %s ——" % text, style="NavSep.TLabel").grid(
                row=row, column=0, columnspan=2, sticky="ew", pady=(12, 2))

        # 连接
        self.btn_guard = ttk.Button(nav, text="启动守护", style="Green.TButton",
                                    command=self.toggle_daemon)
        self.btn_guard.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Button(nav, text="立即检测", style="Gray.TButton",
                   command=self.check_now).grid(row=2, column=0, sticky="ew", padx=(0, 6),
                                                pady=(6, 0))
        self.var_auto = tk.BooleanVar(value=core.autostart_enabled())
        self.btn_auto = ttk.Button(nav, text="开机自启：关闭", style="AutoOff.TButton",
                                   command=self._toggle_autostart)
        self.btn_auto.grid(row=2, column=1, sticky="ew", pady=(6, 0))
        self._update_auto_btn()

        # 共享上网
        _sep(3, "共享上网")
        self.btn_share = ttk.Button(nav, text="隧道共享（手机借电脑网上网）",
                                    style="Gray.TButton", command=self.toggle_share)
        self.btn_share.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        ttk.Button(nav, text="热点分享", style="Gray.TButton",
                   command=self.open_hotspot_window).grid(row=5, column=0, sticky="ew",
                                                          padx=(0, 6), pady=(6, 0))
        self.btn_console = ttk.Button(nav, text="网络控制台", style="Gray.TButton",
                                      command=self.toggle_console)
        self.btn_console.grid(row=5, column=1, sticky="ew", pady=(6, 0))

        # VPN 加速
        _sep(6, "VPN 加速")
        self.lbl_vpn = ttk.Label(nav, text="", style="Muted.TLabel", wraplength=300,
                                 justify="left")
        self.lbl_vpn.grid(row=7, column=0, columnspan=2, sticky="w", pady=(4, 0))
        ttk.Button(nav, text="配置 VPN 代理", style="Accent.TButton",
                   command=self._vpn_open_dialog).grid(row=8, column=0, sticky="ew",
                                                       padx=(0, 6), pady=(6, 0))
        ttk.Button(nav, text="一键填本机 7890", style="Gray.TButton",
                   command=self._vpn_preset_local).grid(row=8, column=1, sticky="ew",
                                                        pady=(6, 0))
        self.btn_vpn_disable = ttk.Button(nav, text="停用 VPN 加速", style="Quiet.TButton",
                                          command=self._vpn_disable)
        self.btn_vpn_disable.grid(row=9, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # 路由器
        _sep(10, "路由器")
        ttk.Button(nav, text="路由器中继", style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "router_relay", self.show_router_relay_window)).grid(
                           row=11, column=0, sticky="ew", padx=(0, 6), pady=(4, 0))
        ttk.Button(nav, text="路由器代理", style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "router_proxy", self.show_router_proxy_window)).grid(
                           row=11, column=1, sticky="ew", pady=(4, 0))
        ttk.Button(nav, text="路由器检测（品牌/固件查询）", style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "router", self.show_router_assessment)).grid(
                           row=12, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # 工具
        _sep(13, "工具")
        ttk.Button(nav, text="网络测速", style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "speed", self.show_speed_test)).grid(
                           row=14, column=0, sticky="ew", padx=(0, 6), pady=(4, 0))
        ttk.Button(nav, text="新手向导", style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "wizard", self.show_wizard)).grid(
                           row=14, column=1, sticky="ew", pady=(4, 0))
        ttk.Button(nav, text="偏好设置", style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "prefs", self.show_preferences)).grid(
                           row=15, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        # ===== 底部: 可收起运行日志 (默认收起, 展开时自动加高窗口) =====
        log_card = ttk.Frame(self, style="Card.TFrame", padding=(18, 8))
        log_card.pack(fill="x", padx=24, pady=(10, 14))
        self.log_card = log_card
        log_head = ttk.Frame(log_card, style="Inner.TFrame")
        log_head.pack(fill="x")
        ttk.Label(log_head, text="运行日志", style="Section.TLabel").pack(side="left")
        ttk.Label(log_head, text="守护与网络事件实时记录", style="Muted.TLabel").pack(
            side="left", padx=(12, 0))
        self.log_expanded = False
        self.btn_log_toggle = ttk.Button(log_head, text="展开", style="Quiet.TButton",
                                         command=self._toggle_log)
        self.btn_log_toggle.pack(side="right")
        self.log_body = ttk.Frame(log_card, style="Inner.TFrame")
        self.txt_log = tk.Text(self.log_body, bg="#09101c", fg="#b7c4d8",
                               font=("Menlo", 10), relief="flat", wrap="none",
                               state="disabled", insertbackground=FG,
                               selectbackground=ACCENT, height=8,
                               padx=8, pady=6)
        self._scroll_log_bar = ttk.Scrollbar(self.log_body, orient="vertical",
                                             command=self.txt_log.yview)
        self.txt_log.configure(yscrollcommand=self._scroll_log_bar.set)
        self.txt_log.bind("<MouseWheel>", self._scroll_log)
        self._load_existing_log()

    # ---------- VPN 加速 (主窗直达) ----------

    def _refresh_vpn_status(self):
        vpn = self.cfg.get("vpn_upstream") or {}
        host = (vpn.get("host") or "").strip()
        port = vpn.get("port")
        if host and port:
            self.lbl_vpn.configure(
                text="✓ 已启用: 隧道共享的设备流量经 %s:%s 转发 (VPN 全透明)" % (host, port),
                foreground="#3fae7f")
            try:
                self.btn_vpn_disable.configure(state="normal")
            except Exception:
                pass
        else:
            self.lbl_vpn.configure(
                text="未启用: 设备流量直连校园网出口。填入本机 VPN 客户端 (Clash 等) 的 HTTP 端口即可透明加速。",
                foreground=MUTED)
            try:
                self.btn_vpn_disable.configure(state="disabled")
            except Exception:
                pass

    def _vpn_open_dialog(self):
        self._show_vpn_upstream_dialog(on_done=self._refresh_vpn_status)

    def _vpn_preset_local(self):
        self.cfg["vpn_upstream"] = {"host": "127.0.0.1", "port": 7890, "type": "http"}
        core.save_config(self.cfg)
        self._refresh_vpn_status()
        self._log("VPN 加速: 已预设本机 Clash 端口 127.0.0.1:7890 (隧道共享自动生效)")

    def _vpn_disable(self):
        self.cfg.pop("vpn_upstream", None)
        core.save_config(self.cfg)
        self._refresh_vpn_status()
        self._log("VPN 加速: 已停用, 设备流量恢复直连校园网出口")

    # ---------- 日志收起/展开 ----------

    def _toggle_log(self):
        if self.log_expanded:
            self.log_body.pack_forget()
            self.btn_log_toggle.configure(text="展开")
            self.log_expanded = False
        else:
            self.log_body.pack(fill="both", expand=True, pady=(6, 0))
            self._scroll_log_bar.pack(side="right", fill="y")
            self.txt_log.pack(side="left", fill="both", expand=True)
            self.btn_log_toggle.configure(text="收起")
            self.log_expanded = True
            # 展开时若屏幕还有余量, 自动加高窗口, 避免挤压左栏表单
            try:
                screen_h = self.winfo_screenheight()
                h = self.winfo_height()
                want = min(h + 170, screen_h - 60)
                if want > h + 20:
                    self.geometry("%dx%d" % (self.winfo_width(), want))
            except Exception:
                pass

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
