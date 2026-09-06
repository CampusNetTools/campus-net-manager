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
    def _stop_share(self):
        """停止隧道共享并同步界面按钮。"""
        if self.proxy and self.proxy.running:
            self.proxy.stop()
            allow = sorted(self.proxy.allowed)
            if allow != list(self.cfg.get("tunnel_allow", [])):
                self.cfg["tunnel_allow"] = allow
                core.save_config(self.cfg)
            self._log("隧道共享已停止 (授权设备 %d 台已记住)" % len(allow))
        self.proxy = None
        btn = getattr(self, "btn_share", None)
        if btn is not None:
            try:
                if btn.winfo_exists():
                    btn.configure(text="隧道共享", style="Gray.TButton")
            except Exception:
                pass

    def toggle_share(self):
        """隧道共享: 其他设备(手机/平板)借本机网络访问外网 (带访问控制)"""
        if self.proxy and self.proxy.running:
            self._stop_share()
            return
        try:
            allowed = list(self.cfg.get("tunnel_allow", []))
            ips = shared_proxy.get_lan_ips()
            myip = ips[0] if ips else None
            # v4.0.5: 默认不再强制开启「防蹭网口令」。
            # 原因: PAC/手动代理客户端(iOS/Android)无法附加自定义 HTTP 头 (X-Shared-Key),
            # 默认开启会导致所有手机/平板请求被 407 拒绝, 普通用户根本无法走通。
            # 现在: 只有用户在隧道共享窗口里显式勾选「启用口令保护」时, 才生成口令。
            # 兼容: 如果历史配置里已经存在 tunnel_shared_key (v4.0.4 强制写过),
            #       自动读取, 不主动清空, 避免破坏「已开启口令保护」的用户。
            if self.cfg.get("tunnel_require_key"):
                self.tunnel_shared_key = self.cfg.get("tunnel_shared_key") or core.gen_tunnel_key()
                self.cfg["tunnel_shared_key"] = self.tunnel_shared_key
            else:
                # 没勾选: 内存里也不带口令(代理直接放行任何同网段设备)。
                self.tunnel_shared_key = None
                # 但保留磁盘上的旧 key (用户随时可以再勾回来用)。
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
        """用应用内统一样式展示一键隧道结果，避免系统消息框拥挤。

        两种上游模式都集成进本窗口:
          ① 路由器模式 (电脑经路由器/中继接入校园网):
             手机直接连那台路由器的 WiFi 即可借校园网出口, 无需配代理;
             也可走电脑的隧道共享 (跨网段/不同 WiFi 时)。
          ② 电脑模式 (电脑本身直连校园网):
             手机必须配电脑的 HTTP 代理 (同 WiFi 或电脑热点) 才能借出口;
             不配代理则等于 "无网络"。
        支持多网卡环境下手动切换给手机填的服务器 IP。"""
        win = tk.Toplevel(self)
        win.title("隧道共享")
        win.configure(bg=BG)
        win.geometry("760x780")
        win.minsize(700, 660)
        win.resizable(True, True)
        win.transient(self)
        win.grab_set()

        # 外层滚动容器(便于内容超出屏幕时)
        canvas = tk.Canvas(win, bg=BG, highlightthickness=0)
        scrollbar = ttk.Scrollbar(win, orient="vertical", command=canvas.yview)
        scroll_frame = ttk.Frame(canvas, style="Card.TFrame", padding=(28, 24))
        scroll_frame.bind("<Configure>",
                          lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        canvas.bind("<MouseWheel>",
                    lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))

        # 顶部: 标题 + 概要状态
        ttk.Label(scroll_frame, text="隧道已经准备好",
                  style="DialogTitle.TLabel").pack(anchor="w")
        gm = core.detect_gateway_mode()
        mode = gm["mode"]
        if mode == "router":
            top_status = ("✓ 服务自检通过。" if verified else
                          "⚠ 服务已启动，但局域网自检未通过；请检查防火墙。")
            top_desc = ("检测到: %s\n\n"
                        "这种模式下, 手机直接连那台路由器的 WiFi 就能借校园网出口上网, "
                        "不需要配代理。下面一段会自动隐藏「需要配代理」的步骤, "
                        "转成「已能直接上网」说明。"
                        % gm["description"])
        elif mode == "computer":
            top_status = ("✓ 服务自检通过。" if verified else
                          "⚠ 服务已启动，但局域网自检未通过；请检查防火墙。")
            top_desc = ("检测到: %s\n\n"
                        "这种模式下, 手机与电脑如果在不同 WiFi, 手机必须配电脑的 "
                        "HTTP 代理 才能借校园网出口上网。"
                        % gm["description"])
        else:
            top_status = ("✓ 服务已启动。" if verified else
                          "⚠ 服务已启动，但局域网自检未通过。")
            top_desc = "未识别上游模式。下面两条独立方案按你实际情况选用。"
        ttk.Label(scroll_frame, text=top_status, style="Muted.TLabel",
                  justify="left").pack(anchor="w", pady=(6, 0))
        ttk.Label(scroll_frame, text=top_desc, style="Muted.TLabel",
                  justify="left", wraplength=680).pack(anchor="w", pady=(4, 18))

        st = {"ip": myip, "pac": pac_url, "setup": setup_url}
        cands = shared_proxy.get_lan_ips() or [myip]
        if myip not in cands:
            cands.insert(0, myip)

        addr_btn_holder = {"btn": None}

        def refresh_addr_btn():
            btn = addr_btn_holder["btn"]
            if btn is None:
                return
            try:
                btn.configure(text="电脑地址: %s ▾  (适用代理模式)" % st["ip"])
            except Exception:
                pass

        def apply_ip(ip):
            """切换到另一张网卡的地址: 更新 PAC host + 界面。"""
            st["ip"] = ip
            st["pac"] = "http://%s:8080/proxy.pac" % ip
            st["setup"] = "http://%s:8080/" % ip
            if getattr(self, "proxy", None) is not None:
                try:
                    self.proxy.pac_host = ip
                except Exception:
                    pass
            refresh_addr_btn()
            render_qr()
            self._log("隧道地址已切换为: %s:8080 (请按新地址配置手机)" % ip)

        # ---------- ① 路由器模式卡 ----------
        router_card = ttk.Frame(scroll_frame, style="Inner.TFrame")
        router_card.pack(fill="x", pady=(0, 16))
        ttk.Label(router_card, text="① 路由器中继(手机连路由器 WiFi)",
                  style="Section.TLabel").pack(anchor="w")
        if mode == "router":
            router_body = (
                "✓ 当前已是路由器模式。手机直接连那台路由器的 WiFi 就能借校园网出口, "
                "**不用配任何代理**。\n\n"
                "如果你仍希望走本软件代理(有跨网段、防蹭网、鉴权通行等需要), "
                "向下滚到 ② 段, 那里是手动代理 + 扫码配置。\n\n"
                "路由器自身也能开 PAC(在本应用「路由器中继」窗口里有教)。"
            )
        else:
            router_body = (
                "如果手机与你电脑在同一台路由器下:\n"
                "  • 直接让手机连那台路由器的 WiFi 即可上网——无需本软件隧道。\n"
                "  • 若路由器已中继校园网(路由器自身已认证), 那么手机属于校园网覆盖范围。\n\n"
                "若路由器还没中继校园网 / 手机不在路由器覆盖范围:\n"
                "  ↓ 向下滚到 ② 段「电脑直接接入(手机配代理)」"
            )
        ttk.Label(router_card, text=router_body, style="Card.TLabel",
                  justify="left", wraplength=680).pack(anchor="w", pady=(6, 8))

        # ---------- ② 电脑模式卡 ----------
        computer_card = ttk.Frame(scroll_frame, style="Inner.TFrame")
        computer_card.pack(fill="x", pady=(0, 16))
        ttk.Label(computer_card,
                  text="② 电脑直连校园网(手机配代理)",
                  style="Section.TLabel").pack(anchor="w")
        computer_header = ("**手机需要配电脑的 HTTP 代理** 才能借校园网出口上网。"
                           if mode == "computer" else
                           "如果手机不在这台路由器下, 可走电脑代理借校园网出口上网。")
        ttk.Label(computer_card, text=computer_header,
                  style="Card.TLabel", justify="left",
                  wraplength=680).pack(anchor="w", pady=(6, 8))

        # PAC + 手动代理地址
        pac_row = ttk.Frame(computer_card, style="Inner.TFrame")
        pac_row.pack(fill="x", pady=(4, 6))
        ttk.Label(pac_row, text="自动代理 (PAC)", style="Field.TLabel").pack(anchor="w")
        value = ttk.Entry(pac_row)
        value.insert(0, pac_url)
        value.configure(state="readonly")
        value.pack(fill="x", pady=(4, 4))

        manual_row = ttk.Frame(computer_card, style="Inner.TFrame")
        manual_row.pack(fill="x", pady=(4, 6))
        ttk.Label(manual_row, text="手动代理(没「自动」时用)",
                  style="Field.TLabel").pack(anchor="w")
        manual_ip = ttk.Label(manual_row,
                              text="服务器 %s · 端口 8080" % myip,
                              style="Card.TLabel", foreground=ACCENT)
        manual_ip.pack(anchor="w")
        ttk.Label(manual_row,
                  text="(首次访问时本机会弹窗询问是否允许该设备, 「允许」后自动记住)",
                  style="Muted.TLabel").pack(anchor="w", pady=(2, 0))

        # v4.0.5: 防蹭网口令开关 (默认关闭, 因为 PAC/手动代理客户端无法附加自定义 HTTP 头)
        pwd_row = ttk.Frame(computer_card, style="Inner.TFrame")
        pwd_row.pack(fill="x", pady=(10, 6))

        def _has_existing_key():
            return bool(self.cfg.get("tunnel_shared_key"))

        pwd_var = tk.BooleanVar(value=bool(self.cfg.get("tunnel_require_key")) and _has_existing_key())

        def _toggle_pwd():
            """切换口令保护开关: 关 → 重启 proxy 时不再带 shared_key;
            开 → 生成新口令并要求重启 proxy (弹窗提示)。"""
            try:
                if pwd_var.get():
                    # 用户刚勾上 → 生成新口令 + 写盘 + 重启 proxy (带 key)
                    new_key = core.gen_tunnel_key()
                    self.tunnel_shared_key = new_key
                    self.cfg["tunnel_shared_key"] = new_key
                    self.cfg["tunnel_require_key"] = True
                    core.save_config(self.cfg)
                    # 重启 proxy
                    if self.proxy and self.proxy.running:
                        host = self.proxy.pac_host or myip
                        port = self.proxy.port
                        self._stop_share()
                        self.proxy = shared_proxy.SharedProxy(
                            port=port, allowed=list(self.proxy.allowed),
                            on_ask=self._ask_tunnel_allow, pac_host=host,
                            shared_key=new_key, upstream_proxy=self._get_vpn_upstream())
                        self.proxy.start()
                        self._log("已开启口令保护, 新口令: %s" % new_key)
                    messagebox.showinfo(
                        "口令已开启",
                        "防蹭网口令: %s\n\n"
                        "手机端配 PAC/手动代理已可上网;\n"
                        "若以后想用 VPN 客户端/自定义脚本调用本机代理, "
                        "需在 HTTP 请求里附带:\n"
                        "  X-Shared-Key: %s\n\n"
                        "(关闭本开关可随时取消口令保护。)"
                        % (new_key, new_key),
                        parent=win)
                else:
                    # 用户取消勾选 → 内存里清空口令, 重启 proxy 不带 key
                    self.cfg["tunnel_require_key"] = False
                    core.save_config(self.cfg)
                    if self.proxy and self.proxy.running:
                        host = self.proxy.pac_host or myip
                        port = self.proxy.port
                        self._stop_share()
                        self.proxy = shared_proxy.SharedProxy(
                            port=port, allowed=list(self.proxy.allowed),
                            on_ask=self._ask_tunnel_allow, pac_host=host,
                            shared_key=None, upstream_proxy=self._get_vpn_upstream())
                        self.proxy.start()
                        self._log("已关闭口令保护")
            except Exception as e:
                messagebox.showerror("切换失败", str(e), parent=win)

        pwd_chk = ttk.Checkbutton(
            pwd_row,
            text="启用口令保护 (防蹭网, 需在调用方附加 X-Shared-Key 头)",
            variable=pwd_var,
            command=_toggle_pwd,
            style="TCheckbutton")
        pwd_chk.pack(side="left", anchor="w")

        if _has_existing_key() and not self.cfg.get("tunnel_require_key"):
            # v4.0.4 残留: 磁盘有口令但未开启, 提示用户
            ttk.Label(pwd_row,
                      text="(v4.0.4 残留口令, 需勾选才生效)",
                      style="Muted.TLabel",
                      foreground="#cc8800").pack(side="left", padx=(12, 0))

        ip_switch = ttk.Frame(computer_card, style="Inner.TFrame")
        ip_switch.pack(fill="x", pady=(8, 6))
        ttk.Label(ip_switch, text="多网卡时切换电脑地址:",
                  style="Muted.TLabel").pack(side="left")
        addr_btn = ttk.Button(ip_switch, text="电脑地址: %s ▾" % myip,
                              style="Gray.TButton")
        addr_btn.pack(side="left", padx=(8, 0))
        addr_btn_holder["btn"] = addr_btn
        refresh_addr_btn()
        if len(cands) > 1:
            def pop_menu():
                menu = tk.Menu(win, tearoff=0)
                for ip in cands:
                    menu.add_command(label=ip + ("  ← 推荐" if ip == st["ip"] else ""),
                                     command=lambda i=ip: apply_ip(i))
                menu.tk_popup(addr_btn.winfo_rootx(),
                              addr_btn.winfo_rooty() + addr_btn.winfo_height())
            addr_btn.configure(command=pop_menu)

        # 二维码 + 步骤教程
        qr_box = ttk.Frame(computer_card, style="Inner.TFrame")
        qr_box.pack(fill="x", pady=(8, 0))
        qr_holder = None
        if HAS_QR:
            qr_holder = tk.Label(qr_box, bg="#ffffff", bd=0)
            qr_holder.pack(side="left")
            ttk.Label(qr_box,
                      text="手机扫码直接打开设置页(含 PAC / 手动配置)",
                      style="Muted.TLabel", justify="left",
                      wraplength=420).pack(side="left", padx=(12, 0))
        else:
            ttk.Label(qr_box, text="(未安装 Pillow+qrcode, 仅显示文字步骤)",
                      style="Muted.TLabel").pack(side="left")

        def render_qr():
            if qr_holder is None or not HAS_QR:
                return
            try:
                qr_image = qrcode.make(st["setup"]).resize((130, 130))
                photo = ImageTk.PhotoImage(qr_image)
                qr_holder.configure(image=photo)
                qr_holder.image = photo
            except Exception:
                pass

        guide = ("① 手机先连与电脑互通的网络(同 WiFi, 或连电脑热点)\n"
                 "② iOS: Wi-Fi 详情 → 配置代理 → 自动 → 粘贴 PAC 地址\n"
                 "    Android: 长按已连 WiFi → 修改 → 高级 → 代理 → 切换为「自动」/「手动」→ 粘贴\n"
                 "③ 首次访问任意网页, 本机弹窗「有设备请求, 是否允许」→ 点「允许」\n"
                 "④ 之后手机直走代理借校园网出口, 在校园网覆盖范围就能上网\n")
        ttk.Label(computer_card, text=guide, style="Card.TLabel",
                  justify="left", wraplength=680).pack(anchor="w", pady=(10, 0))

        render_qr()

        # ---------- ③ 路由器代理卡 ----------
        router_proxy_card = ttk.Frame(scroll_frame, style="Inner.TFrame")
        router_proxy_card.pack(fill="x", pady=(0, 16))
        ttk.Label(router_proxy_card,
                  text="③ 路由器代理(路由器自身开 HTTP 代理, 手机走代理到路由器 IP)",
                  style="Section.TLabel").pack(anchor="w")
        rp_intro = (
            "原理: 路由器直连校园网并完成认证 → 路由器自身开 HTTP 代理 (默认 8080) → "
            "手机连路由器的 WiFi (不需要登录校园网) → 手动代理到「路由器 IP:8080」即上网。\n\n"
            "优点: ① 路由器一次性认证, 后续手机永远免登录; ② 手机 0 配置 PAC, 出国/校内分流交给路由器; "
            "③ 比「电脑一直开着 + 手机连电脑 WiFi」省一台电脑。\n"
            "前提: 路由器需刷 OpenWrt / Padavan / Merlin / iKuaiOS 等支持自定义服务的固件 "
            "(具体看主界面「路由器代理」窗口的官方固件查询和刷机教程)。"
        )
        ttk.Label(router_proxy_card, text=rp_intro, style="Card.TLabel",
                  justify="left", wraplength=680).pack(anchor="w", pady=(6, 8))

        # 路由器代理配置 UI: 路由器 IP + 端口 + 生成 PAC / 手动代理 / 打开路由器代理窗口
        rp_row = ttk.Frame(router_proxy_card, style="Inner.TFrame")
        rp_row.pack(fill="x", pady=(4, 4))
        ttk.Label(rp_row, text="路由器 LAN IP", style="Field.TLabel").pack(side="left")
        rp_ip_var = tk.StringVar(value=shared_proxy.get_lan_ips()[0]
                                  if shared_proxy.get_lan_ips() else "192.168.1.1")
        ttk.Entry(rp_row, textvariable=rp_ip_var, width=18).pack(side="left", padx=(8, 0))
        ttk.Label(rp_row, text="代理端口", style="Field.TLabel").pack(side="left", padx=(14, 0))
        rp_port_var = tk.StringVar(value="8080")
        ttk.Entry(rp_row, textvariable=rp_port_var, width=8).pack(side="left", padx=(8, 0))

        rp_actions = ttk.Frame(router_proxy_card, style="Inner.TFrame")
        rp_actions.pack(fill="x", pady=(8, 0))
        rp_state = {"url": ""}

        def gen_rp_setup():
            ip = rp_ip_var.get().strip()
            port = rp_port_var.get().strip() or "8080"
            if not ip:
                messagebox.showwarning("IP 缺失", "请先填路由器 LAN IP", parent=win)
                return
            url = "http://%s:%s/" % (ip, port)
            rp_state["url"] = url
            try:
                self.clipboard_clear()
                self.clipboard_append(url)
                self.update_idletasks()
            except Exception:
                pass
            rp_url_lbl.configure(text="设置页: %s  (已复制到剪贴板)" % url)
            if HAS_QR and rp_qr_holder is not None:
                try:
                    qr_image = qrcode.make(url).resize((110, 110))
                    photo = ImageTk.PhotoImage(qr_image)
                    rp_qr_holder.configure(image=photo)
                    rp_qr_holder.image = photo
                except Exception:
                    pass

        ttk.Button(rp_actions, text="生成路由器代理设置页 + 复制链接",
                   style="Accent.TButton", command=gen_rp_setup).pack(side="left")
        ttk.Button(rp_actions, text="打开「路由器代理」独立窗口",
                   style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy("router_proxy",
                                                           self.show_router_proxy_window)
                   ).pack(side="left", padx=(8, 0))

        rp_url_lbl = ttk.Label(router_proxy_card, text="(还没生成设置页链接)",
                                style="Muted.TLabel", wraplength=680)
        rp_url_lbl.pack(anchor="w", pady=(6, 4))

        rp_qr_box = ttk.Frame(router_proxy_card, style="Inner.TFrame")
        rp_qr_box.pack(fill="x", pady=(4, 0))
        rp_qr_holder = None
        if HAS_QR:
            rp_qr_holder = tk.Label(rp_qr_box, bg="#ffffff", bd=0)
            rp_qr_holder.pack(side="left")
            ttk.Label(rp_qr_box,
                      text="手机扫码直接打开「路由器代理」配置页 (含 PAC / 手动代理一键填)。",
                      style="Muted.TLabel", justify="left",
                      wraplength=420).pack(side="left", padx=(12, 0))
        else:
            ttk.Label(rp_qr_box, text="(未安装 Pillow+qrcode, 仅文字步骤)",
                      style="Muted.TLabel").pack(side="left")

        rp_guide = (
            "路由器代理快速上手:\n"
            "  ① 路由器先刷 OpenWrt/Padavan/Merlin/iKuaiOS (具体品牌步骤 → 「路由器代理」窗口);\n"
            "  ② 在路由器里安装 HTTP 代理插件 (OpenWrt: luci-app-squid / Padavan: 内置 HTTP 代理 "
            "/ Merlin: 自定义脚本 + nginx) 并监听 8080;\n"
            "  ③ 手机连路由器 WiFi 但**不登录校园网** → WiFi 高级 → 代理 → 手动 → 服务器填上方 IP, "
            "端口 8080 → 保存;\n"
            "  ④ 手机打开任意网页就能上网, 流量全走路由器, 路由器替手机完成校园网认证。\n"
            "  ※ 该方案**不需要本软件隧道在电脑运行**, 电脑关了也能用。"
        )
        ttk.Label(router_proxy_card, text=rp_guide, style="Card.TLabel",
                  justify="left", wraplength=680).pack(anchor="w", pady=(10, 0))

        # ---------- 常见问题 ----------
        info = ttk.Frame(scroll_frame, style="Inner.TFrame")
        info.pack(fill="x", pady=(12, 0))
        ttk.Label(info, text="常见问题: 路由模式 / 电脑模式如何选择?",
                  style="Field.TLabel").pack(anchor="w")
        ttk.Label(info,
                  text="• 路由器模式: 网关是 192.168.x.1 这类私网地址 → 手机只要在同一路由器 WiFi 下, "
                       "即可借路由器认证出口, 不需要本软件代理。\n"
                       "• 电脑模式: 电脑直接拨号校园网/有线 → 手机必须通过电脑代理借。\n"
                       "• 本窗口为「隧道共享」统一使用 8080 端口; 若多个网卡, 切换上方电脑地址即可。",
                  style="Muted.TLabel", justify="left",
                  wraplength=680).pack(anchor="w", pady=(2, 0))

        # ---------- 底部按钮区 ----------
        actions = ttk.Frame(scroll_frame, style="Inner.TFrame")
        actions.pack(fill="x", pady=(20, 6))
        ttk.Button(actions, text="🚀 一键部署(自动开启+开机自启)",
                   style="Accent.TButton",
                   command=lambda: self._deploy_tunnel(win, st["ip"], st["pac"],
                                                       st["setup"])).pack(side="left")
        ttk.Button(actions, text="复制 PAC", style="Gray.TButton",
                   command=lambda: self._copy_text(st["pac"])).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="VPN 上游", style="Gray.TButton",
                   command=self._show_vpn_upstream_dialog).pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="停止共享", style="Danger.TButton",
                   command=lambda: (self._stop_share(), win.destroy())).pack(side="right")
        ttk.Button(actions, text="完成", style="Gray.TButton",
                   command=win.destroy).pack(side="right", padx=(0, 8))
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


