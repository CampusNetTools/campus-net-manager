# -*- coding: utf-8 -*-
"""设备管理窗口 Mixin (v5.2.0 新增)。

提供两个能力, 对应校园网"单账号多设备"的两个诉求:
  1. 保护设备 —— 固定某台(路由器/本机)一直在线, 不被新登录的设备挤掉。
     底层靠守护的会话刷新(见 core/daemon.py 的 kick_guard + protected_device),
     本窗口只负责开/关 + 命名 + 状态展示。
  2. 在线设备管理 —— 拉取自助服务系统里的在线设备列表, 一键"解除绑定/踢下线",
     把占用名额的其他设备挤掉。

自助服务接口在设备离开校园网时不可达, 本窗口对"拉取失败"做友好提示, 不崩。
"""
import threading  # noqa: F401
import tkinter as tk  # noqa: F401
from tkinter import ttk, messagebox  # noqa: F401

import keepalive_core as core  # noqa: F401
from gui.theme import *  # noqa: F401,F403
from gui.scrollkit import fit_geometry, make_scrollable  # noqa: F401


class DeviceManagerMixin:
    """设备管理独立窗口。"""

    def _load_protected_device(self):
        pd = self.cfg.get("protected_device", {}) or {}
        return {
            "enabled": bool(pd.get("enabled")),
            "name": pd.get("name", "") or "",
            "kind": pd.get("kind", "router"),
        }

    def _save_protected_device(self, enabled, name, kind):
        self.cfg["protected_device"] = {"enabled": bool(enabled),
                                        "name": name or "", "kind": kind}
        try:
            core.save_config(self.cfg)
        except Exception as e:
            messagebox.showerror("保存失败", "无法保存保护设备设置: %s" % e, parent=self)
            return False
        return True

    def show_device_manager(self):
        """打开设备管理窗口 (单实例)。"""
        win = tk.Toplevel(self)
        win.title("设备管理")
        win.configure(bg=BG)
        win.geometry(fit_geometry(win, 640, 640, min_h=520))
        win.resizable(False, False)
        win.transient(self)

        page = make_scrollable(win, pad=(0, 0), inner_bg_style="TFrame")
        card = ttk.Frame(page, style="Card.TFrame", padding=(24, 20))
        card.pack(fill="both", expand=True, padx=16, pady=16)

        ttk.Label(card, text="设备管理", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="固定某台设备一直在线 · 管理在线设备 · 一键解除绑定",
                  style="Muted.TLabel").pack(anchor="w", pady=(4, 14))

        # ===== 一、保护设备 =====
        ttk.Label(card, text="保护设备（不被挤掉）", style="CardSubTitle.TLabel").pack(
            anchor="w", pady=(4, 2))
        ttk.Label(card, text="开启后, 守护会频繁刷新本机/路由器的出口会话, 让它始终是"
                              "“最新”会话。校园网按会话新鲜度淘汰设备, 新设备登录时被挤掉的"
                              "就是别人, 而不是你的这台设备。",
                  style="Muted.TLabel", wraplength=560, justify="left").pack(anchor="w")

        pd = self._load_protected_device()
        var_protect = tk.BooleanVar(value=pd["enabled"])
        protect_row = ttk.Frame(card, style="Inner.TFrame")
        protect_row.pack(fill="x", pady=(10, 0))
        ttk.Checkbutton(protect_row, text="启用保护", style="Checkmark.TCheckbutton",
                        variable=var_protect).pack(side="left")

        name_row = ttk.Frame(card, style="Inner.TFrame")
        name_row.pack(fill="x", pady=(8, 0))
        ttk.Label(name_row, text="设备名称", style="Field.TLabel").pack(side="left")
        ent_name = ttk.Entry(name_row, width=30)
        ent_name.insert(0, pd["name"] or "小米路由器")
        ent_name.pack(side="left", padx=(10, 0))

        hint_row = ttk.Frame(card, style="Inner.TFrame")
        hint_row.pack(fill="x", pady=(4, 0))
        lbl_hint = ttk.Label(hint_row, text="", style="Muted.TLabel", wraplength=560,
                             justify="left")
        lbl_hint.pack(anchor="w")

        def _render_protect_hint():
            if var_protect.get():
                lbl_hint.configure(
                    text="保护模式已开启：守护将每轮循环刷新出口会话，确保“%s”不被挤掉。"
                         % (ent_name.get().strip() or "该设备"))
            else:
                lbl_hint.configure(text="保护模式关闭：守护按默认频率刷新会话。")

        _render_protect_hint()
        var_protect.trace_add("write", lambda *a: _render_protect_hint())

        btn_save_protect = ttk.Button(card, text="保存保护设置", style="Accent.TButton",
                                      command=lambda: self._on_save_protect(
                                          win, var_protect, ent_name))
        btn_save_protect.pack(anchor="w", pady=(10, 0))

        # ===== 二、在线设备 =====
        ttk.Separator(card, orient="horizontal").pack(fill="x", pady=(16, 12))
        ttk.Label(card, text="在线设备（校园网自助服务）", style="CardSubTitle.TLabel").pack(
            anchor="w", pady=(0, 2))
        ttk.Label(card, text="查看当前账号在校园网上的在线设备, 点“解除绑定”把占用名额的"
                              "其他设备踢下线。需设备处于校园网环境。",
                  style="Muted.TLabel", wraplength=560, justify="left").pack(anchor="w")

        list_host = ttk.Frame(card, style="Inner.TFrame")
        list_host.pack(fill="x", pady=(8, 0))

        head_row = ttk.Frame(card, style="Inner.TFrame")
        head_row.pack(fill="x", pady=(10, 0))
        status_lbl = ttk.Label(head_row, text="", style="Muted.TLabel")
        status_lbl.pack(side="left", padx=(12, 0))
        refresh_btn = ttk.Button(head_row, text="刷新设备列表", style="Gray.TButton",
                                 command=lambda: self._refresh_devices(
                                     list_host, status_lbl, refresh_btn))
        refresh_btn.pack(side="left")

        # 初始占位
        placeholder = ttk.Label(list_host, text="点击“刷新设备列表”查看在线设备",
                                style="Muted.TLabel")
        placeholder.pack(anchor="w", pady=(6, 6))

        # 首次打开自动刷新一次 (异步)
        self.after(200, lambda: self._refresh_devices(list_host, status_lbl, refresh_btn))

    # ---------- 事件处理 ----------
    def _on_save_protect(self, win, var_protect, ent_name):
        name = ent_name.get().strip()
        ok = self._save_protected_device(var_protect.get(), name, "router")
        if ok:
            self._log("保护设备设置已保存: %s (%s)" % (
                name or "未命名", "开启" if var_protect.get() else "关闭"))
            messagebox.showinfo("已保存", "保护设备设置已保存。守护会在下轮循环生效。",
                                parent=win)

    def _refresh_devices(self, list_host, status_lbl, refresh_btn):
        """异步拉取在线设备列表并渲染。"""
        status_lbl.configure(text="正在拉取…")
        refresh_btn.configure(state="disabled")

        def work():
            devices, error = core.selfservice.fetch_online_devices(self.cfg)
            self.after(0, lambda: self._render_devices(
                list_host, status_lbl, refresh_btn, devices, error))

        threading.Thread(target=work, daemon=True).start()

    def _render_devices(self, list_host, status_lbl, refresh_btn, devices, error):
        refresh_btn.configure(state="normal")
        for child in list_host.winfo_children():
            child.destroy()

        if error:
            status_lbl.configure(text="拉取失败")
            tk.Label(list_host, text=error, bg=CARD, fg=YELLOW, font=FONT_S,
                     wraplength=540, justify="left").pack(anchor="w", pady=(6, 6))
            return

        if not devices:
            status_lbl.configure(text="无在线设备")
            ttk.Label(list_host, text="未解析到在线设备（可能账号当前无设备在线，或自助"
                                      "服务返回格式需校准）。", style="Muted.TLabel",
                      wraplength=540, justify="left").pack(anchor="w", pady=(6, 6))
            return

        status_lbl.configure(text="共 %d 台设备在线" % len(devices))

        # 表头
        header = ttk.Frame(list_host, style="Surface.TFrame", padding=(10, 6))
        header.pack(fill="x")
        header.columnconfigure(0, weight=3)
        header.columnconfigure(1, weight=2)
        header.columnconfigure(2, weight=2)
        header.columnconfigure(3, weight=2)
        for col, title in enumerate(("设备", "IP", "MAC", "操作")):
            ttk.Label(header, text=title, style="SurfaceMuted.TLabel").grid(
                row=0, column=col, sticky="w")

        for device in devices:
            row = ttk.Frame(list_host, style="Inner.TFrame", padding=(10, 4))
            row.pack(fill="x", pady=(2, 0))
            row.columnconfigure(0, weight=3)
            row.columnconfigure(1, weight=2)
            row.columnconfigure(2, weight=2)
            row.columnconfigure(3, weight=2)

            name = device.get("name") or device.get("mac") or device.get("ip") or "未知设备"
            ip = device.get("ip") or "—"
            mac = device.get("mac") or "—"
            ttk.Label(row, text=name, style="Card.TLabel").grid(
                row=0, column=0, sticky="w")
            ttk.Label(row, text=ip, style="Muted.TLabel").grid(
                row=0, column=1, sticky="w")
            ttk.Label(row, text=mac, style="Muted.TLabel").grid(
                row=0, column=2, sticky="w")
            btn = ttk.Button(row, text="解除绑定", style="Danger.TButton",
                             command=lambda d=device, r=row: self._on_kick(d, r))
            btn.grid(row=0, column=3, sticky="w")

    def _on_kick(self, device, row):
        name = device.get("name") or device.get("ip") or device.get("mac") or "该设备"
        if not messagebox.askyesno(
                "确认解除绑定",
                "确定要把「%s」从校园网强制下线吗？\n\n该设备会立即断网，此操作不可撤销。"
                % name, parent=self):
            return

        def work():
            ok, error = core.selfservice.kick_device(self.cfg, device)
            self.after(0, lambda: self._kick_done(row, ok, error, name))

        threading.Thread(target=work, daemon=True).start()

    def _kick_done(self, row, ok, error, name):
        if ok:
            self._log("已解除绑定: %s" % name)
            messagebox.showinfo("已解除", "「%s」已从校园网下线。" % name, parent=self)
            # 行置灰标记
            for child in row.winfo_children():
                if isinstance(child, ttk.Label):
                    child.configure(style="Muted.TLabel")
        else:
            self._log("解除绑定失败: %s" % error)
            messagebox.showerror("操作失败", error or "未知错误", parent=self)
