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

# ---------- 深色主题 ----------
BG = "#0b1220"
CARD = "#131d2e"
CARD2 = "#1b2940"
METRIC = "#17243a"
BORDER = "#2a3a53"
FG = "#f3f7fc"
MUTED = "#8fa1ba"
ACCENT = "#4f7cff"
ACCENT_HOVER = "#416de8"
GREEN = "#32c48d"
RED = "#f06478"
YELLOW = "#f1b84b"
FONT = ("PingFang SC", 11)
FONT_S = ("PingFang SC", 10)
FONT_M = ("PingFang SC", 13, "bold")
FONT_L = ("PingFang SC", 24, "bold")


class App(tk.Tk):
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
        self.cmb_profile.bind("<<ComboboxSelected>>", lambda e: self._load_form_from_current())
        ttk.Button(prof_row, text="新建", style="Gray.TButton", command=self.new_profile).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(prof_row, text="删除", style="Quiet.TButton", command=self.del_profile).grid(row=0, column=2, padx=(4, 0))

        def _field_label(row, col, text):
            ttk.Label(pcfg, text=text, style="Field.TLabel").grid(
                row=row, column=col, sticky="w", padx=(0 if col == 0 else 8, 0), pady=(2, 3))

        def _field(widget, row, col):
            widget.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 8, 8 if col == 0 else 0), pady=(0, 4))

        _field_label(2, 0, "档案名称")
        _field_label(2, 1, "运营商")
        self.ent_name = ttk.Entry(pcfg)
        _field(self.ent_name, 3, 0)
        self.cmb_type = ttk.Combobox(pcfg, state="readonly",
                                     values=["移动互联网访问 (cmcc)", "联通互联网访问 (unicom)", "教师登录 (teacher)"])
        _field(self.cmb_type, 3, 1)

        _field_label(4, 0, "校园网账号")
        _field_label(4, 1, "密码（macOS 钥匙串）" if core.IS_MACOS else "密码")
        self.ent_user = ttk.Entry(pcfg)
        _field(self.ent_user, 5, 0)
        pwf = ttk.Frame(pcfg, style="Inner.TFrame")
        pwf.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))
        pwf.columnconfigure(0, weight=1)
        self.ent_pass = ttk.Entry(pwf, show="●")
        self.ent_pass.grid(row=0, column=0, sticky="ew")
        ttk.Button(pwf, text="显示", style="Quiet.TButton", command=self._toggle_pass).grid(row=0, column=1, padx=(5, 0))

        _field_label(6, 0, "绑定 WiFi（SSID，可留空）")
        _field_label(6, 1, "绑定网关（有线，可留空）")
        self.ent_ssid = ttk.Entry(pcfg)
        _field(self.ent_ssid, 7, 0)
        self.ent_gw = ttk.Entry(pcfg)
        _field(self.ent_gw, 7, 1)

        _field_label(8, 0, "检测间隔（秒）")
        _field_label(8, 1, "认证服务器")
        self.cmb_interval = ttk.Combobox(pcfg, values=["60", "300", "600", "1800", "3600"])
        _field(self.cmb_interval, 9, 0)
        authf = ttk.Frame(pcfg, style="Inner.TFrame")
        authf.grid(row=9, column=1, sticky="ew", padx=(8, 0), pady=(0, 4))
        authf.columnconfigure(0, weight=1)
        self.cmb_auth = ttk.Combobox(authf)
        self.cmb_auth.grid(row=0, column=0, sticky="ew")
        self.btn_detect = ttk.Button(authf, text="探测", style="Gray.TButton", command=self.detect_auth)
        self.btn_detect.grid(row=0, column=1, padx=(6, 0))

        btns = ttk.Frame(pcfg, style="Inner.TFrame")
        btns.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(8, 0))
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
        ttk.Button(sidebar, text="偏好设置与网络报告", style="Quiet.TButton",
                   command=self.show_preferences).grid(
                       row=10, column=0, columnspan=2, sticky="ew", pady=(3, 0))

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
    def _current_profile(self):
        disp = self.cmb_profile.get()
        name = getattr(self, "_profile_map", {}).get(disp, disp)
        for p in self.cfg.get("profiles", []):
            if p["name"] == name:
                return p
        return None

    def _refresh_profile_list(self):
        self._profile_map = {}
        displays = []
        for p in self.cfg.get("profiles", []):
            if p.get("ssid") or p.get("gateway"):
                d = "%s (%s)" % (p["name"], p.get("ssid") or p.get("gateway"))
            else:
                d = "任意网络使用"
            if p.get("preset") == core.LIDA_PROFILE_ID:
                d = "立达专属 · " + d
            self._profile_map[d] = p["name"]
            displays.append(d)
        self.cmb_profile["values"] = displays
        active = self.cfg.get("active_profile")
        if active and active in self._profile_map.values():
            for d, n in self._profile_map.items():
                if n == active:
                    self.cmb_profile.set(d)
                    break
        elif displays:
            self.cmb_profile.set(displays[0])

    def _toggle_pass(self):
        self.ent_pass.configure(show="" if self.ent_pass.cget("show") else "●")

    def _load_form_from_current(self):
        p = self._current_profile()
        if not p:
            return
        def setv(ent, v):
            ent.delete(0, "end")
            ent.insert(0, str(v or ""))
        setv(self.ent_name, p.get("name", ""))
        setv(self.ent_ssid, p.get("ssid", ""))
        setv(self.ent_gw, p.get("gateway", ""))
        setv(self.ent_user, p.get("username", ""))
        setv(self.ent_pass, p.get("password", ""))
        self.cmb_interval.set(str(p.get("interval", 1800)))
        history = self.cfg.get("auth_history") or []
        cur = p.get("auth_url", core.DEFAULT_AUTH_URL)
        if cur and cur not in history:
            history = [cur] + history
        self.cmb_auth["values"] = history[-15:]
        self.cmb_auth.set(cur)
        lt = p.get("login_type", "cmcc")
        self.cmb_type.current({"cmcc": 0, "unicom": 1, "teacher": 2}.get(lt, 0))

    def _form_to_profile(self):
        lt = {0: "cmcc", 1: "unicom", 2: "teacher"}[self.cmb_type.current()]
        return {
            "name": self.ent_name.get().strip(),
            "ssid": self.ent_ssid.get().strip(),
            "gateway": self.ent_gw.get().strip(),
            "username": self.ent_user.get().strip(),
            "password": self.ent_pass.get().strip(),
            "login_type": lt,
            "auth_url": self.cmb_auth.get().strip() or core.DEFAULT_AUTH_URL,
            "interval": max(10, int(self.cmb_interval.get() or 1800)),
        }

    def new_profile(self):
        base = "新档案"
        i = 1
        names = [p["name"] for p in self.cfg.get("profiles", [])]
        while base + str(i) in names:
            i += 1
        self.cfg.setdefault("profiles", []).append(core.default_profile(base + str(i)))
        self.cfg["active_profile"] = base + str(i)
        core.save_config(self.cfg)
        self._refresh_profile_list()
        self._load_form_from_current()
        self._log("已新建档案: %s" % (base + str(i)))

    def del_profile(self):
        p = self._current_profile()
        if not p:
            return
        if p.get("preset") == core.LIDA_PROFILE_ID:
            messagebox.showinfo("内置档案", "立达校园网是内置专属档案，不能删除。\n账号、密码和运营商可以自由修改。")
            return
        if len(self.cfg["profiles"]) <= 1:
            messagebox.showwarning("提示", "至少保留一个档案")
            return
        if not messagebox.askyesno("删除档案", "确定删除档案「%s」吗？" % p["name"]):
            return
        core.keychain_delete(p.get("secret_id"))
        self.cfg["profiles"].remove(p)
        self.cfg["active_profile"] = self.cfg["profiles"][0]["name"]
        core.save_config(self.cfg)
        self._refresh_profile_list()
        self._load_form_from_current()
        self._log("已删除档案: %s" % p["name"])

    def save_profile(self):
        try:
            data = self._form_to_profile()
            if not data["name"]:
                messagebox.showwarning("提示", "档案名称不能为空")
                return
            if not data["username"] or not data["password"]:
                messagebox.showwarning("提示", "账号和密码不能为空")
                return
            p = self._current_profile()
            if p:
                p.update(data)
            self.cfg["active_profile"] = data["name"]
            # 记录认证服务器历史
            hist = [h for h in (self.cfg.get("auth_history") or []) if h != data["auth_url"]]
            self.cfg["auth_history"] = [data["auth_url"]] + hist
            self.cfg["auth_history"] = self.cfg["auth_history"][-15:]
            core.save_config(self.cfg, sync_secrets=True)
            self._refresh_profile_list()
            self._log("档案已保存: %s (%s)" % (data["name"], data["ssid"] or "默认"))
            secure_note = "\n密码已安全保存到 macOS 钥匙串。" if core.IS_MACOS else ""
            messagebox.showinfo("已保存", "档案「%s」已保存。%s\n\n换网络后 App 会根据 WiFi 自动匹配对应档案。" % (
                data["name"], secure_note))
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def open_router_admin(self):
        threading.Thread(target=self._do_open_router, daemon=True).start()

    def _do_open_router(self):
        self._log("正在探测路由器管理页...")
        fingerprint = core.router_fingerprint()
        saved = (self.cfg.get("routers") or {}).get(fingerprint, {})
        url = saved.get("admin_url") or core.get_router_admin_url()
        if url:
            self._log("打开管理页: %s" % url)
            webbrowser.open(url)
        else:
            self._log("未检测到路由器管理页")
            self.after(0, lambda: messagebox.showwarning(
                "未找到", "没检测到路由器管理页。\n请确认电脑已连接路由器 WiFi 后重试。"))

    def show_router_assessment(self):
        """路由器只读体检：收集证据、保存入口，但绝不自动刷写固件。"""
        win = tk.Toplevel(self)
        win.title("路由器检测与适配评估")
        win.configure(bg=BG)
        win.geometry("720x610")
        win.minsize(680, 570)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(22, 18))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text="路由器检测与适配评估", style="Section.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(card, text="只读识别，不登录路由器、不修改配置、不写入固件",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=3, sticky="w", pady=(3, 14))

        fields = (("品牌", "brand"), ("型号", "model"), ("硬件版本", "revision"),
                  ("网关 / MAC", "network"), ("固定管理入口", "admin_url"))
        entries = {}
        for row, (label, key) in enumerate(fields, start=2):
            ttk.Label(card, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", pady=4)
            entry = ttk.Entry(card)
            entry.grid(row=row, column=1, columnspan=2, sticky="ew", padx=(12, 0), pady=4)
            entries[key] = entry
        entries["brand"].configure(state="readonly")
        entries["network"].configure(state="readonly")

        status = tk.Text(card, height=10, bg="#09101c", fg="#b7c4d8", font=("PingFang SC", 10),
                         relief="flat", wrap="word", padx=12, pady=10, state="disabled")
        status.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(12, 10))
        card.rowconfigure(7, weight=1)

        warning = ("安全边界：刷机不可能保证‘对路由器没有影响’。只有精确型号和硬件版本、"
                   "OpenWrt 官方适配、镜像校验、配置备份和恢复方案全部确认后，才能进入最后人工确认。")
        ttk.Label(card, text=warning, style="Muted.TLabel", justify="left", wraplength=650).grid(
            row=8, column=0, columnspan=3, sticky="w", pady=(0, 10))

        current = {"report": None}

        def set_entry(entry, value):
            old_state = str(entry.cget("state"))
            entry.configure(state="normal")
            entry.delete(0, "end")
            entry.insert(0, value or "")
            entry.configure(state=old_state)

        def set_status(text):
            status.configure(state="normal")
            status.delete("1.0", "end")
            status.insert("1.0", text)
            status.configure(state="disabled")

        def render(report):
            current["report"] = report
            saved = (self.cfg.get("routers") or {}).get(report["fingerprint"], {})
            set_entry(entries["brand"], report["brand"] or "未识别")
            set_entry(entries["model"], saved.get("model") or report["model"])
            set_entry(entries["revision"], saved.get("revision") or report["revision"])
            set_entry(entries["network"], "%s  /  %s" % (report["gateway"] or "无网关", report["mac"] or "无 MAC"))
            set_entry(entries["admin_url"], saved.get("admin_url") or report["admin_url"])
            evidence = report.get("evidence") or {}
            lines = [
                "系统识别：%s" % ("OpenWrt / LuCI" if report["openwrt"] else "未识别为 OpenWrt"),
                "管理页：%s" % (report["page_title"] or report["admin_url"] or "未发现"),
                "WISP 评估：%s" % report["wisp_status"],
                "刷机评估：%s" % report["flash_status"],
            ]
            if evidence:
                lines.append("UPnP 证据：%s" % " / ".join(filter(None, (
                    evidence.get("friendlyName"), evidence.get("manufacturer"),
                    evidence.get("modelName"), evidence.get("modelNumber")))))
            set_status("\n\n".join(lines))
            btn_detect.configure(text="重新检测", state="normal")

        def detect():
            btn_detect.configure(text="检测中…", state="disabled")
            set_status("正在读取网关、ARP、管理页公开标识和 UPnP 设备描述……")
            def work():
                try:
                    report = core.detect_router_hardware()
                    self.after(0, lambda: render(report))
                except Exception as exc:
                    error = str(exc)
                    self.after(0, lambda value=error: (set_status("检测失败：%s" % value),
                                          btn_detect.configure(text="重新检测", state="normal")))
            threading.Thread(target=work, daemon=True).start()

        def save_router():
            report = current["report"]
            if not report:
                messagebox.showwarning("尚未检测", "请先完成一次路由器检测。", parent=win)
                return
            model = entries["model"].get().strip()
            revision = entries["revision"].get().strip()
            admin_url = entries["admin_url"].get().strip()
            if admin_url and not core._private_http_url(admin_url):
                messagebox.showwarning("地址无效", "固定入口必须是局域网 HTTP/HTTPS 地址。", parent=win)
                return
            self.cfg.setdefault("routers", {})[report["fingerprint"]] = {
                "brand": report["brand"], "model": model, "revision": revision,
                "admin_url": admin_url, "last_checked": core.now_str(),
            }
            core.save_config(self.cfg)
            readiness = core.evaluate_flash_readiness(model, revision)
            self._log("已保存路由器识别信息与固定管理入口")
            messagebox.showinfo("已保存", "以后会优先打开这个管理入口。\n\n%s" % readiness["message"], parent=win)

        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.grid(row=9, column=0, columnspan=3, sticky="ew")
        for col in range(4):
            actions.columnconfigure(col, weight=1)
        btn_detect = ttk.Button(actions, text="开始检测", style="Accent.TButton", command=detect)
        btn_detect.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(actions, text="保存识别结果", style="Gray.TButton", command=save_router).grid(
            row=0, column=1, sticky="ew", padx=4)
        ttk.Button(actions, text="打开管理页", style="Gray.TButton", command=self.open_router_admin).grid(
            row=0, column=2, sticky="ew", padx=4)
        ttk.Button(actions, text="官方适配查询", style="Gray.TButton",
                   command=lambda: webbrowser.open("https://firmware-selector.openwrt.org/")).grid(
            row=0, column=3, sticky="ew", padx=(4, 0))
        detect()

    def show_speed_test(self):
        """轻量测速：可测当前 VPN 路径，也可在 macOS 上绑定物理网卡绕过 VPN。"""
        win = tk.Toplevel(self)
        win.title("网络测速")
        win.configure(bg=BG)
        win.geometry("680x570")
        win.resizable(False, False)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 20))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="网络测速", style="DialogTitle.TLabel").pack(anchor="w")
        subtitle = ttk.Label(card, text="", style="Muted.TLabel")
        subtitle.pack(anchor="w", pady=(4, 12))
        vpn_row = ttk.Frame(card, style="Inner.TFrame")
        vpn_row.pack(fill="x")
        vpn_dot = tk.Label(vpn_row, text="●", fg=MUTED, bg=CARD, font=("Arial", 11))
        vpn_dot.pack(side="left", padx=(0, 8))
        vpn_status = ttk.Label(vpn_row, text="正在识别 VPN…", style="Card.TLabel")
        vpn_status.pack(side="left")

        def refresh_speed_plan():
            plan = core.automatic_speed_test_plan()
            if plan["compare"]:
                vpn_dot.configure(fg=GREEN)
                vpn_status.configure(text="已检测到 VPN，将自动对比两种连接")
                subtitle.configure(text="自动测试经过 VPN 与未经过 VPN的网络；预计使用约 24 MB 流量")
            elif plan["vpn_active"]:
                vpn_dot.configure(fg=YELLOW)
                vpn_status.configure(text="已检测到 VPN，当前系统仅测试 VPN 连接")
                subtitle.configure(text="本次预计使用约 12 MB 流量")
            else:
                vpn_dot.configure(fg=MUTED)
                vpn_status.configure(text="未检测到 VPN，将测试当前网络")
                subtitle.configure(text="本次预计使用约 12 MB 流量")
            return plan

        refresh_speed_plan()

        result_box = ttk.Frame(card, style="Surface.TFrame", padding=(14, 14))
        result_box.pack(fill="both", expand=True, pady=(16, 12))
        for col in range(3):
            result_box.columnconfigure(col, weight=1)
        for row in range(2):
            result_box.rowconfigure(row, weight=1)
        values = {}
        subtexts = {}
        metrics = (("latency", "延迟"), ("download", "下载"), ("upload", "上传"),
                   ("jitter", "抖动"), ("success", "请求成功率"), ("quality", "网络质量"))
        for index, (key, title) in enumerate(metrics):
            row, col = divmod(index, 3)
            cell = ttk.Frame(result_box, style="Metric.TFrame", padding=(12, 10))
            cell.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            cell.columnconfigure(0, weight=1)
            ttk.Label(cell, text=title, style="MetricTitle.TLabel").grid(row=0, column=0)
            label = ttk.Label(cell, text="—", style="MetricValue.TLabel")
            label.grid(row=1, column=0, pady=(5, 4))
            sublabel = ttk.Label(cell, text=" ", style="MetricSub.TLabel", anchor="center")
            sublabel.grid(row=2, column=0, sticky="ew")
            values[key] = label
            subtexts[key] = sublabel
        path_label = ttk.Label(result_box, text="点击下方按钮开始自动测速", style="SurfaceMuted.TLabel")
        path_label.grid(row=2, column=0, columnspan=3, pady=(10, 2))
        detail_label = ttk.Label(result_box, text="", style="SurfaceMuted.TLabel")
        detail_label.grid(row=3, column=0, columnspan=3)

        def set_metric_hints():
            hints = {
                "latency": "TCP/TLS 校正", "download": "当前路径", "upload": "当前路径",
                "jitter": "越低越稳定", "success": "6 次请求", "quality": "综合评分",
            }
            for key, text in hints.items():
                subtexts[key].configure(text=text)

        def clear_metric_subtexts():
            for label in subtexts.values():
                label.configure(text=" ")

        def set_running(running, comparing=False):
            btn.configure(state="disabled" if running else "normal",
                          text=("正在自动对比…" if comparing else "测速中…") if running else "开始测速")

        def render(result):
            values["latency"].configure(text="%.0f ms" % result["latency_ms"])
            values["download"].configure(text="%.1f Mbps" % result["download_mbps"])
            values["upload"].configure(text="%.1f Mbps" % result["upload_mbps"])
            values["jitter"].configure(text="%.1f ms" % result["jitter_ms"])
            values["success"].configure(text="%.0f%%" % result["success_rate"])
            values["quality"].configure(text="%d · %s" % (result["quality_score"], result["quality_grade"]))
            path_label.configure(text=result["path_label"])
            detail_label.configure(text="接口：%s    测试流量：%.1f MB" % (
                result["interface"] or "系统默认", result["traffic_mb"]))

        def finish(result=None, error=None):
            set_running(False)
            if error:
                path_label.configure(text="测速失败：%s" % error)
                self._log("测速失败: %s" % error)
                return
            render(result)
            set_metric_hints()
            self._log("测速完成 [%s] 延迟 %.0fms / 下载 %.1fMbps / 上传 %.1fMbps" % (
                result["path_label"], result["latency_ms"], result["download_mbps"], result["upload_mbps"]))

        def finish_compare(results=None, error=None):
            set_running(False)
            if error:
                path_label.configure(text="VPN 对比失败：%s" % error)
                return
            vpn_result, physical_result = results
            render(vpn_result)
            latency_delta = vpn_result["latency_ms"] - physical_result["latency_ms"]
            down_change = (vpn_result["download_mbps"] / max(physical_result["download_mbps"], 0.01) - 1.0) * 100.0
            up_change = (vpn_result["upload_mbps"] / max(physical_result["upload_mbps"], 0.01) - 1.0) * 100.0
            jitter_delta = vpn_result["jitter_ms"] - physical_result["jitter_ms"]
            comparison = {
                "latency": "直连 %.0f ms  ·  VPN %+.0f ms" % (physical_result["latency_ms"], latency_delta),
                "download": "直连 %.1f Mbps  ·  VPN %+.0f%%" % (physical_result["download_mbps"], down_change),
                "upload": "直连 %.1f Mbps  ·  VPN %+.0f%%" % (physical_result["upload_mbps"], up_change),
                "jitter": "直连 %.1f ms  ·  VPN %+.1f ms" % (physical_result["jitter_ms"], jitter_delta),
                "success": "直连 %.0f%%  ·  VPN %.0f%%" % (physical_result["success_rate"], vpn_result["success_rate"]),
                "quality": "直连 %d · %s" % (physical_result["quality_score"], physical_result["quality_grade"]),
            }
            for key, text in comparison.items():
                subtexts[key].configure(text=text)
            path_label.configure(text="当前显示：经过 VPN 的测速结果")
            detail_label.configure(text="已自动与直连网络对比    每种连接约 %.1f MB" % vpn_result["traffic_mb"])

        def start():
            plan = refresh_speed_plan()
            compare = plan["compare"]
            set_running(True, comparing=compare)
            for label in values.values():
                label.configure(text="…")
            clear_metric_subtexts()
            def progress(text):
                self.after(0, lambda value=text: path_label.configure(text=value))
            def work():
                try:
                    if compare:
                        vpn_result = core.run_speed_test("current", progress=progress)
                        physical_result = core.run_speed_test("physical", progress=progress)
                        self.after(0, lambda: finish_compare(results=(vpn_result, physical_result)))
                    else:
                        result = core.run_speed_test("current", progress=progress)
                        self.after(0, lambda: finish(result=result))
                except Exception as exc:
                    error = str(exc)
                    callback = finish_compare if compare else finish
                    self.after(0, lambda value=error, target=callback: target(error=value))
            threading.Thread(target=work, daemon=True).start()

        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.pack(fill="x")
        actions.columnconfigure(0, weight=1)
        btn = ttk.Button(actions, text="开始测速", style="Accent.TButton", command=start)
        btn.grid(row=0, column=0, sticky="ew")

    def toggle_share(self):
        """隧道共享: 其他设备(手机/平板)借本机网络访问外网 (带访问控制)"""
        if self.proxy and self.proxy.running:
            self.proxy.stop()
            # 保存授权设备列表
            allow = sorted(self.proxy.allowed)
            if allow != list(self.cfg.get("tunnel_allow", [])):
                self.cfg["tunnel_allow"] = allow
                core.save_config(self.cfg)
            self._log("隧道共享已停止 (授权设备 %d 台已记住)" % len(allow))
            self.proxy = None
            self.btn_share.configure(text="隧道共享", style="Gray.TButton")
            return
        try:
            allowed = list(self.cfg.get("tunnel_allow", []))
            ips = shared_proxy.get_lan_ips()
            myip = ips[0] if ips else None
            self.proxy = shared_proxy.SharedProxy(port=8080, allowed=allowed,
                                                  on_ask=self._ask_tunnel_allow,
                                                  pac_host=myip)
            self.proxy.start()
        except Exception as e:
            self.proxy = None
            messagebox.showerror("开启失败",
                                 "无法监听 8080 端口：%s\n\n可能是端口被占用，或需要防火墙放行。" % e)
            return
        self.btn_share.configure(text="隧道共享：已开启", style="Green.TButton")
        myip = myip or "本机IP"
        pac_url = "http://%s:8080/proxy.pac" % myip
        setup_url = "http://%s:8080/" % myip
        verified = myip != "本机IP" and shared_proxy.check_setup_page(myip)
        try:
            self.clipboard_clear()
            self.clipboard_append(pac_url)
            self.update_idletasks()
        except Exception:
            pass
        self._log("隧道共享已开启并完成%s: %s:8080 (已有授权设备 %d 台)"
                  % ("自检" if verified else "启动", myip, len(self.proxy.allowed)))
        self._show_tunnel_ready(myip, pac_url, setup_url, verified)

    def _show_tunnel_ready(self, myip, pac_url, setup_url, verified):
        """用应用内统一样式展示一键隧道结果，避免系统消息框拥挤。"""
        win = tk.Toplevel(self)
        win.title("隧道共享")
        win.configure(bg=BG)
        win.geometry("620x430")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 22))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(card, text="隧道已经准备好", style="Section.TLabel").pack(anchor="w")
        status_text = ("服务自检通过，自动配置地址已复制。" if verified else
                       "服务已启动，但局域网自检未通过；请检查防火墙。")
        ttk.Label(card, text=status_text,
                  style="Muted.TLabel").pack(anchor="w", pady=(5, 18))

        content = ttk.Frame(card, style="Inner.TFrame")
        content.pack(fill="both", expand=True)
        left = ttk.Frame(content, style="Inner.TFrame")
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="手机自动代理地址", style="Field.TLabel").pack(anchor="w")
        value = ttk.Entry(left)
        value.insert(0, pac_url)
        value.configure(state="readonly")
        value.pack(fill="x", pady=(6, 14))

        guide = ("手机与电脑连接同一 Wi‑Fi 后：\n"
                 "Wi‑Fi 详情  →  配置代理  →  自动  →  粘贴上面的地址。\n\n"
                 "如果设备没有“自动”选项，请改用手动代理：\n"
                 "服务器 %s    端口 8080\n\n"
                 "首次访问时，本机会询问是否允许该设备。" % myip)
        ttk.Label(left, text=guide, style="Card.TLabel", justify="left", wraplength=350).pack(anchor="w")

        if HAS_QR:
            qr_image = qrcode.make(setup_url).resize((150, 150))
            qr_photo = ImageTk.PhotoImage(qr_image)
            qr_box = ttk.Frame(content, style="Surface.TFrame", padding=8)
            qr_box.pack(side="right", anchor="n", padx=(16, 0))
            qr_label = tk.Label(qr_box, image=qr_photo, bg="#ffffff", bd=0)
            qr_label.image = qr_photo
            qr_label.pack()
            ttk.Label(qr_box, text="手机扫码查看步骤", style="SurfaceMuted.TLabel").pack(pady=(6, 0))

        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.pack(fill="x", side="bottom", pady=(18, 0))
        ttk.Button(actions, text="复制自动配置地址", style="Gray.TButton",
                   command=lambda: self._copy_text(pac_url)).pack(side="left")
        ttk.Button(actions, text="打开手机引导页", style="Gray.TButton",
                   command=lambda: webbrowser.open(setup_url)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="完成", style="Accent.TButton", command=win.destroy).pack(side="right")

    def _copy_text(self, text):
        try:
            self.clipboard_clear()
            self.clipboard_append(text)
            self.update_idletasks()
        except Exception:
            pass

    def _ask_tunnel_allow(self, ip):
        """代理线程调用: 询问用户是否允许新设备使用隧道 (最多等 45 秒)"""
        try:
            ev = threading.Event()
            holder = {}
            self._allow_q.put((ip, ev, holder))
            ev.wait(45)
            return holder.get("ok", False)
        except Exception:
            return False

    def _poll_allow(self):
        """主线程轮询: 处理新设备的授权弹窗"""
        try:
            while True:
                ip, ev, holder = self._allow_q.get_nowait()
                self._on_alert("有新设备请求使用隧道共享：%s" % ip, "device")
                ok = messagebox.askyesno(
                    "设备连接请求",
                    "有设备 (%s) 想使用你的隧道共享上网。\n\n"
                    "选择允许会记住该设备，以后不再询问。\n"
                    "选择拒绝会断开本次连接。" % ip,
                    parent=self)
                holder["ok"] = bool(ok)
                ev.set()
        except queue.Empty:
            pass
        self.after(400, self._poll_allow)

    def show_hotspot(self):
        """移动热点共享: 电脑 1 个名额带所有设备 (设备直连校园网场景)"""
        on = core.hotspot_on()
        if on:
            self._log("热点检测: 已开启 (其他设备可连接电脑热点共享上网)")
            messagebox.showinfo(
                "📶 热点已开启",
                "移动热点正在运行。\n\n手机/平板连接电脑热点即可上网，"
                "不占用额外校园网名额。\n\nWiFi 名称与密码：\n"
                "设置 → 网络和 Internet → 移动热点 中查看/修改。")
        elif core.IS_MACOS:
            self._log("打开 macOS 互联网共享设置引导")
            if core.open_hotspot_settings():
                messagebox.showinfo(
                    "📶 开启互联网共享",
                    "已打开 macOS「通用 → 共享」设置页。\n\n"
                    "选择「互联网共享」后，把校园网连接共享给 Wi‑Fi，"
                    "再让手机/平板连接你设置的热点。\n\n"
                    "macOS 不提供稳定的无权限状态读取，因此请在该页面确认开关状态。")
            else:
                messagebox.showerror("打开失败", "请手动打开：系统设置 → 通用 → 共享 → 互联网共享")
        else:
            self._log("热点检测: 未开启, 打开设置引导")
            if core.open_hotspot_settings():
                messagebox.showinfo(
                    "📶 开启热点共享",
                    "已为你打开「移动热点」设置页。\n\n只需两步：\n"
                    "① 打开「与其他设备共享我的 Internet 连接」开关\n"
                    "② 手机/平板连接电脑热点（名称密码见该页面）\n\n"
                    "原理：所有设备走电脑的网络，只占用电脑 1 个校园网名额，"
                    "不受 2 台限制。")
            else:
                messagebox.showerror("打开失败", "无法打开移动热点设置，请手动打开：\n设置 → 网络和 Internet → 移动热点")

    def _update_auto_btn(self):
        on = self.var_auto.get()
        self.btn_auto.configure(text="开机自启：开启" if on else "开机自启：关闭",
                                style="AutoOn.TButton" if on else "AutoOff.TButton")

    def _toggle_autostart(self):
        previous = self.var_auto.get()
        target = not previous
        ok = core.set_autostart(target)
        if not ok:
            self.var_auto.set(previous)
            messagebox.showerror("失败", "修改开机自启失败（可能需要权限）")
        else:
            self.var_auto.set(target)
            self._log("开机自启: %s" % ("已开启" if target else "已关闭"))
        self._update_auto_btn()

    def export_config(self):
        path = filedialog.asksaveasfilename(
            title="导出配置", defaultextension=".json",
            initialfile="校园网连接管家配置.json",
            filetypes=[("JSON 配置", "*.json")])
        if not path:
            return
        try:
            import json
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(core.config_for_export(self.cfg), handle, ensure_ascii=False, indent=2)
            messagebox.showinfo("已导出", "配置已导出到：\n%s\n\n为保护账号安全，导出文件不包含密码。" % path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def import_config(self):
        path = filedialog.askopenfilename(
            title="导入配置", filetypes=[("JSON 配置", "*.json")])
        if not path:
            return
        try:
            import json
            with open(path, "r", encoding="utf-8") as handle:
                imported = json.load(handle)
            for profile in imported.get("profiles", []):
                profile.pop("secret_id", None)
                profile.pop("password_store", None)
            core.ensure_lida_profile(imported)
            core.ensure_preferences(imported)
            core.save_config(imported, sync_secrets=True)
            self.cfg = core.load_config()
            self._refresh_profile_list()
            self._load_form_from_current()
            self._log("配置已导入: %s" % path)
            messagebox.showinfo("已导入", "配置导入成功。\n未包含密码的档案需要重新填写密码；重启守护后生效。")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

    def show_preferences(self):
        """网络记录和系统通知集中设置，避免继续挤占主界面。"""
        core.ensure_preferences(self.cfg)
        win = tk.Toplevel(self)
        win.title("偏好设置与网络报告")
        win.configure(bg=BG)
        win.geometry("620x570")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()

        card = ttk.Frame(win, style="Card.TFrame", padding=(22, 18))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="偏好设置", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="只记录连接状态，不记录浏览内容、账号或密码。",
                  style="Muted.TLabel").pack(anchor="w", pady=(3, 12))
        ttk.Label(card, text="绿色对号表示已选择；点击“保存设置”后正式生效。",
                  style="Muted.TLabel").pack(anchor="w", pady=(0, 10))

        var_history = tk.BooleanVar(value=self.cfg.get("history_enabled", False))
        notifications = self.cfg.get("notifications", {})
        var_notify = tk.BooleanVar(value=notifications.get("enabled", True))
        category_vars = {
            "disconnect": tk.BooleanVar(value=notifications.get("disconnect", True)),
            "recovery": tk.BooleanVar(value=notifications.get("recovery", True)),
            "failure": tk.BooleanVar(value=notifications.get("failure", True)),
            "device": tk.BooleanVar(value=notifications.get("device", True)),
        }
        ttk.Checkbutton(card, text="保存网络稳定性历史", variable=var_history,
                        style="Checkmark.TCheckbutton").pack(anchor="w")

        report = ttk.Frame(card, style="Surface.TFrame", padding=(14, 12))
        report.pack(fill="x", pady=(10, 14))
        report_label = ttk.Label(report, text="", style="Surface.TLabel", justify="left", wraplength=535)
        report_label.pack(anchor="w")

        def refresh_report():
            data = core.summarize_network_history(7)
            c = data["counts"]
            stable = ("%.0f%%" % data["stable_percent"] if data["stable_percent"] is not None else "暂无")
            report_label.configure(text=(
                "最近 7 天网络概况\n%s\n\n"
                "记录 %d 条 · 正常比例 %s · 掉线 %d 次 · 自动恢复 %d 次 · "
                "恢复失败 %d 次 · VPN 异常 %d 次" % (
                    data["summary"], data["events"], stable, c["disconnect"], c["recovery"],
                    c["failure"], c["vpn_issue"])))

        refresh_report()
        ttk.Label(card, text="系统通知", style="Section.TLabel").pack(anchor="w")
        master_notify = ttk.Checkbutton(
            card, text="允许校园网连接管家发送通知", variable=var_notify,
            style="Checkmark.TCheckbutton")
        master_notify.pack(
            anchor="w", pady=(6, 3))
        categories = ttk.Frame(card, style="Inner.TFrame")
        categories.pack(fill="x")
        category_buttons = []
        for index, (key, text) in enumerate((
                ("disconnect", "检测到掉线"), ("recovery", "网络恢复"),
                ("failure", "自动恢复失败"), ("device", "新设备请求共享"))):
            child = ttk.Checkbutton(categories, text=text, variable=category_vars[key],
                                    style="Checkmark.TCheckbutton")
            child.grid(
                row=index // 2, column=index % 2, sticky="w", padx=(0, 30), pady=2)
            category_buttons.append(child)

        def sync_notification_children():
            enabled = bool(var_notify.get())
            if not enabled:
                for value in category_vars.values():
                    value.set(False)
            for child in category_buttons:
                child.configure(state="normal" if enabled else "disabled")

        master_notify.configure(command=sync_notification_children)
        sync_notification_children()

        def save_preferences():
            self.cfg["history_enabled"] = bool(var_history.get())
            self.cfg["notifications"] = core.normalized_notification_settings(
                bool(var_notify.get()), {key: bool(value.get()) for key, value in category_vars.items()})
            core.save_config(self.cfg)
            self._log("偏好设置已保存：网络历史%s，系统通知%s" % (
                "开启" if var_history.get() else "关闭", "开启" if var_notify.get() else "关闭"))
            win.destroy()

        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.pack(fill="x", side="bottom", pady=(14, 0))
        ttk.Button(actions, text="刷新网络报告", style="Gray.TButton", command=refresh_report).pack(side="left")
        ttk.Button(actions, text="测试通知", style="Gray.TButton",
                   command=lambda: core.send_system_notification("通知设置工作正常")).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="保存设置", style="Accent.TButton", command=save_preferences).pack(side="right")

    # ---------- 系统托盘 ----------
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

    def _log(self, msg):
        line = core.log(msg)
        self.log_q.put(line)

    # ---------- 状态 ----------
    def set_guard(self, running):
        self._guard_want = running
        self.lbl_guard.configure(text="守护: 运行中" if running else "守护: 未运行")
        self.dot_guard.configure(fg=GREEN if running else MUTED)
        self.btn_guard.configure(text="停止守护" if running else "启动守护",
                                 style="Danger.TButton" if running else "Green.TButton")

    def set_net(self, paths, authed, last_check):
        if last_check:
            self.lbl_last.configure(text="上次检测: %s" % last_check)
        vpn = paths.get("vpn", False)
        current = paths.get("current", False)
        physical = paths.get("physical", current)
        if authed and physical and current:
            self.dot_net.configure(fg=GREEN)
            self.lbl_net.configure(text="网络: VPN 与校园网在线" if vpn else "网络: 在线正常")
        elif authed and physical and vpn:
            self.dot_net.configure(fg=YELLOW)
            self.lbl_net.configure(text="网络: 校园网在线 (VPN异常)")
        elif authed:
            self.dot_net.configure(fg=YELLOW)
            self.lbl_net.configure(text="网络: 校园网出口异常")
        elif vpn and current:
            self.dot_net.configure(fg=YELLOW)
            self.lbl_net.configure(text="网络: VPN在线 (校园认证掉线)")
        else:
            self.dot_net.configure(fg=RED)
            self.lbl_net.configure(text="网络: 已掉线")

    def set_env(self, mode, ssid, gw, profile_name, in_campus):
        if in_campus is None:
            return
        conn = (" (" + ssid + ")" if ssid else (" (有线/网关 %s)" % gw if gw else ""))
        if in_campus:
            self.dot_env.configure(fg=GREEN)
            extra = " → 档案「%s」" % profile_name if profile_name else " (未匹配档案)"
            self.lbl_env.configure(text="环境: 校园网%s%s" % (conn, extra))
        else:
            self.dot_env.configure(fg=MUTED)
            self.lbl_env.configure(text="环境: 非校园网%s (守护休眠)" % conn)

    def _on_log(self, line):
        self.log_q.put(line)

    def _on_status(self, paths, authed, last_check):
        self.after(0, self.set_net, paths, authed, last_check)

    def _on_env(self, mode, ssid, gw, profile_name, in_campus):
        self.after(0, self.set_env, mode, ssid, gw, profile_name, in_campus)

    # ---------- 动作 ----------
    def start_daemon(self, silent=False):
        if self.daemon and self.daemon.is_alive():
            return
        if not core.acquire_lock():
            messagebox.showwarning("已有实例", "检测到已有守护实例在运行。\n请先关闭它，或重启电脑后重试。")
            return
        self.cfg = core.load_config()
        if not any(p.get("username") and p.get("password") for p in self.cfg.get("profiles", [])):
            messagebox.showwarning("未配置", "请先在档案中填写账号密码并保存")
            core.release_lock()
            return
        self.daemon = core.KeepAliveDaemon(self.cfg, on_log=self._on_log, on_status=self._on_status,
                                           on_env=self._on_env, on_alert=self._on_alert)
        self.daemon.start()
        self.set_guard(True)
        if not silent:
            self._log("守护启动 (GUI)")

    def toggle_daemon(self):
        """单按钮切换守护状态。"""
        if self.daemon and self.daemon.is_alive():
            self.stop_daemon()
        else:
            self.start_daemon()

    def export_diag(self):
        """诊断导出: 先选择保存位置，再生成网络状态/脱敏档案/日志。"""
        import datetime
        default_name = "校园网连接管家诊断_%s.txt" % datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = filedialog.asksaveasfilename(
            title="保存诊断报告",
            defaultextension=".txt",
            initialfile=default_name,
            filetypes=[("文本报告", "*.txt"), ("所有文件", "*.*")])
        if not fname:
            return

        def _do():
            try:
                text = core.collect_diagnostics()
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(text)
                try:
                    self.clipboard_clear()
                    self.clipboard_append(text)
                except Exception:
                    pass
                def done():
                    self._log("诊断报告已保存: %s" % fname)
                    messagebox.showinfo("诊断完成",
                                        "诊断报告已保存到：\n%s\n\n内容也已复制到剪贴板，可直接粘贴发给技术人员。" % fname)
                self.after(0, done)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("诊断失败", str(e)))
        threading.Thread(target=_do, daemon=True).start()

    def _on_alert(self, text, category="failure"):
        """守护告警 → 托盘通知 (守护线程调用, 线程安全)"""
        def _notify():
            if not core.notification_enabled(self.cfg, category):
                return
            if core.send_system_notification(text):
                return
            if HAS_TRAY and getattr(self, "_tray", None):
                try:
                    self._tray.notify(text, "校园网连接管家")
                    return
                except Exception:
                    pass
            self._log("通知: " + text)
        try:
            self.after(0, _notify)
        except Exception:
            pass

    def _watchdog(self):
        """守护看门狗: 守护线程意外退出时自动重启"""
        try:
            want = getattr(self, "_guard_want", False)
            if want and self.daemon and not self.daemon.is_alive():
                self._log("检测到守护异常退出, 自动重启...")
                self.daemon = None
                self.set_guard(False)
                try:
                    core.release_lock()
                except Exception:
                    pass
                self.start_daemon(silent=True)
        except Exception:
            pass
        self.after(3000, self._watchdog)

    def stop_daemon(self):
        if self.daemon and self.daemon.is_alive():
            self.daemon.stop()
            self.daemon = None
        core.release_lock()
        self.set_guard(False)
        self.dot_net.configure(fg=MUTED)
        self.lbl_net.configure(text="网络: 已停止检测")

    def check_now(self):
        threading.Thread(target=self._do_check, daemon=True).start()

    def detect_auth(self):
        known = [self.cmb_auth.get().strip(), core.DEFAULT_AUTH_URL]
        known.extend(self.cfg.get("auth_history") or [])
        known.extend(p.get("auth_url", "") for p in self.cfg.get("profiles", []))
        self.btn_detect.configure(text="探测中...", state="disabled")
        threading.Thread(target=self._do_detect, args=(known,), daemon=True).start()

    def _do_detect(self, known_urls):
        try:
            report = core.discover_auth_servers(known_urls)
        except Exception as e:
            report = {"candidates": [], "online": False}
            err = str(e)
            self.after(0, lambda: self._log("探测异常: %s" % err))
        def done():
            self.btn_detect.configure(text="探测", state="normal")
            candidates = report.get("candidates") or []
            if candidates:
                urls = [item["url"] for item in candidates]
                existing = list(self.cmb_auth.cget("values"))
                merged = list(dict.fromkeys(urls + existing))[:15]
                self.cmb_auth.configure(values=merged)
                self.cmb_auth.set(urls[0])
                history = list(dict.fromkeys(urls + (self.cfg.get("auth_history") or [])))[:15]
                self.cfg["auth_history"] = history
                core.save_config(self.cfg)
                for item in candidates:
                    self._log("发现认证服务器: %s（%s，可信度 %d）" % (
                        item["url"], item["source"], item["confidence"]))
                if len(candidates) > 1:
                    messagebox.showinfo(
                        "发现多个认证服务器",
                        "共发现 %d 个候选地址，已选择可信度最高的一项。\n\n%s\n\n"
                        "其他地址已加入认证服务器下拉框，可以直接切换。" % (
                            len(candidates), "\n".join("• %s（%s）" % (i["url"], i["source"])
                                                       for i in candidates)))
                elif report.get("online"):
                    messagebox.showinfo(
                        "探测完成",
                        "当前已经联网，但仍通过认证页特征验证到：\n%s\n\n"
                        "因此不需要先断开校园网认证。" % urls[0])
            else:
                messagebox.showwarning(
                    "未探测到认证服务器",
                    ("多个 HTTP/204 探针均显示当前网络已经联网，但没有识别出认证页特征。\n\n"
                     "请保留已有地址，或在未认证状态下重新探测。"
                     if report.get("online") else
                     "没有从多组 HTTP/204 探针、重定向、认证页特征和历史地址中发现认证服务器。\n\n"
                     "请确认已连接校园网，或手动输入一次真实认证页地址。"))
        self.after(0, done)

    def show_wizard(self):
        """新手向导: 分步引导, 无计算机基础也能用"""
        import webbrowser
        win = tk.Toplevel(self)
        win.title("新手向导")
        win.configure(bg=BG)
        win.geometry("640x600")
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(20, 18))
        card.pack(fill="both", expand=True, padx=16, pady=14)
        title = ttk.Label(card, text="", style="Card.TLabel", font=("Microsoft YaHei UI", 15, "bold"))
        title.pack(anchor="w")
        body = tk.Text(card, bg="#16161f", fg="#d5d5e5", font=("Microsoft YaHei UI", 11),
                       relief="flat", wrap="word", padx=14, pady=12, height=14)
        body.pack(fill="both", expand=True, pady=(10, 10))
        btns = ttk.Frame(card, style="Card.TFrame")
        btns.pack(fill="x")
        btn_prev = ttk.Button(btns, text="← 上一步", style="Gray.TButton")
        btn_prev.pack(side="left")
        btn_act = ttk.Button(btns, text="下一步 →", style="Accent.TButton")
        btn_act.pack(side="right")
        btn_act2 = ttk.Button(btns, text="", style="Green.TButton")
        btn_act2.pack(side="right", padx=(0, 8))
        btn_act3 = ttk.Button(btns, text="", style="Gray.TButton")
        btn_act3.pack(side="right", padx=(0, 8))

        state = {"step": 0, "brand": None, "gw": None, "guide": "", "plan": None}

        def set_body(text):
            body.configure(state="normal")
            body.delete("1.0", "end")
            body.insert("1.0", text)
            body.configure(state="disabled")

        def show_plan_choice():
            title.configure(text="选择你的上网方式")
            set_body("没有电脑基础也没关系，跟着步骤点就行。\n\n"
                     "【方式 A】电脑直连校园网（最简单）\n"
                     "    电脑连校园网 WiFi，其他设备连电脑开的热点\n"
                     "    适合：只有几台设备、不想碰路由器\n\n"
                     "【方式 B】路由器中继校园网（全屋上网）\n"
                     "    路由器连校园网，手机/平板/电脑都连路由器\n"
                     "    适合：设备多、要覆盖全屋\n\n"
                     "【方式 C】隧道共享（手机手动代理）\n"
                     "    手机通过电脑的 8080 代理访问网络\n"
                     "    适合：手机连着同一 WiFi 但无法通过校园网认证\n\n"
                     "点下面按钮选择：")
            btn_prev.pack_forget()
            btn_act.configure(text="A：电脑直连", command=enter_plan_a, state="normal")
            btn_act2.configure(text="B：路由器中继", command=enter_plan_b, state="normal")
            btn_act2.pack(side="right", padx=(0, 8))
            btn_act3.configure(text="C：隧道共享", command=enter_plan_c, state="normal")
            btn_act3.pack(side="right", padx=(0, 8))

        def enter_plan_a():
            state["plan"] = "A"
            btn_act3.pack_forget()
            title.configure(text="方式 A：电脑直连校园网")
            set_body("第 1 步：让电脑连接校园网 WiFi\n"
                     "  点下面「打开 WiFi 设置」，选择 LIDA-UNIVERSITY 并连接\n\n"
                     "第 2 步：回到主窗口，在「连接档案」里填好\n"
                     "  账号、密码、运营商 → 点「💾 保存档案」\n\n"
                     "第 3 步：点「▶ 启动守护」\n"
                     "  完成后看顶部状态灯：\n"
                     "  · 守护 ● 绿色 = 运行中\n"
                     "  · 网络 ● 绿色 = 在线正常（掉线会自动重登）\n\n"
                     "第 4 步（可选）：让手机也用网\n"
                     "  点下面「打开移动热点设置」→ 打开开关 → 手机连电脑热点")
            btn_act.configure(text="打开 WiFi 设置", command=core.open_wifi_settings)
            btn_act2.configure(text="打开移动热点", command=core.open_hotspot_settings)
            btn_prev.pack(side="left")
            btn_prev.configure(command=lambda: show_plan_choice())

        def enter_plan_b():
            state["plan"] = "B"
            btn_act3.pack_forget()
            title.configure(text="方式 B：路由器中继校园网")
            set_body("正在检测你的路由器...\n\n（请确认电脑当前连接的是【路由器】的 WiFi）")
            btn_act.configure(text="重新检测", command=enter_plan_b)
            btn_act2.configure(text="打开管理页", state="disabled")
            btn_prev.pack(side="left")
            btn_prev.configure(command=lambda: show_plan_choice())

            def detect():
                brand, gw, guide = core.router_guide()
                state["brand"], state["gw"], state["guide"] = brand, gw, guide
                head = "检测到路由器：%s\n管理地址：http://%s\n\n" % (brand or "未知品牌", gw or "无法获取")
                if not gw:
                    tail = "没有检测到路由器网关。\n请先连接【路由器】的 WiFi（不是校园网直连），再点「重新检测」。"
                else:
                    tail = "👇 照着下面的步骤设置中继：\n\n" + guide + \
                           "\n\n完成后：电脑连回这个路由器的 WiFi，软件会自动帮路由器保活（被踢自动重登）。"
                set_body(head + tail)
                btn_act2.configure(state="normal" if gw else "disabled",
                                   command=lambda: webbrowser.open("http://%s" % gw))
            threading.Thread(target=detect, daemon=True).start()

        def enter_plan_c():
            state["plan"] = "C"
            btn_act3.pack_forget()
            title.configure(text="方式 C：隧道共享上网")
            ips = shared_proxy.get_lan_ips()
            server = ips[0] if ips else "电脑的局域网 IP"
            running = bool(self.proxy and self.proxy.running)
            status = "已开启 ✅" if running else "尚未开启"
            set_body("隧道状态：%s\n服务器：%s\n端口：8080\n\n"
                     "第 1 步：先让电脑连接校园网并确认电脑能正常上网\n\n"
                     "第 2 步：手机与电脑连接同一个路由器/WiFi\n\n"
                     "第 3 步：点下面「开启隧道」\n\n"
                     "第 4 步：手机打开当前 WiFi 的详细设置\n"
                     "  → 配置代理/HTTP 代理 → 手动\n"
                     "  → 服务器填写 %s\n"
                     "  → 端口填写 8080 → 保存\n\n"
                     "第 5 步：手机首次访问网页时，电脑会弹出设备授权请求\n"
                     "  → 确认 IP 后点「允许」，以后会自动记住\n\n"
                     "使用期间电脑和连接管家必须保持运行。公共 WiFi 若开启了客户端隔离，"
                     "手机可能无法访问电脑，此时请改用自己的路由器或电脑热点。"
                     % (status, server, server))

            def enable_tunnel():
                if not (self.proxy and self.proxy.running):
                    self.toggle_share()
                enter_plan_c()

            btn_act.configure(text="隧道已开启" if running else "开启隧道",
                              command=enable_tunnel,
                              state="disabled" if running else "normal")
            btn_act2.configure(text="完成", command=win.destroy, state="normal")
            btn_act2.pack(side="right", padx=(0, 8))
            btn_prev.pack(side="left")
            btn_prev.configure(command=show_plan_choice)

        show_plan_choice()
        win.protocol("WM_DELETE_WINDOW", win.destroy)

    def show_help(self):
        gw = core.get_gateway()
        help_win = tk.Toplevel(self)
        help_win.title("使用帮助")
        help_win.configure(bg=BG)
        help_win.geometry("560x560")
        help_win.transient(self)

        txt = tk.Text(help_win, bg="#16161f", fg="#d5d5e5", font=("Microsoft YaHei UI", 10),
                      relief="flat", wrap="word", padx=16, pady=12)
        txt.pack(fill="both", expand=True, padx=12, pady=12)

        gw_tip = "当前网络网关: %s（连上路由器 WiFi 后，在浏览器打开它即管理页）" % gw if gw else "当前未检测到网关（请确认已连接网络）"
        content = """📖 校园网连接管家 · 快速上手

▎方式一：不用路由器（最简单）
  1. 电脑连接校园网 WiFi（如 LIDA-UNIVERSITY）
  2. 打开本软件，填好账号/密码/运营商 → 保存档案 → 启动守护
  3. 手机可连电脑开的「移动热点」上网
  （电脑直连时，本软件会自动检测、掉线自动重登）

▎方式二：用路由器中继校园网（全屋多设备上网，推荐）
  · 原理：路由器中继校园网（占 1 个账号名额），
    手机/平板/其他设备都连路由器的 WiFi —— 不占账号名额，
    一个账号就能带全屋设备上网
  · 配置路由器中继：
    1. 确认电脑/手机连接的是【路由器】的 WiFi
    2. 浏览器打开路由器管理页：
     """ + gw_tip + """
     或看路由器底部标签的管理地址
     （常见: 192.168.1.1 / 192.168.0.1 / tplogin.cn / miwifi.com）
  3. 登录管理页（账号密码在路由器底部标签，常见 admin/admin）
  4. 找到「无线中继 / WISP / 桥接」功能 → 扫描并连接校园网 WiFi
     （如 LIDA-UNIVERSITY），按提示输入校园网账号完成中继
  5. 修改 WiFi 密码：管理页 → 无线设置 → 修改 → 保存
  6. 电脑连回【路由器】的 WiFi → 打开本软件填校园网账号 → 启动守护

  ⭐ 重要：电脑连【路由器】时，软件会自动替【路由器】保活——
     路由器被校园网踢下线后，电脑上的软件会自动帮它重新登录，
     不用再手动断电重启路由器！

▎方式三：隧道共享（手机手动代理）
  1. 先确认电脑已经连接校园网并能正常上网
  2. 手机与电脑连接同一个路由器/WiFi
  3. 主界面点「🔗 隧道」，记下弹窗中的电脑 IP 和端口 8080
  4. 手机当前 WiFi → 配置代理/HTTP 代理 → 手动
  5. 服务器填电脑 IP，端口填 8080，然后保存
  6. 手机首次访问时，在电脑弹出的设备授权窗口点「允许」
  · 使用期间电脑和本软件必须保持运行
  · 公共 WiFi 开启客户端隔离时，请改用自己的路由器或电脑热点

▎打不开路由器管理页？
  · 确认电脑连的是【路由器】的 WiFi，不是校园网直连
  · 换个浏览器试试（Edge / Chrome）
  · 手机连路由器 WiFi 后用手机浏览器打开管理地址

▎换 WiFi / 换账号？
  · 本软件支持【多档案】：每个 WiFi（SSID）一套配置，自动匹配
  · 点「＋ 新建」添加档案，绑定对应 WiFi 名即可
  · SSID 留空 = 默认档案（任意网络兜底）

▎检测间隔？
  · 建议 1800 秒（30 分钟）：掉线后最多 30 分钟自动重登
  · 想更快恢复可调小（如 300 秒 = 5 分钟），检测不闪屏

▎常见问题
  · 非校园网环境（家里/热点）→ 守护自动休眠，不乱登录
  · 一个校园网账号限 2 台设备：手机等走路由器（不占名额）
  · 路由器被踢下线 → 重启路由器，或在校园网自助系统注销
"""
        txt.insert("1.0", content)
        txt.configure(state="disabled")

    def _do_check(self):
        self._log("[%s] 手动检测..." % core.now_str())
        mode, ssid = core.get_connection_mode()
        gw = core.get_gateway()
        profile = core.match_profile(self.cfg, ssid, gw)
        auth_url = profile.get("auth_url", core.DEFAULT_AUTH_URL) if profile else core.DEFAULT_AUTH_URL
        in_campus = core.auth_reachable(auth_url)
        self._on_env(mode, ssid, gw, profile["name"] if profile else None, in_campus)
        if not in_campus:
            self._log("结果: 非校园网环境, 不进行登录")
            return
        if profile is None:
            self._log("结果: 校园网环境但未配置档案")
            return
        authed = core.check_auth(auth_url)
        paths = core.check_network_paths()
        campus_internet = paths["physical"] if paths["vpn"] and core.IS_MACOS else paths["current"]
        self._on_status(paths, authed, core.now_str())
        if authed and campus_internet:
            if paths["vpn"] and not paths["current"]:
                self._log("结果: 校园网在线，VPN/系统路径异常")
            elif paths["vpn"]:
                self._log("结果: VPN 与校园网均在线")
            else:
                self._log("结果: 在线正常")
        elif authed:
            self._log("结果: 校园网认证在线，但物理出口异常")
        else:
            self._log("结果: 未登录/掉线")

    def _refresh_env(self):
        def work():
            mode, ssid = core.get_connection_mode()
            gw = core.get_gateway()
            profile = core.match_profile(self.cfg, ssid, gw)
            auth_url = profile.get("auth_url", core.DEFAULT_AUTH_URL) if profile else core.DEFAULT_AUTH_URL
            in_campus = core.auth_reachable(auth_url)
            self._on_env(mode, ssid, gw, profile["name"] if profile else None, in_campus)
        threading.Thread(target=work, daemon=True).start()

    def _auto_start(self):
        try:
            self.cfg = core.load_config()
            if not any(p.get("username") and p.get("password") for p in self.cfg.get("profiles", [])):
                self.after(800, self.show_wizard)
                return
            if core.acquire_lock():
                core.release_lock()
                self.start_daemon(silent=True)
        except Exception:
            pass


if __name__ == "__main__":
    App().mainloop()
