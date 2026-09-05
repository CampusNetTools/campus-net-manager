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
            # 多设备泄露检测 (中继伪装)
            try:
                stealth = core.relay_stealth_check()
                risk_txt = {"low": "低（仅本机）", "mid": "中（少量设备）", "high": "高（多台设备共享）"}
                lines.append("")
                lines.append("多设备检测：%s 台设备可被看到（风险：%s）" % (
                    stealth["device_count"], risk_txt.get(stealth["risk"], stealth["risk"])))
                for device in stealth["visible_devices"][:4]:
                    lines.append("  · %s  %s  %s" % (device["ip"], device["mac"],
                                                     device["brand"] or "未知设备"))
                lines.append("轻量伪装建议（不掉速）：")
                for tip in stealth["advice"][:3]:
                    lines.append("  · %s" % tip)
            except Exception as exc:
                lines.append("")
                lines.append("多设备检测：暂不可用（%s）" % exc)
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


