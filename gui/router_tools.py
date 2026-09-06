# -*- coding: utf-8 -*-
"""路由器管理/体检/热点 Mixin (自 app_gui.py 拆分)"""
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


class RouterToolsMixin:
    def open_router_admin(self):
        threading.Thread(target=self._do_open_router, daemon=True).start()


    def _do_open_router(self):
        self._log("正在探测路由器/光猫管理页...")
        fingerprint = core.router_fingerprint()
        saved = (self.cfg.get("routers") or {}).get(fingerprint, {})
        url = saved.get("admin_url") or core.get_router_admin_url()
        if url:
            self._log("打开管理页: %s" % url)
            webbrowser.open(url)
        else:
            self._log("未检测到路由器/光猫管理页")
            self.after(0, lambda: messagebox.showwarning(
                "未找到",
                "没检测到路由器/光猫管理页。\n\n"
                "常见原因与解决：\n"
                "① 若是光猫，直接连光猫 WiFi 后访问192.168.1.1 或 192.168.100.1\n"
                "② 光猫管理页可能被运营商隐藏，需先拨号上网或用超级账号\n"
                "③ 请确认电脑已连接路由器/光猫 WiFi 后重试"))


    def show_router_assessment(self):
        """「路由器检测」窗口: A 段（路由器识别: 品牌/型号/硬件版本/网关/MAC/管理入口）.
        中继方案和固件查询已拆到「路由器中继」窗口。
        """
        win = tk.Toplevel(self)
        win.title("路由器检测")
        win.configure(bg=BG)
        win.geometry("720x640")
        win.minsize(680, 580)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 22))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        card.columnconfigure(1, weight=1)
        ttk.Label(card, text="路由器检测", style="DialogTitle.TLabel").grid(
            row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(card,
                  text="自动读网关/MAC/UPnP 识别品牌和精确型号。仅只读, 不登录路由器、不修改配置。",
                  style="Muted.TLabel", wraplength=640).grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(6, 14))
        card.columnconfigure(1, weight=1)

        # 字段: 品牌 / 型号 / 硬件版本 / 网关 MAC / 管理入口
        entries = {}
        for row, (label, key, readonly) in enumerate([
                ("品牌", "brand", True), ("型号", "model", False),
                ("硬件版本", "revision", False), ("网关 / MAC", "network", True),
                ("固定管理入口", "admin_url", False)]):
            ttk.Label(card, text=label, style="Field.TLabel").grid(
                row=row+2, column=0, sticky="w", pady=(10, 4))
            ent = ttk.Entry(card)
            ent.grid(row=row+2, column=1, columnspan=2, sticky="ew",
                       padx=(16, 0), pady=(10, 4))
            entries[key] = (ent, readonly)

        status_box = tk.Text(card, height=10, bg="#09101c", fg="#b7c4d8",
                             font=("PingFang SC", 10), relief="flat", wrap="word",
                             padx=12, pady=10, state="disabled")
        status_box.grid(row=7, column=0, columnspan=3, sticky="nsew", pady=(14, 12))
        card.rowconfigure(7, weight=1)

        current = {"report": None}

        def set_entry_value(ent, value, readonly):
            ent.configure(state="normal")
            ent.delete(0, "end")
            ent.insert(0, value or "")
            if readonly:
                ent.configure(state="readonly")

        def set_status(text):
            status_box.configure(state="normal")
            status_box.delete("1.0", "end")
            status_box.insert("1.0", text)
            status_box.configure(state="disabled")

        def open_relay_window():
            self._fwin_open_legacy("router_relay", self.show_router_relay_window)

        def open_firmware_lookup():
            """跳出当前窗口, 直接打开路由器中继窗口看固件段。"""
            self._fwin_open_legacy("router_relay", self.show_router_relay_window)

        def refresh_with(report):
            current["report"] = report
            saved = (self.cfg.get("routers") or {}).get(report["fingerprint"], {})
            set_entry_value(entries["brand"][0], report["brand"] or "未识别",
                            entries["brand"][1])
            set_entry_value(entries["model"][0], saved.get("model") or report["model"],
                            entries["model"][1])
            set_entry_value(entries["revision"][0],
                            saved.get("revision") or report["revision"],
                            entries["revision"][1])
            set_entry_value(entries["network"][0],
                            "%s  /  %s" % (report.get("gateway", "") or "无网关",
                                          report.get("mac", "") or "无 MAC"),
                            entries["network"][1])
            set_entry_value(entries["admin_url"][0],
                            saved.get("admin_url") or report.get("admin_url", ""),
                            entries["admin_url"][1])
            lines = [
                "系统识别：%s" % ("OpenWrt / LuCI" if report["openwrt"] else "未识别为 OpenWrt"),
                "管理页标题：%s" % (report.get("page_title", "") or
                                  report.get("admin_url", "") or "未发现"),
                "WISP 评估：%s" % report["wisp_status"],
                "刷机评估：%s" % report["flash_status"],
            ]
            evidence = report.get("evidence") or {}
            if evidence:
                lines.append("UPnP 证据：%s" % " / ".join(filter(None, (
                    evidence.get("friendlyName"), evidence.get("manufacturer"),
                    evidence.get("modelName"), evidence.get("modelNumber")))))
            try:
                stealth = core.relay_stealth_check()
                risk_txt = {"low": "低（仅本机）", "mid": "中（少量设备）",
                            "high": "高（多台设备共享）"}
                lines.append("")
                lines.append("多设备检测：%s 台可见设备（风险：%s）" % (
                    stealth["device_count"], risk_txt.get(stealth["risk"], stealth["risk"])))
                for device in stealth["visible_devices"][:4]:
                    lines.append("  · %s  %s  %s" % (device["ip"], device["mac"],
                                                     device["brand"] or "未知设备"))
                for tip in stealth["advice"][:3]:
                    lines.append("  · %s" % tip)
            except Exception as exc:
                lines.append("")
                lines.append("多设备检测：暂不可用（%s）" % exc)
            set_status("\n\n".join(lines))
            btn_detect.configure(text="重新检测", state="normal")

        def do_detect():
            btn_detect.configure(text="检测中…", state="disabled")
            set_status("正在读取网关/MAC/ARP/UPnP/管理页公开标识…")

            def work():
                try:
                    report = core.detect_router_hardware()
                    self.after(0, lambda: refresh_with(report))
                except Exception as exc:
                    self.after(0, lambda: (
                        set_status("检测失败：%s" % exc),
                        btn_detect.configure(text="重新检测", state="normal")))
            threading.Thread(target=work, daemon=True).start()

        def do_save():
            report = current.get("report")
            if not report:
                messagebox.showwarning("尚未检测", "请先完成一次路由器检测。", parent=win)
                return
            model = entries["model"][0].get().strip()
            revision = entries["revision"][0].get().strip()
            admin_url = entries["admin_url"][0].get().strip()
            if admin_url and not core._private_http_url(admin_url):
                messagebox.showwarning("地址无效", "固定入口必须是局域网 HTTP/HTTPS 地址。",
                                       parent=win)
                return
            self.cfg.setdefault("routers", {})[report["fingerprint"]] = {
                "brand": report.get("brand", ""), "model": model,
                "revision": revision, "admin_url": admin_url,
                "last_checked": core.now_str()
            }
            core.save_config(self.cfg)
            readiness = core.evaluate_flash_readiness(model, revision)
            self._log("已保存路由器识别信息")
            messagebox.showinfo("已保存",
                                "已记住这台路由器和固定管理入口。\n\n%s" % readiness["message"],
                                parent=win)

        # 底部按钮: 检测 / 保存 / 打开管理页 + 跳转中继方案窗口
        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        for col in range(4):
            actions.columnconfigure(col, weight=1)
        btn_detect = ttk.Button(actions, text="开始检测", style="Accent.TButton",
                                command=do_detect)
        btn_detect.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ttk.Button(actions, text="保存识别结果", style="Gray.TButton",
                   command=do_save).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Button(actions, text="打开管理页", style="Gray.TButton",
                   command=self.open_router_admin).grid(row=0, column=2, sticky="ew", padx=6)
        ttk.Button(actions, text="去路由器中继方案", style="Gray.TButton",
                   command=open_relay_window).grid(
            row=0, column=3, sticky="ew", padx=(6, 0))

        # 默认先跑一次检测
        do_detect()


    def show_router_relay_window(self):
        """「路由器中继」窗口: 不刷固件也能用——按品牌路由给上游 WiFi 的分步指引。

        包含两段:
          A. 中继校园网方案   (按品牌生成步骤, 含一键打开路由器中继设置页路径)
          B. 固件适配查询     (按品牌列 OpenWrt/官方/Merlin, 下载到本地, 不刷入)
        """
        from tkinter import filedialog as _fd
        win = tk.Toplevel(self)
        win.title("路由器中继: 不刷固件也能用 + 一键刷固件准备")
        win.configure(bg=BG)
        win.geometry("820x780")
        win.minsize(760, 680)
        win.transient(self)

        # 外层滚动容器
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="Card.TFrame", padding=(24, 22))
        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        ttk.Label(scroll_frame,
                  text="路由器中继校园网 · 不刷固件也能用",
                  style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(scroll_frame,
                  text="路由器连上游校园网 WiFi 分给它 1 个名额, 下挂设备无需账号即可上网。\n"

                       "本窗口不要求刷 OpenWrt, 按品牌给出对应的管理页设置步骤; "
                       "固件适配查询作为可选(为刷固件准备但绝不自动刷入)。",
                  style="Muted.TLabel", justify="left", wraplength=720).pack(
            anchor="w", pady=(6, 16))

        current = {"report": None, "lookup": None}

        # ---------- A. 中继方案段 ----------
        relay_card = ttk.Frame(scroll_frame, style="Inner.TFrame")
        relay_card.pack(fill="x", pady=(0, 18))
        ttk.Label(relay_card, text="A. 路由器中继校园网方案",
                  style="Section.TLabel").pack(anchor="w")
        ttk.Label(relay_card,
                  text="按品牌自动生成进入路由器管理页 → 找到中继/WISP/桥接 → 扫描选 WiFi → 保存 的步骤路径。",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 10))

        relay_actions = ttk.Frame(relay_card, style="Inner.TFrame")
        relay_actions.pack(fill="x")
        ttk.Label(relay_actions, text="上游 SSID:", style="Field.TLabel").pack(side="left")
        v_ssid = tk.StringVar(value="LIDA-UNIVERSITY")
        ttk.Entry(relay_actions, textvariable=v_ssid, width=22).pack(side="left", padx=(8, 0))
        v_need_auth = tk.BooleanVar(value=True)
        ttk.Checkbutton(relay_actions, text="上游需认证 (账号密码)",
                        variable=v_need_auth, style="Checkmark.TCheckbutton").pack(
            side="left", padx=(14, 0))
        ttk.Button(relay_actions, text="生成分步路径", style="Accent.TButton",
                   command=lambda: refresh_relay_guide(v_ssid.get(),
                                                       v_need_auth.get())).pack(
            side="left", padx=(14, 0))

        relay_box = tk.Text(relay_card, height=10, bg="#09101c", fg="#b7c4d8",
                            font=("PingFang SC", 10), relief="flat", wrap="word",
                            padx=12, pady=10, state="disabled")
        relay_box.pack(fill="x", pady=(10, 0))

        def refresh_relay_guide(ssid=None, need_auth=None):
            if ssid is None:
                ssid = "LIDA-UNIVERSITY"
            if need_auth is None:
                need_auth = True
            brand, gw, guide = core.router_guide(ssid, need_auth)
            header = ("自动识别的品牌: %s\n"
                      "管理页地址: %s\n" % (
                          brand or "(未识别 — 请先去「路由器检测」窗口)",
                          gw or "(未找到 — 浏览器常见 192.168.0.1 / 192.168.1.1)"))
            relay_box.configure(state="normal")
            relay_box.delete("1.0", "end")
            relay_box.insert("1.0", header + "\n" + guide)
            relay_box.configure(state="disabled")

        # ---------- B. 固件适配查询段 ----------
        fw_card = ttk.Frame(scroll_frame, style="Inner.TFrame")
        fw_card.pack(fill="x")
        ttk.Label(fw_card, text="B. 固件统一准备（官方适配查询 + 下载到本地）",
                  style="Section.TLabel").pack(anchor="w")
        ttk.Label(fw_card,
                  text="按检测到的品牌查对应的官方/社区固件入口。\n"
                       "本软件仅下载 + 校验, 不刷入路由器——升级请到路由器管理页「系统升级」手动选本地文件。",
                  style="Muted.TLabel", justify="left", wraplength=720).pack(
            anchor="w", pady=(2, 10))

        fw_status_box = tk.Text(fw_card, height=8, bg="#09101c", fg="#b7c4d8",
                                font=("PingFang SC", 10), relief="flat", wrap="word",
                                padx=12, pady=10, state="disabled")
        fw_status_box.pack(fill="x", pady=(0, 10))

        fw_btns = ttk.Frame(fw_card, style="Inner.TFrame")
        fw_btns.pack(fill="x")
        ttk.Button(fw_btns, text="查询官方适配", style="Accent.TButton",
                   command=lambda: refresh_firmware_lookup()).pack(side="left")
        ttk.Button(fw_btns, text="下载到本地（不刷入）",
                   style="Gray.TButton",
                   command=lambda: do_download_fw()).pack(side="left", padx=(10, 0))

        fw_progress = ttk.Progressbar(fw_card, length=720, mode="determinate", maximum=100)
        fw_progress_is_packed = False

        def set_fw_status(text):
            fw_status_box.configure(state="normal")
            fw_status_box.delete("1.0", "end")
            fw_status_box.insert("1.0", text)
            fw_status_box.configure(state="disabled")

        def set_fw_progress(value):
            nonlocal fw_progress_is_packed
            if not fw_progress_is_packed:
                fw_progress.pack(fill="x", pady=(8, 0))
                fw_progress_is_packed = True
            fw_progress.configure(value=value)

        def refresh_firmware_lookup():
            report = current.get("report")
            saved = (self.cfg.get("routers") or {}).get(
                report["fingerprint"], {}) if report else {}
            brand = (report.get("brand", "") if report else "") or saved.get("brand", "")
            model = saved.get("model", "") or (
                report.get("model", "") if report else "")
            revision = saved.get("revision", "") or (
                report.get("revision", "") if report else "")
            lookup = core.lookup_firmware_urls(brand, model, revision)
            current["lookup"] = lookup
            if not brand:
                set_fw_status("请先去「路由器检测」窗口识别品牌后再来查官方适配。\n"
                              "或者下面手动填品牌(常见品牌已在 _FIRMWARE_SOURCES 内置)。")
                return
            lines = [
                "当前路由器: %s %s %s" % (lookup["brand"],
                                          model and "(型号 %s)" % model or "",
                                          revision and "Rev %s" % revision or ""),
                "",
                "厂商适配查询: %s" % (lookup["vendor_url"] or "(未内置)"),
                "OpenWrt 适配: %s" % lookup["openwrt_toh"],
            ]
            if lookup.get("merlin_url"):
                lines.append("Merlin (华硕增强): %s" % lookup["merlin_url"])
            lines.append("")
            lines.append("适配提醒:")
            lines.append(lookup["note"])
            lines.append("")
            lines.append("提示: 点上方「OpenWrt 适配」链接会在浏览器打开对应品牌的官方适配表，")
            lines.append("      按你的精确型号和硬件版本找到匹配的镜像, 复制镜像 SHA256 后再来「下载到本地」。")
            set_fw_status("\n".join(filter(None, lines)))

        def do_download_fw():
            lookup = current.get("lookup")
            if not lookup or not lookup.get("brand"):
                messagebox.showwarning("请先查询",
                                       "先点「查询官方适配」确认品牌, 然后去浏览器把镜像 URL 复制回来。",
                                       parent=win)
                return
            url = tk.simpledialog.askstring(
                "下载镜像到本地",
                "粘贴 OpenWrt / 厂商发布的镜像 URL（HTTP/HTTPS）:",
                parent=win)
            if not url:
                return
            sha256 = tk.simpledialog.askstring(
                "可选: SHA256 校验",
                "粘贴镜像包 SHA256（强烈建议; 与发布页对照, 避免下载不完整/被篡改）:\n"
                "不校验请留空直接点 OK。",
                parent=win)
            default_name = "%s_%s_%s.bin" % (
                (lookup["brand"] or "router"),
                (current.get("report", {}).get("model", "") if current.get("report") else "model"),
                __import__("datetime").datetime.now().strftime("%Y%m%d"))
            save_path = _fd.asksaveasfilename(
                title="选择镜像保存位置（本软件不会自动刷入, 只是下载到本地）",
                defaultextension=".bin",
                initialfile=default_name,
                filetypes=[("固件镜像", "*.bin *.img *.tar *.trx"),
                           ("所有文件", "*.*")])
            if not save_path:
                return

            set_fw_progress(0)
            set_fw_status("正在下载 %s ...\n目标: %s" % (url, save_path))

            def on_progress(done, total):
                pct = (done * 100.0 / total) if total else 0
                self.after(0, lambda: set_fw_progress(pct))

            def work():
                ok, msg, sha = core.download_firmware(
                    url, save_path, expected_sha256=(sha256 or "").strip(),
                    progress_cb=on_progress)
                def done():
                    set_fw_progress(100 if ok else 0)
                    set_fw_status(("✓ 已下载: %s\n%s\nSHA256: %s"
                                   % (save_path, msg, sha)) if ok else
                                  ("✗ 下载失败\n%s" % msg))
                    if ok:
                        self._log("已下载固件: %s" % save_path)
                self.after(0, done)
            threading.Thread(target=work, daemon=True).start()

        # 默认先填一次中继步骤 + 尝试查固件(用已保存品牌)
        refresh_relay_guide()
        refresh_firmware_lookup()


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
                    "已为你打开「系统设置 → 通用 → 共享」。\n\n"
                    "在这里只需要一步：\n"
                    "① 打开「互联网共享」开关  →  选择「Wi‑Fi」共享给\n"
                    "② 点「Wi‑Fi 选项」设置热点名称和密码\n\n"
                    "说明：macOS 出于安全不开放自动开启，需在此页面手动确认一次；"
                    "开启后手机/平板连该热点即上网，只占电脑 1 个校园网名额。")
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


