# -*- coding: utf-8 -*-
"""v4.0.0 独立窗口版: 功能窗口管理 Mixin。

每个功能拥有自己的独立窗口(单实例, 重复点击仅置前), 主窗口只保留
状态条 + 守护开关 + 功能宫格, 不再把档案表单/日志/工具挤在一个窗口。
"""
import queue  # noqa: F401
import threading  # noqa: F401
import tkinter as tk
from tkinter import ttk, messagebox  # noqa: F401

import keepalive_core as core  # noqa: F401
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


class FeatureWindowsMixin:
    """窗口注册表 + 各功能独立窗口的构建器。"""

    # ---------- 窗口注册表 ----------

    def _fwin(self, name):
        """返回已打开且仍存在的功能窗口, 否则 None; 已打开时顺带置前。"""
        w = getattr(self, "_fwin_map", {}).get(name)
        if w is not None:
            try:
                if w.winfo_exists():
                    w.deiconify()
                    w.lift()
                    w.focus_force()
                    return w
            except Exception:
                pass
        return None

    def _fwin_open(self, name, builder, on_close=None):
        """单实例打开功能窗口。builder() 应返回创建的 Toplevel。"""
        if self._fwin(name):
            return None
        win = builder()
        if win is None:
            return None
        self._fwin_map[name] = win

        def _closed(_w=win, _n=name, _cb=on_close):
            try:
                _w.destroy()
            except Exception:
                pass
            try:
                self._fwin_map.pop(_n, None)
            except Exception:
                pass
            if _cb:
                try:
                    _cb()
                except Exception:
                    pass
        try:
            win.protocol("WM_DELETE_WINDOW", _closed)
        except Exception:
            pass
        return win

    def _fwin_open_legacy(self, name, builder):
        """对"内部自行创建 Toplevel 且不返回句柄"的既有功能(builder() 无返回值)
        做单实例包装: 调用后从根窗口子级里取新建的 Toplevel 登记。"""
        if self._fwin(name):
            return
        try:
            before = {id(w) for w in self.winfo_children()}
            builder()
            after = [w for w in self.winfo_children() if id(w) not in before
                     and isinstance(w, tk.Toplevel)]
            if after:
                win = after[-1]
                self._fwin_map[name] = win

                def _closed(_w=win, _n=name):
                    try:
                        _w.destroy()
                    except Exception:
                        pass
                    self._fwin_map.pop(_n, None)
                try:
                    win.protocol("WM_DELETE_WINDOW", _closed)
                except Exception:
                    pass
        except Exception:
            pass

    def _init_fwin_map(self):
        if not hasattr(self, "_fwin_map"):
            self._fwin_map = {}

    # ---------- 独立窗口: 连接档案 ----------

    def open_profile_window(self):
        """连接档案管理(独立窗口): 档案下拉 + 完整编辑表单。"""
        if self._fwin("profile"):
            return
        self._init_fwin_map()
        win = tk.Toplevel(self)
        win.title("连接档案管理")
        win.configure(bg=BG)
        win.geometry("760x600")
        win.minsize(700, 560)
        win.transient(self)
        card = ttk.Frame(win, style="Card.TFrame", padding=(18, 14))
        card.pack(fill="both", expand=True, padx=14, pady=14)

        ttk.Label(card, text="连接档案", style="DialogTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="每个网络(WiFi/网关)一套账号, 自动匹配; 密码存钥匙串",
                  style="Muted.TLabel").grid(row=1, column=0, columnspan=2, sticky="w", pady=(2, 8))

        prof_row = ttk.Frame(card, style="Inner.TFrame")
        prof_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        prof_row.columnconfigure(0, weight=1)
        self.cmb_profile = ttk.Combobox(prof_row, state="readonly")
        self.cmb_profile.grid(row=0, column=0, sticky="ew")
        self.cmb_profile.bind("<<ComboboxSelected>>", self._on_profile_selected)
        ttk.Button(prof_row, text="新建", style="Gray.TButton",
                   command=self.new_profile).grid(row=0, column=1, padx=(8, 0))
        ttk.Button(prof_row, text="删除", style="Quiet.TButton",
                   command=self.del_profile).grid(row=0, column=2, padx=(4, 0))

        form = ttk.Frame(card, style="Inner.TFrame")
        form.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(12, 0))
        card.rowconfigure(3, weight=1)
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        def _fl(row, col, text):
            ttk.Label(form, text=text, style="Field.TLabel").grid(
                row=row, column=col, sticky="w", padx=(0 if col == 0 else 12, 0), pady=(4, 2))

        def _fw(widget, row, col):
            widget.grid(row=row, column=col, sticky="ew", pady=(0, 5),
                        padx=(0 if col == 0 else 12, 12 if col == 0 else 0))

        _fl(0, 0, "档案类型")
        self.cmb_ptype = ttk.Combobox(
            form, state="readonly", values=["校园网认证（登录保活）", "普通WiFi/热点（只检测断网）"])
        _fw(self.cmb_ptype, 1, 0)
        self.cmb_ptype.bind("<<ComboboxSelected>>", self._on_ptype_change)
        self.lbl_ptype_hint = ttk.Label(form, text="此档案会登录校园网并保活，认证服务器必填。",
                                        style="Muted.TLabel", wraplength=320)
        self.lbl_ptype_hint.grid(row=1, column=1, sticky="w", padx=(12, 0), pady=(0, 5))

        _fl(2, 0, "档案名称")
        _fl(2, 1, "运营商")
        self.ent_name = ttk.Entry(form)
        _fw(self.ent_name, 3, 0)
        self.cmb_type = ttk.Combobox(form, state="readonly", values=[
            "移动互联网访问 (cmcc)", "联通互联网访问 (unicom)", "教师登录 (teacher)"])
        _fw(self.cmb_type, 3, 1)

        _fl(4, 0, "校园网账号")
        _fl(4, 1, "密码（macOS 钥匙串）" if core.IS_MACOS else "密码")
        self.ent_user = ttk.Entry(form)
        _fw(self.ent_user, 5, 0)
        pwf = ttk.Frame(form, style="Inner.TFrame")
        pwf.grid(row=5, column=1, sticky="ew", padx=(12, 12), pady=(0, 5))
        pwf.columnconfigure(0, weight=1)
        self.ent_pass = ttk.Entry(pwf, show="●")
        self.ent_pass.grid(row=0, column=0, sticky="ew")
        ttk.Button(pwf, text="显示", style="Quiet.TButton",
                   command=self._toggle_pass).grid(row=0, column=1, padx=(5, 0))

        _fl(6, 0, "绑定 WiFi（SSID，可留空）")
        _fl(6, 1, "绑定网关（有线，可留空）")
        self.ent_ssid = ttk.Entry(form)
        _fw(self.ent_ssid, 7, 0)
        self.ent_gw = ttk.Entry(form)
        _fw(self.ent_gw, 7, 1)

        _fl(8, 0, "检测间隔（秒）")
        _fl(8, 1, "认证服务器")
        self.cmb_interval = ttk.Combobox(form, values=["60", "300", "600", "1800", "3600"])
        _fw(self.cmb_interval, 9, 0)
        authf = ttk.Frame(form, style="Inner.TFrame")
        authf.grid(row=9, column=1, sticky="ew", padx=(12, 12), pady=(0, 5))
        authf.columnconfigure(0, weight=1)
        self.cmb_auth = ttk.Combobox(authf)
        self.cmb_auth.grid(row=0, column=0, sticky="ew")
        self.btn_detect = ttk.Button(authf, text="探测", style="Gray.TButton",
                                     command=self.detect_auth)
        self.btn_detect.grid(row=0, column=1, padx=(6, 0))

        btns = ttk.Frame(card, style="Inner.TFrame")
        btns.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        btns.columnconfigure(0, weight=1)
        btns.columnconfigure(1, weight=1)
        btns.columnconfigure(2, weight=1)
        btns.columnconfigure(3, weight=1)
        self.btn_save = ttk.Button(btns, text="保存档案", style="Accent.TButton",
                                   command=self.save_profile)
        self.btn_save.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.btn_check = ttk.Button(btns, text="立即检测", style="Gray.TButton",
                                    command=self.check_now)
        self.btn_check.grid(row=0, column=1, sticky="ew", padx=(4, 4))
        ttk.Button(btns, text="导入配置", style="Gray.TButton",
                   command=self.import_config).grid(row=0, column=2, sticky="ew", padx=(4, 4))
        ttk.Button(btns, text="导出配置", style="Gray.TButton",
                   command=self.export_config).grid(row=0, column=3, sticky="ew", padx=(4, 0))

        def _closed():
            for attr in ("cmb_profile", "ent_name", "ent_user", "ent_pass",
                         "ent_ssid", "ent_gw", "cmb_type", "cmb_ptype",
                         "cmb_interval", "cmb_auth", "btn_detect", "btn_save",
                         "btn_check", "lbl_ptype_hint"):
                if hasattr(self, attr):
                    try:
                        setattr(self, attr, None)
                    except Exception:
                        pass
        self._fwin_open("profile", lambda: (self._refresh_profile_list(),
                                            self._load_form_from_current(), win)[-1],
                        on_close=_closed)

    # ---------- 独立窗口: 运行日志 ----------

    def open_log_window(self):
        if self._fwin("log"):
            return
        self._init_fwin_map()
        win = tk.Toplevel(self)
        win.title("运行日志")
        win.configure(bg=BG)
        win.geometry("860x520")
        win.minsize(600, 360)
        win.transient(self)
        card = ttk.Frame(win, style="Card.TFrame", padding=(14, 10))
        card.pack(fill="both", expand=True, padx=14, pady=14)
        ttk.Label(card, text="运行日志", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="守护与网络事件实时记录（也会写入日志文件，重启不丢失）",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 8))
        body = ttk.Frame(card, style="Inner.TFrame")
        body.pack(fill="both", expand=True)
        self.txt_log = tk.Text(body, bg="#09101c", fg="#b7c4d8", font=("Menlo", 10),
                               relief="flat", wrap="none", state="disabled",
                               insertbackground=FG, selectbackground=ACCENT)
        self.txt_log.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(body, orient="vertical", command=self.txt_log.yview)
        scroll.pack(side="right", fill="y")
        self.txt_log.configure(yscrollcommand=scroll.set)
        self.txt_log.bind("<MouseWheel>", self._scroll_log)
        self._load_existing_log()

        def _closed():
            self.txt_log = None
        self._fwin_open("log", lambda: win, on_close=_closed)

    # ---------- 独立窗口: 热点分享 ----------

    def open_hotspot_window(self):
        """热点分享(独立窗口): 检测当前状态并引导打开系统热点。"""
        if self._fwin("hotspot"):
            return
        self._init_fwin_map()
        win = tk.Toplevel(self)
        win.title("热点分享")
        win.configure(bg=BG)
        win.geometry("560x430")
        win.transient(self)
        card = ttk.Frame(win, style="Card.TFrame", padding=(22, 18))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="热点分享", style="DialogTitle.TLabel").pack(anchor="w")
        state_label = ttk.Label(card, text="", style="Muted.TLabel", wraplength=480,
                                justify="left")
        state_label.pack(anchor="w", pady=(6, 12))

        def refresh():
            on = core.hotspot_on()
            if on:
                state_label.configure(
                    text="✅ 热点已开启\n\n手机/平板连接电脑热点即可上网，只占电脑 1 个校园网名额。\n"
                         "WiFi 名称与密码在「系统设置 → 移动热点/互联网共享」中查看/修改。",
                    foreground="#3fae7f")
            else:
                state_label.configure(
                    text="电脑热点尚未开启。点击下方按钮打开系统热点设置：\n\n"
                         "Windows: 打开开关「与其他设备共享我的 Internet 连接」\n"
                         "macOS: 打开「互联网共享」开关 → Wi-Fi 选项设名称密码\n\n"
                         "开启后回到此窗口点「刷新状态」确认。", foreground=FG)

        refresh()
        btns = ttk.Frame(card, style="Inner.TFrame")
        btns.pack(fill="x", pady=(14, 0))
        ttk.Button(btns, text="打开热点设置", style="Accent.TButton",
                   command=lambda: self._open_hotspot_setting()).pack(side="left")
        ttk.Button(btns, text="刷新状态", style="Gray.TButton",
                   command=refresh).pack(side="left", padx=(8, 0))
        ttk.Label(card, text="原理：所有设备走电脑的网络出口，只占用电脑 1 个名额，"
                             "不受校园网多设备限制。", style="Muted.TLabel",
                  wraplength=480).pack(anchor="w", pady=(14, 0))
        self._fwin_open("hotspot", lambda: win)

    def _open_hotspot_setting(self):
        ok = False
        try:
            ok = bool(core.open_hotspot_settings())
        except Exception:
            ok = False
        if not ok:
            messagebox.showerror(
                "打开失败", "无法自动打开热点设置，请手动到\n"
                "系统设置 → 网络和 Internet/通用 → 移动热点/互联网共享 开启。")

    # ---------- 独立窗口: 网络报告 ----------

    def open_report_window(self):
        if self._fwin("report"):
            return
        self._init_fwin_map()
        win = tk.Toplevel(self)
        win.title("网络报告")
        win.configure(bg=BG)
        win.geometry("660x560")
        win.minsize(600, 460)
        win.transient(self)
        card = ttk.Frame(win, style="Card.TFrame", padding=(22, 18))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="网络报告", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="只记录连接状态，不记录浏览内容、账号或密码。需先在偏好设置里开启「保存网络稳定性历史」。",
                  style="Muted.TLabel", wraplength=560).pack(anchor="w", pady=(3, 12))
        report_label = ttk.Label(card, text="", style="Card.TLabel", justify="left",
                                 wraplength=580)
        report_label.pack(fill="both", expand=True, anchor="nw")

        def refresh_report():
            data = core.summarize_network_history(7)
            c = data["counts"]
            stable = ("%.0f%%" % data["stable_percent"] if data["stable_percent"] is not None
                      else "暂无")
            text = (
                "最近 7 天网络概况\n%s\n\n"
                "记录 %d 条 · 正常比例 %s · 掉线 %d 次 · 自动恢复 %d 次 · "
                "恢复失败 %d 次 · VPN 异常 %d 次" % (
                    data["summary"], data["events"], stable, c["disconnect"], c["recovery"],
                    c["failure"], c["vpn_issue"]))
            outages = core.analyze_outage_timeline(7)
            if outages:
                text += "\n\n—— 断网时间线（最近 7 天）——\n"
                for idx, o in enumerate(outages, 1):
                    text += "%d. %s 断网 → %s 恢复（持续 %s）\n" % (
                        idx, o["start"], o["end"], o["duration"])
                text += ("\n（提示：若断网集中在固定时段，多为路由器过热/链路问题；"
                         "持续多次请检查路由器散热或考虑重启）")
            report_label.configure(text=text)

        refresh_report()
        btns = ttk.Frame(card, style="Inner.TFrame")
        btns.pack(fill="x", side="bottom", pady=(14, 0))
        ttk.Button(btns, text="刷新报告", style="Gray.TButton",
                   command=refresh_report).pack(side="left")
        ttk.Button(btns, text="导出诊断", style="Gray.TButton",
                   command=self.export_diag).pack(side="left", padx=(8, 0))
        self._fwin_open("report", lambda: win)

    # ---------- 独立窗口: 软件更新 ----------

    def open_update_window(self):
        if self._fwin("update"):
            return
        self._init_fwin_map()
        win = tk.Toplevel(self)
        win.title("软件更新")
        win.configure(bg=BG)
        win.geometry("560x300")
        win.transient(self)
        card = ttk.Frame(win, style="Card.TFrame", padding=(22, 18))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="软件更新", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="当前版本 v%s（%s）" % (core.APP_VERSION,
                                                     "macOS" if core.IS_MACOS else "Windows"),
                  style="Muted.TLabel").pack(anchor="w", pady=(8, 4))
        upd_line = ttk.Frame(card, style="Inner.TFrame")
        upd_line.pack(fill="x", pady=(6, 0))
        self._upd_line_frame = upd_line
        self._lbl_update = ttk.Label(upd_line, text="", style="Card.TLabel")
        self._lbl_update.pack(side="left")
        ttk.Button(upd_line, text="检查更新", style="Accent.TButton",
                   command=self._check_update_now).pack(side="right")
        ttk.Label(card, text="点击「检查更新」联网检测 GitHub 最新版本；发现新版本后点「立即更新」自动下载替换重启。",
                  style="Muted.TLabel", wraplength=520).pack(anchor="w", pady=(10, 0))

        def _closed():
            self._lbl_update = None
            self._upd_line_frame = None
            self._btn_update_now = None
            self._update_info = None
        self._fwin_open("update", lambda: win, on_close=_closed)
