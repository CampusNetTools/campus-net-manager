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

try:
    import pystray
    from PIL import Image, ImageDraw
    HAS_TRAY = True
except Exception:
    HAS_TRAY = False

# ---------- 深色主题 ----------
BG = "#1e1e2e"
CARD = "#2a2a3c"
CARD2 = "#32324a"
FG = "#e8e8f0"
MUTED = "#9a9ab0"
ACCENT = "#7c5cff"
GREEN = "#4cc38a"
RED = "#f46d6d"
YELLOW = "#e6c15a"
FONT = ("Microsoft YaHei UI", 10)
FONT_S = ("Microsoft YaHei UI", 9)
FONT_M = ("Microsoft YaHei UI", 13)
FONT_L = ("Microsoft YaHei UI", 18, "bold")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("校园网连接管家 v" + core.APP_VERSION)
        self.geometry("780x880")
        self.minsize(720, 800)
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

    # ---------- 样式 ----------
    def _style(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("TFrame", background=BG)
        s.configure("Card.TFrame", background=CARD)
        s.configure("TLabel", background=BG, foreground=FG, font=FONT)
        s.configure("Card.TLabel", background=CARD, foreground=FG, font=FONT)
        s.configure("Muted.TLabel", background=CARD, foreground=MUTED, font=FONT_S)
        s.configure("Title.TLabel", background=BG, foreground=FG, font=FONT_L)
        s.configure("Sub.TLabel", background=BG, foreground=MUTED, font=FONT_S)
        s.configure("TEntry", fieldbackground=CARD2, foreground=FG, insertcolor=FG, font=FONT, bordercolor=CARD2)
        s.configure("TCombobox", fieldbackground=CARD2, foreground=FG, background=CARD2, arrowcolor=FG, font=FONT)
        s.map("TCombobox",
              fieldbackground=[("readonly", CARD2), ("disabled", CARD2)],
              background=[("readonly", CARD2), ("active", CARD2)],
              foreground=[("readonly", FG)],
              selectbackground=[("readonly", CARD2)],
              selectforeground=[("readonly", FG)],
              arrowcolor=[("readonly", MUTED)])
        s.configure("TCombobox.Listbox", background=CARD2, foreground=FG,
                    bordercolor=CARD, selectbackground=ACCENT, selectforeground="#ffffff")
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=CARD, foreground=MUTED, padding=(16, 6), font=FONT)
        s.map("TNotebook.Tab", background=[("selected", "#4a4a72")],
              foreground=[("selected", "#ffffff")],
              font=[("selected", ("Microsoft YaHei UI", 10, "bold"))])
        s.configure("Accent.TButton", background=ACCENT, foreground="#ffffff", font=FONT, borderwidth=0, padding=(14, 6))
        s.map("Accent.TButton", background=[("active", "#6b4df0"), ("pressed", "#5c3fd6")])
        s.configure("Green.TButton", background="#2f9e6b", foreground="#ffffff", font=FONT, borderwidth=0, padding=(14, 6))
        s.map("Green.TButton", background=[("active", "#2a8f5f"), ("pressed", "#23794f")])
        s.configure("Gray.TButton", background="#3a3a52", foreground=FG, font=FONT, borderwidth=0, padding=(14, 6))
        s.map("Gray.TButton", background=[("active", "#454563"), ("pressed", "#2f2f45")])
        s.configure("Danger.TButton", background="#b34a4a", foreground="#ffffff", font=FONT, borderwidth=0, padding=(14, 6))
        s.map("Danger.TButton", background=[("active", "#a04040"), ("pressed", "#8a3434")])
        s.configure("AutoOn.TButton", background="#2f9e6b", foreground="#ffffff", font=FONT, borderwidth=0, padding=(14, 6))
        s.map("AutoOn.TButton", background=[("active", "#2a8f5f"), ("pressed", "#23794f")])
        s.configure("AutoOff.TButton", background="#3a3a52", foreground=FG, font=FONT, borderwidth=0, padding=(14, 6))
        s.map("AutoOff.TButton", background=[("active", "#454563"), ("pressed", "#2f2f45")])

    # ---------- UI ----------
    def _build_ui(self):
        top = ttk.Frame(self, padding=(18, 14, 18, 4))
        top.pack(fill="x")
        ttk.Label(top, text="校园网连接管家", style="Title.TLabel").pack(anchor="w")
        ttk.Label(top, text="多档案自动匹配 · 掉线自动重登 · 非校园网自动休眠", style="Sub.TLabel").pack(anchor="w", pady=(2, 0))

        # 状态卡片
        status = ttk.Frame(self, style="Card.TFrame", padding=(16, 12))
        status.pack(fill="x", padx=18, pady=(10, 4))
        status.columnconfigure(3, weight=1)

        self.dot_guard = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=FONT_M)
        self.dot_guard.grid(row=0, column=0, padx=(0, 6))
        self.lbl_guard = ttk.Label(status, text="守护: 未运行", style="Card.TLabel")
        self.lbl_guard.grid(row=0, column=1, padx=(0, 24))

        self.dot_net = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=FONT_M)
        self.dot_net.grid(row=0, column=2, padx=(0, 6))
        self.lbl_net = ttk.Label(status, text="网络: 未知", style="Card.TLabel")
        self.lbl_net.grid(row=0, column=3, sticky="w")

        self.dot_env = tk.Label(status, text="●", fg=MUTED, bg=CARD, font=FONT_M)
        self.dot_env.grid(row=1, column=0, padx=(0, 6), pady=(8, 0))
        self.lbl_env = ttk.Label(status, text="环境: 检测中...", style="Card.TLabel")
        self.lbl_env.grid(row=1, column=1, columnspan=3, sticky="w", pady=(8, 0))

        self.lbl_last = ttk.Label(status, text="上次检测: -", style="Muted.TLabel")
        self.lbl_last.grid(row=2, column=0, columnspan=4, sticky="w", pady=(6, 0))

        # 档案卡片: 两列网格布局 (标签右对齐/控件左对齐, 统一间距)
        pcfg = ttk.Frame(self, style="Card.TFrame", padding=(18, 14))
        pcfg.pack(fill="x", padx=18, pady=6)
        for c in (1, 3):
            pcfg.columnconfigure(c, weight=1)
        ttk.Label(pcfg, text="⚙ 连接档案（每个 WiFi 一套配置，自动匹配）", style="Card.TLabel",
                  font=("Microsoft YaHei UI", 11, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 12))

        # 当前档案选择行
        prof_row = ttk.Frame(pcfg, style="Card.TFrame")
        prof_row.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(0, 10))
        ttk.Label(prof_row, text="当前档案", style="Card.TLabel").pack(side="left")
        self.cmb_profile = ttk.Combobox(prof_row, width=30, state="readonly")
        self.cmb_profile.pack(side="left", padx=(10, 10))
        self.cmb_profile.bind("<<ComboboxSelected>>", lambda e: self._load_form_from_current())
        ttk.Button(prof_row, text="＋ 新建", style="Gray.TButton", command=self.new_profile).pack(side="left", padx=(0, 6))
        ttk.Button(prof_row, text="🗑 删除", style="Danger.TButton", command=self.del_profile).pack(side="left")

        def _flabel(row, col, text):
            ttk.Label(pcfg, text=text, style="Card.TLabel").grid(
                row=row, column=col, sticky="e", padx=(0, 10), pady=5)

        # row2: 档案名称 | 运营商
        _flabel(2, 0, "档案名称")
        self.ent_name = ttk.Entry(pcfg, width=24)
        self.ent_name.grid(row=2, column=1, sticky="w", pady=5)
        _flabel(2, 2, "运营商")
        self.cmb_type = ttk.Combobox(pcfg, width=24, state="readonly",
                                     values=["移动互联网访问 (cmcc)", "联通互联网访问 (unicom)", "教师登录 (teacher)"])
        self.cmb_type.grid(row=2, column=3, sticky="w", pady=5)

        # row3: 账号 | 密码
        _flabel(3, 0, "账号")
        self.ent_user = ttk.Entry(pcfg, width=24)
        self.ent_user.grid(row=3, column=1, sticky="w", pady=5)
        _flabel(3, 2, "密码")
        pwf = ttk.Frame(pcfg, style="Card.TFrame")
        pwf.grid(row=3, column=3, sticky="w", pady=5)
        self.ent_pass = ttk.Entry(pwf, width=19, show="●")
        self.ent_pass.pack(side="left")
        tk.Button(pwf, text="👁", relief="flat", bg=CARD, fg=MUTED, activebackground=CARD,
                  activeforeground=FG, cursor="hand2", font=FONT_S, bd=0, padx=4,
                  command=self._toggle_pass).pack(side="left", padx=(6, 0))

        # row4: 检测间隔
        _flabel(4, 0, "检测间隔 (秒/次)")
        self.cmb_interval = ttk.Combobox(pcfg, width=24, values=["60", "300", "600", "1800", "3600"])
        self.cmb_interval.grid(row=4, column=1, sticky="w", pady=5)

        # row5: 绑定方式 (无线 WiFi / 有线 选项卡)
        _flabel(5, 0, "绑定方式")
        nb = ttk.Notebook(pcfg)
        nb.grid(row=5, column=1, columnspan=3, sticky="w", pady=5)
        tab_w = ttk.Frame(nb, style="Card.TFrame", padding=(10, 5))
        tab_e = ttk.Frame(nb, style="Card.TFrame", padding=(10, 5))
        nb.add(tab_w, text="无线 WiFi")
        nb.add(tab_e, text="有线")
        ttk.Label(tab_w, text="绑定 WiFi (SSID)", style="Card.TLabel").pack(side="left")
        self.ent_ssid = ttk.Entry(tab_w, width=30)
        self.ent_ssid.pack(side="left", padx=(10, 0))
        ttk.Label(tab_e, text="网关 IP", style="Card.TLabel").pack(side="left")
        self.ent_gw = ttk.Entry(tab_e, width=30)
        self.ent_gw.pack(side="left", padx=(10, 0))

        # row6: 认证服务器 + 自动探测
        _flabel(6, 0, "认证服务器")
        authf = ttk.Frame(pcfg, style="Card.TFrame")
        authf.grid(row=6, column=1, columnspan=3, sticky="w", pady=5)
        self.cmb_auth = ttk.Combobox(authf, width=30)
        self.cmb_auth.pack(side="left")
        self.btn_detect = tk.Button(authf, text="🔍 自动探测", relief="flat", bg=ACCENT, fg="#ffffff",
                                    activebackground="#6b4df0", activeforeground="#ffffff",
                                    cursor="hand2", font=FONT_S, bd=0, padx=10, pady=3,
                                    command=self.detect_auth)
        self.btn_detect.pack(side="left", padx=(10, 0))

        # row7: 操作按钮
        btns = ttk.Frame(pcfg, style="Card.TFrame")
        btns.grid(row=7, column=0, columnspan=4, sticky="ew", pady=(14, 2))
        self.btn_save = ttk.Button(btns, text="💾 保存档案", style="Accent.TButton", command=self.save_profile)
        self.btn_save.pack(side="left")
        self.btn_check = ttk.Button(btns, text="🔍 立即检测", style="Gray.TButton", command=self.check_now)
        self.btn_check.pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="📤 导出", style="Gray.TButton", command=self.export_config).pack(side="left", padx=(8, 0))
        ttk.Button(btns, text="📥 导入", style="Gray.TButton", command=self.import_config).pack(side="left", padx=(8, 0))
        # 工具组(右侧): 隧道共享 / 热点 / 路由器管理页
        self.btn_share = ttk.Button(btns, text="🔗 隧道", style="Gray.TButton", command=self.toggle_share)
        self.btn_share.pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="📶 热点", style="Gray.TButton", command=self.show_hotspot).pack(side="right", padx=(6, 0))
        ttk.Button(btns, text="🌐 管理页", style="Gray.TButton", command=self.open_router_admin).pack(side="right")

        # 控制区
        ctrl = ttk.Frame(self, padding=(18, 4))
        ctrl.pack(fill="x")
        self.btn_start = ttk.Button(ctrl, text="▶ 启动守护", style="Green.TButton", command=self.start_daemon)
        self.btn_start.pack(side="left")
        self.btn_stop = ttk.Button(ctrl, text="⏹ 停止守护", style="Danger.TButton", command=self.stop_daemon)
        self.btn_stop.pack(side="left", padx=(8, 0))
        self.var_auto = tk.BooleanVar(value=core.autostart_enabled())
        self.btn_auto = ttk.Button(ctrl, text="❌ 开机自启", style="AutoOff.TButton",
                                   command=self._toggle_autostart)
        self.btn_auto.pack(side="left", padx=(16, 0))
        self._update_auto_btn()
        self.btn_help = ttk.Button(ctrl, text="❓ 使用帮助", style="Gray.TButton", command=self.show_help)
        self.btn_help.pack(side="right")
        self.btn_wizard = ttk.Button(ctrl, text="🚀 新手向导", style="Accent.TButton", command=self.show_wizard)
        self.btn_wizard.pack(side="right", padx=(0, 8))
        ttk.Button(ctrl, text="🩺 诊断", style="Gray.TButton", command=self.export_diag).pack(side="right", padx=(0, 8))

        # 日志区
        logf = ttk.Frame(self, style="Card.TFrame", padding=(12, 10))
        logf.pack(fill="both", expand=True, padx=18, pady=(4, 14))
        headf = ttk.Frame(logf, style="Card.TFrame")
        headf.pack(fill="x")
        ttk.Label(headf, text="📄 运行日志", style="Card.TLabel", font=("Microsoft YaHei UI", 10, "bold")).pack(side="left")
        self.btn_log_toggle = tk.Button(headf, text="▲ 收起", relief="flat", bg=CARD, fg=MUTED,
                                        activebackground=CARD2, activeforeground=FG,
                                        cursor="hand2", font=FONT_S, bd=0, padx=8, pady=1,
                                        command=self._toggle_log)
        self.btn_log_toggle.pack(side="right")
        tk.Frame(logf, bg="#3a3a52", height=1).pack(fill="x", pady=(8, 0))
        self.log_expanded = True
        self.txt_log = tk.Text(logf, bg="#16161f", fg="#c9c9dd", font=("Consolas", 9),
                               relief="flat", height=10, wrap="none", state="disabled",
                               insertbackground=FG, selectbackground=ACCENT)
        self.txt_log.pack(fill="both", expand=True, pady=(6, 0))
        self._load_existing_log()

    def _toggle_log(self):
        self.log_expanded = not self.log_expanded
        if self.log_expanded:
            self.txt_log.pack(fill="both", expand=True, pady=(6, 0))
            self.btn_log_toggle.configure(text="▲ 收起")
        else:
            self.txt_log.pack_forget()
            self.btn_log_toggle.configure(text="▼ 展开")
            self.btn_log_toggle.master.master.pack(fill="both", expand=True, padx=18, pady=(4, 14))

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
        if len(self.cfg["profiles"]) <= 1:
            messagebox.showwarning("提示", "至少保留一个档案")
            return
        if not messagebox.askyesno("删除档案", "确定删除档案「%s」吗？" % p["name"]):
            return
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
            core.save_config(self.cfg)
            self._refresh_profile_list()
            self._log("档案已保存: %s (%s)" % (data["name"], data["ssid"] or "默认"))
            messagebox.showinfo("已保存", "档案「%s」已保存。\n\n换网络后 App 会根据 WiFi 自动匹配对应档案。" % data["name"])
        except Exception as e:
            messagebox.showerror("保存失败", str(e))

    def open_router_admin(self):
        threading.Thread(target=self._do_open_router, daemon=True).start()

    def _do_open_router(self):
        self._log("正在探测路由器管理页...")
        url = core.get_router_admin_url()
        if url:
            self._log("打开管理页: %s" % url)
            webbrowser.open(url)
        else:
            self._log("未检测到路由器管理页")
            self.after(0, lambda: messagebox.showwarning(
                "未找到", "没检测到路由器管理页。\n请确认电脑已连接路由器 WiFi 后重试。"))

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
            self.btn_share.configure(text="🔗 隧道", style="Gray.TButton")
            return
        try:
            allowed = list(self.cfg.get("tunnel_allow", []))
            self.proxy = shared_proxy.SharedProxy(port=8080, allowed=allowed,
                                                  on_ask=self._ask_tunnel_allow)
            self.proxy.start()
        except Exception as e:
            self.proxy = None
            messagebox.showerror("开启失败",
                                 "无法监听 8080 端口：%s\n\n可能是端口被占用，或需要防火墙放行。" % e)
            return
        self.btn_share.configure(text="🔗 隧道:开", style="Green.TButton")
        ips = shared_proxy.get_lan_ips()
        myip = ips[0] if ips else "本机IP"
        self._log("隧道共享已开启: %s:8080 (已有授权设备 %d 台)"
                  % (myip, len(self.proxy.allowed)))
        msg = ("隧道共享已开启 ✅\n\n"
               "【手机/平板设置】(与电脑连同一个网络后):\n"
               "① Wi-Fi → 点当前网络右侧 ⓘ →\n"
               "② 配置代理 → 手动\n"
               "③ 服务器:  %s\n"
               "④ 端口:  8080 → 保存\n\n"
               "手机首次连接会弹出「是否允许该设备」→ 点允许即可。\n"
               "授权过的设备下次直接可用，不占额外校园网名额。\n\n"
               "⚠️ 只在你信任的网络(宿舍/教室)开启；\n"
               "关闭隧道后授权记录自动保存。" % myip)
        messagebox.showinfo("🔗 隧道共享", msg)

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
                ok = messagebox.askyesno(
                    "🔗 设备连接请求",
                    "有设备 (%s) 想使用你的隧道共享上网。\n\n"
                    "✅ 允许 —— 记住该设备，以后不再询问\n"
                    "❌ 拒绝 —— 断开它" % ip,
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
        self.btn_auto.configure(text="✅ 开机自启" if on else "❌ 开机自启",
                                style="AutoOn.TButton" if on else "AutoOff.TButton")

    def _toggle_autostart(self):
        ok = core.set_autostart(self.var_auto.get())
        if not ok:
            self.var_auto.set(not self.var_auto.get())
            messagebox.showerror("失败", "修改开机自启失败（可能需要权限）")
        else:
            self._log("开机自启: %s" % ("已开启" if self.var_auto.get() else "已关闭"))
        self._update_auto_btn()

    def export_config(self):
        path = filedialog.asksaveasfilename(
            title="导出配置", defaultextension=".json",
            initialfile="校园网连接管家配置.json",
            filetypes=[("JSON 配置", "*.json")])
        if not path:
            return
        try:
            import shutil
            shutil.copyfile(core.CONFIG_PATH, path)
            messagebox.showinfo("已导出", "配置已导出到：\n%s\n\n（含账号密码，请妥善保管，勿外传）" % path)
        except Exception as e:
            messagebox.showerror("导出失败", str(e))

    def import_config(self):
        path = filedialog.askopenfilename(
            title="导入配置", filetypes=[("JSON 配置", "*.json")])
        if not path:
            return
        try:
            import shutil
            shutil.copyfile(path, core.CONFIG_PATH)
            self.cfg = core.load_config()
            self._refresh_profile_list()
            self._load_form_from_current()
            self._log("配置已导入: %s" % path)
            messagebox.showinfo("已导入", "配置导入成功。\n重启守护后生效。")
        except Exception as e:
            messagebox.showerror("导入失败", str(e))

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
        self.btn_start.state(["disabled"] if running else ["!disabled"])
        self.btn_stop.state(["!disabled"] if running else ["disabled"])

    def set_net(self, online, authed, last_check):
        if last_check:
            self.lbl_last.configure(text="上次检测: %s" % last_check)
        if online:
            self.dot_net.configure(fg=GREEN)
            self.lbl_net.configure(text="网络: 在线正常")
        elif authed:
            self.dot_net.configure(fg=YELLOW)
            self.lbl_net.configure(text="网络: 假在线 (外网不通)")
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

    def _on_status(self, online, authed, last_check):
        self.after(0, self.set_net, online, authed, last_check)

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
        if not any(p.get("username") for p in self.cfg.get("profiles", [])):
            messagebox.showwarning("未配置", "请先在档案中填写账号密码并保存")
            core.release_lock()
            return
        self.daemon = core.KeepAliveDaemon(self.cfg, on_log=self._on_log, on_status=self._on_status,
                                           on_env=self._on_env, on_alert=self._on_alert)
        self.daemon.start()
        self.set_guard(True)
        if not silent:
            self._log("守护启动 (GUI)")

    def export_diag(self):
        """一键诊断导出: 网络状态/档案(脱敏)/日志 → 文件 + 剪贴板"""
        def _do():
            try:
                text = core.collect_diagnostics()
                import datetime
                desktop = os.path.join(os.path.expanduser("~"), "Desktop")
                fname = os.path.join(desktop, "校园网连接管家诊断_%s.txt"
                                     % datetime.datetime.now().strftime("%Y%m%d_%H%M%S"))
                with open(fname, "w", encoding="utf-8") as f:
                    f.write(text)
                try:
                    self.clipboard_clear()
                    self.clipboard_append(text)
                except Exception:
                    pass
                def done():
                    self._log("诊断报告已保存: %s" % fname)
                    messagebox.showinfo("🩺 诊断完成",
                                        "诊断报告已保存到桌面:\n%s\n\n内容也已复制到剪贴板，可直接粘贴发给技术人员。" % fname)
                self.after(0, done)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("诊断失败", str(e)))
        threading.Thread(target=_do, daemon=True).start()

    def _on_alert(self, text):
        """守护告警 → 托盘通知 (守护线程调用, 线程安全)"""
        def _notify():
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
        self.btn_detect.configure(text="探测中...")
        threading.Thread(target=self._do_detect, daemon=True).start()

    def _do_detect(self):
        try:
            url = core.detect_auth_server()
        except Exception as e:
            url = None
            err = str(e)
            self.after(0, lambda: self._log("探测异常: %s" % err))
        def done():
            self.btn_detect.configure(text="🔍 探测")
            if url:
                self.cmb_auth.set(url)
                self._log("自动探测到认证服务器: %s" % url)
            else:
                messagebox.showwarning(
                    "未探测到认证服务器",
                    "没有检测到认证服务器的重定向。\n\n常见原因：\n· 当前已经认证在线（探测需要未认证状态）\n· 当前不在校园网环境\n\n可以先断开校园网认证再点探测，或直接手动输入。")
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
                     "    适合：设备多、要覆盖全屋（推荐）\n\n"
                     "点下面按钮选择：")
            btn_prev.pack_forget()
            btn_act.configure(text="选 A：电脑直连", command=lambda: enter_plan_a())
            btn_act2.configure(text="选 B：路由器中继", command=lambda: enter_plan_b())
            btn_act2.pack(side="right", padx=(0, 8))

        def enter_plan_a():
            state["plan"] = "A"
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
            btn_act.configure(text="打开 WiFi 设置", command=lambda: os.startfile("ms-settings:network-wifi"))
            btn_act2.configure(text="打开移动热点", command=lambda: os.startfile("ms-settings:network-mobilehotspot"))
            btn_prev.pack(side="left")
            btn_prev.configure(command=lambda: show_plan_choice())

        def enter_plan_b():
            state["plan"] = "B"
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
        internet = core.check_internet()
        self._on_status(internet and authed, authed, core.now_str())
        if authed and internet:
            self._log("结果: 在线正常")
        elif authed:
            self._log("结果: 假在线 (认证页在但外网不通)")
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
            if core.acquire_lock():
                core.release_lock()
                self.start_daemon(silent=True)
        except Exception:
            pass
        # 首次运行: 未配置账号 → 自动打开新手向导引导
        if not any(p.get("username") for p in self.cfg.get("profiles", [])):
            self.after(800, self.show_wizard)


if __name__ == "__main__":
    App().mainloop()
