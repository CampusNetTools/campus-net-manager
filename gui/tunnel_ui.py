# -*- coding: utf-8 -*-
"""隧道共享 UI Mixin (自 app_gui.py 拆分)"""
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


class TunnelUiMixin:
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
            # 防蹭网: 生成/复用共享口令。默认开启口令校验, 仅记住口令的设备能访问。
            self.tunnel_shared_key = self.cfg.get("tunnel_shared_key") or core.gen_tunnel_key()
            self.cfg["tunnel_shared_key"] = self.tunnel_shared_key
            core.save_config(self.cfg)
            self.proxy = shared_proxy.SharedProxy(port=8080, allowed=allowed,
                                                  on_ask=self._ask_tunnel_allow,
                                                  pac_host=myip,
                                                  shared_key=self.tunnel_shared_key,
                                                  upstream_proxy=self._get_vpn_upstream())
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
        win.geometry("620x560")
        win.resizable(False, False)
        win.transient(self)
        win.grab_set()
        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 22))
        card.pack(fill="both", expand=True, padx=18, pady=18)
        ttk.Label(card, text="隧道已经准备好", style="Section.TLabel").pack(anchor="w")
        gm = core.detect_gateway_mode()
        gm_txt = ""
        if gm["mode"] == "router":
            gm_txt = "检测到当前经路由器接入（%s）\n手机连路由器 Wi‑Fi 即可直接上网，无需代理；\n若需跨网段借网，可用下方代理。" % gm["description"]
        elif gm["mode"] == "computer":
            gm_txt = "检测到电脑直连网络\n手机/平板通过代理借用电脑网络上网。"
        status_text = ("服务自检通过，自动配置地址已复制。\n\n%s" % gm_txt if verified else
                       "服务已启动，但局域网自检未通过；请检查防火墙。\n\n%s" % gm_txt)
        ttk.Label(card, text=status_text,
                  style="Muted.TLabel", justify="left", wraplength=480).pack(anchor="w", pady=(5, 18))

        content = ttk.Frame(card, style="Inner.TFrame")
        content.pack(fill="both", expand=True)
        left = ttk.Frame(content, style="Inner.TFrame")
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="手机自动代理地址", style="Field.TLabel").pack(anchor="w")
        value = ttk.Entry(left)
        value.insert(0, pac_url)
        value.configure(state="readonly")
        value.pack(fill="x", pady=(6, 14))

        guide = (
            "手机与电脑连接同一 Wi‑Fi 后：\n"
            "Wi‑Fi 详情  →  配置代理  →  自动  →  粘贴上面的地址。\n\n"
            "没有“自动”选项时，改用手动代理：\n"
            "服务器 %s    端口 8080\n\n"
            "首次访问时，本机会询问是否允许该设备。\n"
            "防蹭网口令：%s\n"
            "（连接时需在代理头带上该口令）"
            % (myip, self.tunnel_shared_key))
        ttk.Label(left, text=guide, style="Card.TLabel", justify="left", wraplength=380).pack(anchor="w")

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
        # 一键部署: 自动开启开机自启, 让隧道长期在线(日常主力)
        ttk.Button(actions, text="🚀 一键部署(自动开启+开机自启)", style="Accent.TButton",
                   command=lambda: self._deploy_tunnel(win, myip, pac_url, setup_url)).pack(side="left")
        ttk.Button(actions, text="复制配置地址", style="Gray.TButton",
                   command=lambda: self._copy_text(pac_url)).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="VPN 上游", style="Gray.TButton",
                   command=self._show_vpn_upstream_dialog).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="完成", style="Gray.TButton", command=win.destroy).pack(side="right")


    def _deploy_tunnel(self, win, myip, pac_url, setup_url):
        """一键部署: 自动开启开机自启, 让隧道长期在线; 提示用户手机扫码连接。"""
        ok = core.set_autostart(True)
        if ok:
            self.var_auto.set(True)
            self._update_auto_btn()
            self._log("一键部署: 已开启开机自启, 隧道将长期在线")
            messagebox.showinfo(
                "🚀 一键部署完成",
                "已自动开启开机自启，隧道会长期在线。\n\n"
                "手机扫码后按提示点一次「安装/保存」即可连上，"
                "之后连同一个 Wi‑Fi 会自动生效，无需重复设置。\n\n"
                "（防蹭网口令已内置在二维码中）")
        else:
            messagebox.showerror("部署失败", "开启开机自启失败（可能需要权限），请手动开启开机自启。")


    def _get_vpn_upstream(self):
        """读取配置的 VPN 上游代理 (供隧道共享把设备流量转给 VPN)。
        返回 None 表示不使用上游; 否则 dict {host, port, type}。"""
        vpn = self.cfg.get("vpn_upstream") or {}
        host = (vpn.get("host") or "").strip()
        port = vpn.get("port")
        if not host or not port:
            return None
        try:
            port = int(port)
        except Exception:
            return None
        return {"host": host, "port": port, "type": vpn.get("type") or "http"}


    def _show_vpn_upstream_dialog(self):
        """VPN 上游代理配置对话框。"""
        import tkinter.simpledialog as simpledialog
        win = tk.Toplevel(self)
        win.title("VPN 上游代理")
        win.configure(bg=BG)
        win.geometry("460x300")
        win.transient(self)
        win.grab_set()
        card = ttk.Frame(win, style="Card.TFrame", padding=(22, 18))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="VPN 上游代理", style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(card, text="开启后，接入隧道的设备流量会经你的 VPN 转发，实现\"电脑当网关+VPN全透明\"。\n"
                  "填你本机 VPN 客户端（如 Clash/机场）的 HTTP 代理端口即可（通常 127.0.0.1:7890）。\n"
                  "留空则设备直连外网。",
                  style="Muted.TLabel", justify="left", wraplength=400).pack(anchor="w", pady=(4, 12))
        vpn = self.cfg.get("vpn_upstream") or {}
        def make_row(label, val):
            row = ttk.Frame(card, style="Inner.TFrame")
            row.pack(fill="x", pady=4)
            ttk.Label(row, text=label, style="Field.TLabel", width=10).pack(side="left")
            ent = ttk.Entry(row)
            ent.insert(0, val)
            ent.pack(side="left", fill="x", expand=True, padx=(8, 0))
            return ent
        e_host = make_row("主机", vpn.get("host", "127.0.0.1"))
        e_port = make_row("端口", vpn.get("port", "7890"))
        def save():
            host = e_host.get().strip()
            port = e_port.get().strip()
            if host and port:
                try:
                    int(port)
                except Exception:
                    messagebox.showwarning("端口无效", "端口必须是数字", parent=win)
                    return
                self.cfg["vpn_upstream"] = {"host": host, "port": port, "type": "http"}
            else:
                self.cfg.pop("vpn_upstream", None)
            core.save_config(self.cfg)
            self._log("VPN 上游代理: %s" % (host and ("%s:%s" % (host, port)) or "已关闭"))
            win.destroy()
        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.pack(fill="x", side="bottom", pady=(14, 0))
        ttk.Button(actions, text="保存并应用", style="Accent.TButton", command=save).pack(side="right")
        ttk.Button(actions, text="取消", style="Gray.TButton", command=win.destroy).pack(side="right", padx=(0, 8))


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


