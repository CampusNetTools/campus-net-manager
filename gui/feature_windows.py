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
        """连接档案管理(独立窗口): 档案下拉 + 按类型动态表单。
        - 校园网档案: 账号/密码/运营商/认证服务器/SSID/网关/检测间隔
        - 普通WiFi档案: 仅档案名 + 绑定WiFi或网关 + 检测间隔(其他字段不存在, 不变灰)
        切换档案类型会重建字段区, 不会留"变灰禁用"控件。
        """
        if self._fwin("profile"):
            return
        self._init_fwin_map()
        win = tk.Toplevel(self)
        win.title("连接档案管理")
        win.configure(bg=BG)
        win.geometry("780x620")
        win.minsize(700, 560)
        win.transient(self)
        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 22))
        card.pack(fill="both", expand=True, padx=18, pady=18)

        ttk.Label(card, text="连接档案", style="DialogTitle.TLabel").grid(
            row=0, column=0, columnspan=2, sticky="w")
        ttk.Label(card, text="按类型匹配网络：校园网=登录保活；普通WiFi/热点=只检测断网不登录",
                  style="Muted.TLabel", wraplength=700).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(4, 10))

        prof_row = ttk.Frame(card, style="Inner.TFrame")
        prof_row.grid(row=2, column=0, columnspan=2, sticky="ew")
        prof_row.columnconfigure(0, weight=1)
        self.cmb_profile = ttk.Combobox(prof_row, state="readonly")
        self.cmb_profile.grid(row=0, column=0, sticky="ew")
        self.cmb_profile.bind("<<ComboboxSelected>>", self._on_profile_selected)
        ttk.Button(prof_row, text="新建", style="Gray.TButton",
                   command=self.new_profile).grid(row=0, column=1, padx=(12, 0))
        ttk.Button(prof_row, text="删除", style="Quiet.TButton",
                   command=self.del_profile).grid(row=0, column=2, padx=(8, 0))

        # 类型选择器
        type_row = ttk.Frame(card, style="Inner.TFrame")
        type_row.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(16, 6))
        ttk.Label(type_row, text="档案类型", style="Field.TLabel").pack(side="left")
        self.cmb_ptype = ttk.Combobox(
            type_row, state="readonly", width=32,
            values=["校园网认证（登录保活）", "普通WiFi/热点（只检测断网）"])
        self.cmb_ptype.pack(side="left", padx=(16, 0))
        self.cmb_ptype.bind("<<ComboboxSelected>>",
                            lambda e: self._profile_rebuild_form())

        # 类型说明
        self.lbl_ptype_hint = ttk.Label(card, text="", style="Muted.TLabel", wraplength=700)
        self.lbl_ptype_hint.grid(row=4, column=0, columnspan=2, sticky="w", pady=(0, 8))

        # 动态字段容器
        self._profile_form_host = ttk.Frame(card, style="Inner.TFrame")
        self._profile_form_host.grid(row=5, column=0, columnspan=2, sticky="nsew", pady=(6, 0))
        card.rowconfigure(5, weight=1)

        # 底部按钮行
        btns = ttk.Frame(card, style="Inner.TFrame")
        btns.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(16, 0))
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
        ttk.Button(btns, text="导入配置", style="Gray.TButton",
                   command=self.import_config).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(btns, text="导出配置", style="Gray.TButton",
                   command=self.export_config).grid(row=0, column=3, sticky="ew", padx=(6, 0))

        # 关窗时清理所有表单控件引用
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

    def _profile_rebuild_form(self):
        """根据当前 cmb_ptype 重建档案表单字段区。"""
        host = getattr(self, "_profile_form_host", None)
        if host is None:
            return
        try:
            for child in host.winfo_children():
                child.destroy()
        except Exception:
            return
        # 同步类型提示
        wifi = self.cmb_ptype.get() == "普通WiFi/热点（只检测断网）"
        try:
            self.lbl_ptype_hint.configure(
                text="此档案不登录校园网，守护只检测是否断网，断网时通知你。" if wifi
                else "此档案会登录校园网并保活，必须有账号密码与认证服务器。")
        except Exception:
            pass

        # 通用控件清空引用, 重建时按需赋值
        for attr in ("ent_name", "ent_ssid", "ent_gw",
                     "ent_user", "ent_pass", "cmb_type", "cmb_interval",
                     "cmb_auth", "btn_detect"):
            if hasattr(self, attr):
                try:
                    setattr(self, attr, None)
                except Exception:
                    pass

        f = ttk.Frame(host, style="Inner.TFrame")
        f.pack(fill="x")
        f.columnconfigure(0, weight=1)
        f.columnconfigure(1, weight=1)

        def _fl(row, col, text):
            ttk.Label(f, text=text, style="Field.TLabel").grid(
                row=row, column=col, sticky="w", padx=(0 if col == 0 else 16, 0), pady=(10, 4))

        def _fw(widget, row, col):
            widget.grid(row=row, column=col, sticky="ew", pady=(0, 8),
                        padx=(0 if col == 0 else 16, 16 if col == 0 else 0))

        # 档案名(两种类型都需要)
        _fl(0, 0, "档案名称")
        ttk.Label(f, text="", style="Muted.TLabel").grid(row=0, column=1, sticky="w")
        self.ent_name = ttk.Entry(f)
        _fw(self.ent_name, 1, 0)
        ttk.Label(f, text="(易记的名字，例如「寝室华为中继」「家」)",
                  style="Muted.TLabel").grid(row=1, column=1, sticky="w", padx=(16, 0), pady=(0, 8))

        if wifi:
            # ----- 普通WiFi档案: 只显示绑定 + 间隔 -----
            _fl(2, 0, "绑定 WiFi（SSID，留空表示默认）")
            _fl(2, 1, "绑定网关（有线，留空表示默认）")
            self.ent_ssid = ttk.Entry(f)
            _fw(self.ent_ssid, 3, 0)
            self.ent_gw = ttk.Entry(f)
            _fw(self.ent_gw, 3, 1)

            probe_row = ttk.Frame(f, style="Inner.TFrame")
            probe_row.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(2, 8))
            ttk.Button(probe_row, text="自动探查当前网络", style="Gray.TButton",
                       command=self._profile_auto_probe).pack(side="left")
            ttk.Label(probe_row, text="点击后填入电脑当前连接的 WiFi 名 与 网关",
                      style="Muted.TLabel").pack(side="left", padx=(12, 0))

            _fl(5, 0, "检测间隔（秒）")
            ttk.Label(f, text="", style="Muted.TLabel").grid(row=5, column=1, sticky="w")
            self.cmb_interval = ttk.Combobox(f, values=["60", "300", "600", "1800", "3600"],
                                             state="normal", width=24)
            _fw(self.cmb_interval, 6, 0)
            ttk.Label(f, text="断网后多久开始通知(默认 60 秒)",
                      style="Muted.TLabel").grid(row=6, column=1, sticky="w", padx=(16, 0))
        else:
            # ----- 校园网档案: 完整字段 -----
            _fl(2, 0, "运营商")
            ttk.Label(f, text="", style="Muted.TLabel").grid(row=2, column=1, sticky="w")
            self.cmb_type = ttk.Combobox(f, state="readonly", width=24, values=[
                "移动互联网访问 (cmcc)", "联通互联网访问 (unicom)", "教师登录 (teacher)"])
            _fw(self.cmb_type, 3, 0)
            ttk.Label(f, text="校园网按运营商分流，移动=cmcc/联通=unicom",
                      style="Muted.TLabel").grid(row=3, column=1, sticky="w", padx=(16, 0))

            _fl(4, 0, "校园网账号")
            _fl(4, 1, "密码" + ("（macOS 钥匙串）" if core.IS_MACOS else ""))
            self.ent_user = ttk.Entry(f)
            _fw(self.ent_user, 5, 0)
            pwf = ttk.Frame(f, style="Inner.TFrame")
            pwf.grid(row=5, column=1, sticky="ew", padx=(16, 16), pady=(0, 8))
            pwf.columnconfigure(0, weight=1)
            self.ent_pass = ttk.Entry(pwf, show="●")
            self.ent_pass.grid(row=0, column=0, sticky="ew")
            ttk.Button(pwf, text="显示", style="Quiet.TButton",
                       command=self._toggle_pass).grid(row=0, column=1, padx=(5, 0))

            _fl(6, 0, "绑定 WiFi（SSID，可留空）")
            _fl(6, 1, "绑定网关（有线，可留空）")
            self.ent_ssid = ttk.Entry(f)
            _fw(self.ent_ssid, 7, 0)
            self.ent_gw = ttk.Entry(f)
            _fw(self.ent_gw, 7, 1)
            probe_row = ttk.Frame(f, style="Inner.TFrame")
            probe_row.grid(row=8, column=0, columnspan=2, sticky="ew", pady=(2, 10))
            ttk.Button(probe_row, text="自动探查当前网络", style="Gray.TButton",
                       command=self._profile_auto_probe).pack(side="left")
            ttk.Label(probe_row, text="SSID 留空=任意网络(默认); 网关用于有线/中继匹配",
                      style="Muted.TLabel").pack(side="left", padx=(12, 0))

            _fl(9, 0, "检测间隔（秒）")
            _fl(9, 1, "认证服务器")
            self.cmb_interval = ttk.Combobox(f, values=["60", "300", "600", "1800", "3600"],
                                             state="normal", width=24)
            _fw(self.cmb_interval, 10, 0)
            authf = ttk.Frame(f, style="Inner.TFrame")
            authf.grid(row=10, column=1, sticky="ew", padx=(16, 16), pady=(0, 8))
            authf.columnconfigure(0, weight=1)
            self.cmb_auth = ttk.Combobox(authf)
            self.cmb_auth.grid(row=0, column=0, sticky="ew")
            self.btn_detect = ttk.Button(authf, text="探测", style="Gray.TButton",
                                         command=self.detect_auth)
            self.btn_detect.grid(row=0, column=1, padx=(6, 0))

        # 重建后立即用当前档案值填充(填充只走控件已存在的分支, 不再 rebuild)
        self._fill_form_for_current_profile()

    def _profile_auto_probe(self):
        """把电脑当前 SSID + 网关自动填入绑定字段。"""
        try:
            mode, ssid = core.get_connection_mode()
            gw = core.get_gateway() or ""
        except Exception as exc:
            messagebox.showerror("探查失败", str(exc))
            return
        if self.ent_ssid is not None:
            try:
                self.ent_ssid.delete(0, "end")
                if ssid:
                    self.ent_ssid.insert(0, ssid)
            except Exception:
                pass
        if self.ent_gw is not None:
            try:
                self.ent_gw.delete(0, "end")
                if gw:
                    self.ent_gw.insert(0, gw)
            except Exception:
                pass
        self._log("自动探查: SSID=%s 网关=%s" % (ssid or "(无)", gw or "(无)"))

    # ---------- 独立窗口: 热点分享 ----------

    def open_hotspot_window(self):
        """热点分享(独立窗口): 检测状态 + 引导开热点 + 列出连入设备/流量。"""
        if self._fwin("hotspot"):
            return
        self._init_fwin_map()
        win = tk.Toplevel(self)
        win.title("热点分享")
        win.configure(bg=BG)
        win.geometry("720x620")
        win.minsize(660, 560)
        win.transient(self)
        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 22))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(card, text="热点分享", style="DialogTitle.TLabel").pack(anchor="w")
        state_label = ttk.Label(card, text="", style="Muted.TLabel", wraplength=640,
                                justify="left")
        state_label.pack(anchor="w", pady=(8, 12), fill="x")

        # 设备列表 + 流量表
        list_label = ttk.Label(card, text="连入设备 (0)", style="CardSubTitle.TLabel")
        list_label.pack(anchor="w", pady=(12, 6))
        table_frame = ttk.Frame(card, style="Inner.TFrame")
        table_frame.pack(fill="both", expand=True)
        cols = ("ip", "mac", "vendor", "rx", "tx")
        tree = ttk.Treeview(table_frame, columns=cols, show="headings", height=6)
        tree.heading("ip", text="IP")
        tree.heading("mac", text="MAC")
        tree.heading("vendor", text="厂家")
        tree.heading("rx", text="接收")
        tree.heading("tx", text="发送")
        tree.column("ip", width=110, anchor="w")
        tree.column("mac", width=140, anchor="w")
        tree.column("vendor", width=100, anchor="w")
        tree.column("rx", width=90, anchor="e")
        tree.column("tx", width=90, anchor="e")
        tree.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        note_label = ttk.Label(card, text="", style="Muted.TLabel", wraplength=580,
                               justify="left")
        note_label.pack(anchor="w", pady=(6, 0), fill="x")

        def refresh():
            on = core.hotspot_on()
            clients = core.list_hotspot_clients()
            # 已开启判定: Windows 走 192.168.137 网段; macOS 走 list_hotspot_clients 命中
            on_effective = bool(on) or bool(clients)
            if on_effective:
                state_label.configure(
                    text="✅ 热点已开启\n\n手机/平板连接电脑热点即可上网，只占电脑 1 个校园网名额。\n"
                         "WiFi 名称与密码在「系统设置 → 移动热点/互联网共享」中查看/修改。",
                    foreground="#3fae7f")
            else:
                if core.IS_MACOS:
                    state_label.configure(
                        text="⚠️ macOS 互联网共享限制\n\n"
                             "macOS 不支持 Wi-Fi→Wi-Fi 共享（系统级硬限制，App 无法绕过）。\n"
                             "可选方案：\n"
                             "① USB 线连手机（系统设置 → 共享 → 互联网共享 → Wi-Fi 共享给 iPhone USB）\n"
                             "② 改用「隧道共享」：iPhone 配 HTTP 代理指电脑 IP:8080，效果一样\n\n"
                             "点击下方按钮打开 macOS 共享设置页（macOS 不支持脚本化开启）。",
                        foreground="#f1b84b")
                else:
                    state_label.configure(
                        text="电脑热点尚未开启。点击下方「一键开启热点」即可自动启动（需 Wi-Fi 网卡支持移动热点）。\n\n"
                             "失败 fallback 到系统「设置 → 移动热点」手动开启。", foreground=FG)
            # 设备列表
            tree.delete(*tree.get_children())
            for c in clients:
                tree.insert("", "end", values=(
                    c.get("ip", "—"),
                    c.get("mac", "—") or "—",
                    c.get("vendor", "") or "—",
                    (core.fmt_bytes(c.get("rx_bytes")) if c.get("rx_bytes") is not None
                     else (c.get("note", "") or "—")),
                    (core.fmt_bytes(c.get("tx_bytes")) if c.get("tx_bytes") is not None
                     else "—"),
                ))
            list_label.configure(text="连入设备 (%d)" % len(clients))
            if not clients:
                note_label.configure(
                    text="当前未检测到连入设备。开启热点后让手机/平板连入此电脑，再点「刷新状态」。")
            else:
                note_label.configure(
                    text="提示：macOS 不能按 IP 拆分流量（需 sudo），列出的「接收/发送」是 NAT 接口的总流量；Windows 可按 IP 精确拆分。")

        refresh()
        btns = ttk.Frame(card, style="Inner.TFrame")
        btns.pack(fill="x", pady=(16, 0))
        if core.IS_MACOS:
            ttk.Button(btns, text="打开 macOS 共享设置", style="Accent.TButton",
                       command=lambda: self._open_hotspot_setting()).pack(side="left")
        else:
            ttk.Button(btns, text="一键开启热点", style="Accent.TButton",
                       command=lambda: self._start_hotspot()).pack(side="left")
            ttk.Button(btns, text="打开热点设置", style="Gray.TButton",
                       command=lambda: self._open_hotspot_setting()).pack(side="left", padx=(10, 0))
        ttk.Button(btns, text="刷新状态", style="Gray.TButton",
                   command=refresh).pack(side="left", padx=(10, 0))
        ttk.Label(card, text="原理：所有设备走电脑的网络出口，只占用电脑 1 个校园网名额，"
                             "不受校园网多设备限制。", style="Muted.TLabel",
                  wraplength=640).pack(anchor="w", pady=(20, 0))
        self._fwin_open("hotspot", lambda: win)

    def _start_hotspot(self):
        """一键开启 Windows 移动热点 (PowerShell 优先, netsh 兜底)."""
        ok, msg = core.start_mobile_hotspot()
        if ok:
            self._log("移动热点: %s" % msg)
            messagebox.showinfo("✅ 已开启", msg + "\n\n请到「设置 → 移动热点」查看 WiFi 名称/密码。")
        else:
            self._log("一键开热点失败: %s" % msg)
            messagebox.showwarning("开启失败", msg)
            self._open_hotspot_setting()

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
