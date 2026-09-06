# -*- coding: utf-8 -*-
"""「路由器代理」独立窗口 Mixin (v4.0.4 新增)。

目标: 路由器(自身完成校园网认证) → 路由器开 HTTP 代理 (默认 8080)
→ 手机连路由器 WiFi 不登录 → 手机手动代理到「路由器 IP:8080」即上网。

窗口职责:
  1. 自动识别路由器品牌/型号/硬件版本 (复用 core.router_fingerprint)
  2. 列出适配的 OpenWrt/Padavan/Merlin/iKuaiOS 官方固件入口 (复用 lookup_firmware_urls)
  3. 在线探测路由器 8080 是否已在跑 HTTP 代理 (HTTP HEAD 探测)
  4. 生成 PAC URL / 手动代理配置 / 设置页链接 / QR 码, 给手机一键接入
  5. 路由器还没起代理时: 引导刷固件 + 装插件 (按品牌给 OpenWrt luci-app-squid / Padavan 内置代理 步骤)
"""
import os
import socket
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from urllib import request as urlrequest
from urllib.error import URLError

import keepalive_core as core
import shared_proxy
from PIL import Image, ImageTk

from gui.theme import *  # noqa: F401,F403

try:
    import qrcode
    HAS_QR = True
except Exception:
    HAS_QR = False


# 路由器常见的 HTTP 代理端口列表 (探测时逐个尝试)
_ROUTER_PROXY_PORTS = [8080, 8888, 1080, 3128, 9090]
# 探测超时 (秒)
_PROBE_TIMEOUT = 1.6


def probe_router_proxy(ip, ports=None, timeout=_PROBE_TIMEOUT):
    """探测路由器 IP 上某端口是否在跑 HTTP 代理。

    判定: 能连上且返回的 HTTP 头像代理 (有 Proxy-Authenticate / Via / Server: squid|privoxy 等)
    或 HEAD 一个 http:// 资源能拿到 40x (代理会替换原始 404)。

    返回 dict: {ip, port, is_proxy, banner, latency_ms, error}
    """
    ports = ports or _ROUTER_PROXY_PORTS
    for port in ports:
        result = {"ip": ip, "port": port, "is_proxy": False, "banner": "",
                  "latency_ms": 0, "error": ""}
        try:
            sock = socket.create_connection((ip, port), timeout=timeout)
        except (socket.timeout, OSError) as e:
            result["error"] = "无法连接: %s" % e
            continue
        try:
            sock.settimeout(timeout)
            req = (
                "HEAD http://example.com/ HTTP/1.1\r\n"
                "Host: %s:%d\r\n"
                "User-Agent: CampusNetManager-RouterProbe/1.0\r\n"
                "Connection: close\r\n\r\n" % (ip, port)
            ).encode("ascii", "ignore")
            sock.sendall(req)
            buf = b""
            while b"\r\n\r\n" not in buf and len(buf) < 4096:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            sock.close()
            head = buf.decode("iso-8859-1", "ignore").split("\r\n\r\n", 1)[0]
            latency = 0  # 简化: 不算精确延迟
            result["latency_ms"] = latency
            head_lc = head.lower()
            proxy_signals = (
                "proxy-authenticate",  # 代理要求认证
                "via: ",                # 标准代理 Via 头
                "server: squid", "server: privoxy", "server: tinyproxy",
                "server: mikrotik", "server: padavan", "server: merlin",
                "server: openwrt",
                "x-cache",              # 缓存代理特征
            )
            for sig in proxy_signals:
                if sig in head_lc:
                    result["is_proxy"] = True
                    break
            # 也接受 HEAD 拿到 4xx/5xx 且头里有 Server 字段
            if not result["is_proxy"]:
                if "server:" in head_lc and head_lc.startswith("http/1."):
                    # 多数家用路由器 80/8080 也会返回 Server 头, 但通常代理会触发 4xx
                    first_line = head_lc.split("\r\n", 1)[0]
                    if any(code in first_line for code in (" 400 ", " 403 ", " 502 ", " 503 ")):
                        # 400/502/503 + Server 头有可能是代理 (代理无法解析目标)
                        # 但路由器后台也可能返回这些, 不做强判定, 只在 banner 含代理关键词时为真
                        banner = ""
                        for line in head.split("\r\n"):
                            if line.lower().startswith("server:"):
                                banner = line.split(":", 1)[1].strip()
                                break
                        result["banner"] = banner
                        if any(k in banner.lower() for k in ("squid", "privoxy", "tinyproxy",
                                                              "mikrotik", "padavan", "merlin",
                                                              "openwrt", "polipo")):
                            result["is_proxy"] = True
            if not result["banner"]:
                for line in head.split("\r\n"):
                    if line.lower().startswith("server:"):
                        result["banner"] = line.split(":", 1)[1].strip()
                        break
        except Exception as e:
            result["error"] = "读取失败: %s" % e
        if result["is_proxy"] or (not result["error"] and result["banner"]):
            return result
    return {"ip": ip, "port": ports[0] if ports else 8080, "is_proxy": False,
            "banner": "", "latency_ms": 0,
            "error": "%d 个端口都未探测到 HTTP 代理特征" % len(ports)}


def build_router_pac(host, port):
    """生成路由器代理的 PAC 字符串: 所有流量都走路由器代理。"""
    return (
        "function FindProxyForURL(url, host) {\n"
        "  return 'PROXY %s:%d; SOCKS5 %s:%d; DIRECT';\n"
        "}\n" % (host, port, host, port)
    )


class RouterProxyMixin:
    def show_router_proxy_window(self):
        """「路由器代理」窗口 — 路由器自身开 HTTP 代理, 手机走代理到路由器。

        与「路由器中继」(WISP) 的区别:
          - 中继 = 路由器用 WDS/WISP 把上游 WiFi 转给下挂设备 (路由器本身也认证, 占 1 名额)
          - 代理 = 路由器自己认证 + 自己开 8080 端口 HTTP 代理, 手机走代理 (路由器自身认证, 占 1 名额)
        两种都「占 1 个校园网账号名额」, 但代理方案对路由器固件要求更高 (需支持自定义服务),
        中继方案只要求支持 WISP/WDS (几乎所有家用路由器都行)。
        """
        win = tk.Toplevel(self)
        win.title("路由器代理: 路由器自身开 HTTP 代理 · 手机不认证走代理")
        win.configure(bg=BG)
        win.geometry("880x820")
        win.minsize(820, 720)
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

        # 标题
        ttk.Label(scroll_frame,
                  text="路由器代理 · 路由器自身开 HTTP 代理",
                  style="DialogTitle.TLabel").pack(anchor="w")
        ttk.Label(scroll_frame,
                  text=("原理: 路由器直连校园网并完成认证 → 路由器自身开 HTTP 代理 (默认 8080) → "
                        "手机连路由器 WiFi 但不登录校园网 → 手动代理到「路由器 IP:8080」即上网。\n"
                        "相比「路由器中继 (WISP)」: 路由器固件要求更高 (需支持自定义服务) 但下挂设备无需任何配置, "
                        "且路由器可以统一做国内外分流。"),
                  style="Muted.TLabel", justify="left", wraplength=780).pack(
            anchor="w", pady=(6, 16))

        state = {"report": None, "lookup": None, "probe": None, "router_ip": "192.168.1.1",
                 "port": "8080"}

        # ========== A. 路由器识别 + 适配固件查询 ==========
        card_a = ttk.Frame(scroll_frame, style="Inner.TFrame")
        card_a.pack(fill="x", pady=(0, 16))
        ttk.Label(card_a, text="A. 识别路由器品牌 / 查适配固件",
                  style="Section.TLabel").pack(anchor="w")

        info_box = tk.Text(card_a, height=6, bg="#09101c", fg="#b7c4d8",
                           font=("PingFang SC", 10), relief="flat", wrap="word",
                           padx=12, pady=10, state="disabled")
        info_box.pack(fill="x", pady=(6, 8))

        fw_box = tk.Text(card_a, height=8, bg="#09101c", fg="#b7c4d8",
                         font=("PingFang SC", 10), relief="flat", wrap="word",
                         padx=12, pady=10, state="disabled")
        fw_box.pack(fill="x", pady=(0, 8))

        a_actions = ttk.Frame(card_a, style="Inner.TFrame")
        a_actions.pack(fill="x")

        def set_info(text):
            info_box.configure(state="normal")
            info_box.delete("1.0", "end")
            info_box.insert("1.0", text)
            info_box.configure(state="disabled")

        def set_fw(text):
            fw_box.configure(state="normal")
            fw_box.delete("1.0", "end")
            fw_box.insert("1.0", text)
            fw_box.configure(state="disabled")

        def do_detect():
            set_info("正在探测路由器...\n")
            threading.Thread(target=_do_detect_bg, daemon=True).start()

        def _do_detect_bg():
            try:
                report = core.router_fingerprint()
                state["report"] = report
                gw = core.detect_gateway_mode()
                if gw.get("gateway"):
                    state["router_ip"] = gw["gateway"]
                brand = report.get("brand") or "未识别"
                model = report.get("model") or ""
                revision = report.get("revision") or ""
                admin = report.get("admin_url") or ""
                msg = ("识别结果:\n"
                       "  品牌: %s\n"
                       "  型号: %s\n"
                       "  硬件版本: %s\n"
                       "  网关: %s\n"
                       "  MAC: %s\n"
                       "  管理入口: %s\n"
                       % (brand, model, revision, gw.get("gateway", ""),
                          report.get("gateway_mac", ""), admin or "(未识别)"))
                self.after(0, lambda: set_info(msg))
                # 触发固件查询
                lookup = core.lookup_firmware_urls(brand, model, revision)
                state["lookup"] = lookup
                fw_msg = ("固件适配入口:\n"
                          "  厂商搜索: %s\n"
                          "  OpenWrt ToH: %s\n"
                          % (lookup.get("vendor_url") or "(无)",
                             lookup.get("openwrt_toh") or "(无)"))
                if lookup.get("merlin_url"):
                    fw_msg += "  Merlin (华硕): %s\n" % lookup["merlin_url"]
                fw_msg += "\n说明: %s" % (lookup.get("note") or "")
                self.after(0, lambda: set_fw(fw_msg))
                self.after(0, lambda: ip_var.set(state["router_ip"]))
            except Exception as e:
                self.after(0, lambda: set_info("探测失败: %s" % e))

        ttk.Button(a_actions, text="🔍 识别我的路由器", style="Accent.TButton",
                   command=do_detect).pack(side="left")

        def open_vendor():
            lookup = state["lookup"] or {}
            url = lookup.get("vendor_url") or lookup.get("openwrt_toh")
            if url:
                webbrowser.open(url)
            else:
                messagebox.showwarning("暂未识别", "请先点「识别我的路由器」", parent=win)

        def open_toh():
            lookup = state["lookup"] or {}
            url = lookup.get("openwrt_toh") or "https://openwrt.org/toh/start"
            webbrowser.open(url)

        ttk.Button(a_actions, text="打开厂商官网", style="Gray.TButton",
                   command=open_vendor).pack(side="left", padx=(8, 0))
        ttk.Button(a_actions, text="OpenWrt ToH 适配表", style="Gray.TButton",
                   command=open_toh).pack(side="left", padx=(8, 0))

        # ========== B. 探测路由器 8080 端口 + 配置连接 ==========
        card_b = ttk.Frame(scroll_frame, style="Inner.TFrame")
        card_b.pack(fill="x", pady=(0, 16))
        ttk.Label(card_b, text="B. 探测路由器代理端口 + 生成 PAC / 手动代理配置",
                  style="Section.TLabel").pack(anchor="w")

        ip_row = ttk.Frame(card_b, style="Inner.TFrame")
        ip_row.pack(fill="x", pady=(6, 4))
        ttk.Label(ip_row, text="路由器 LAN IP", style="Field.TLabel").pack(side="left")
        ip_var = tk.StringVar(value=state["router_ip"])
        ttk.Entry(ip_row, textvariable=ip_var, width=18).pack(side="left", padx=(8, 0))
        ttk.Label(ip_row, text="代理端口", style="Field.TLabel").pack(side="left", padx=(14, 0))
        port_var = tk.StringVar(value=state["port"])
        ttk.Entry(ip_row, textvariable=port_var, width=8).pack(side="left", padx=(8, 0))
        ttk.Button(ip_row, text="探测", style="Accent.TButton",
                   command=lambda: threading.Thread(target=_probe_bg,
                                                     args=(ip_var.get().strip(),),
                                                     daemon=True).start()
                   ).pack(side="left", padx=(12, 0))

        probe_box = tk.Text(card_b, height=5, bg="#09101c", fg="#b7c4d8",
                            font=("PingFang SC", 10), relief="flat", wrap="word",
                            padx=12, pady=10, state="disabled")
        probe_box.pack(fill="x", pady=(8, 8))

        def set_probe(text):
            probe_box.configure(state="normal")
            probe_box.delete("1.0", "end")
            probe_box.insert("1.0", text)
            probe_box.configure(state="disabled")

        def _probe_bg(ip):
            if not ip:
                self.after(0, lambda: set_probe("请先填路由器 IP"))
                return
            self.after(0, lambda: set_probe("正在探测 %s 的 %s ..." % (ip, _ROUTER_PROXY_PORTS)))
            result = probe_router_proxy(ip)
            state["probe"] = result
            if result.get("is_proxy"):
                msg = ("✓ 探测到 HTTP 代理\n"
                       "  IP: %s\n  端口: %s\n  Banner: %s\n"
                       % (result["ip"], result["port"], result.get("banner") or "(未知)"))
                self.after(0, lambda: set_probe(msg))
                self.after(0, lambda: port_var.set(str(result["port"])))
                self.after(0, lambda: state.update({"port": str(result["port"])}))
            else:
                msg = ("✗ 未在常见端口探测到 HTTP 代理\n"
                       "  IP: %s\n  已尝试: %s\n"
                       "  提示: 如果代理在其它端口, 直接在「代理端口」框填对应端口, "
                       "或继续往下做「在路由器上启动代理」段。\n"
                       "  错误: %s" % (ip, _ROUTER_PROXY_PORTS,
                                     result.get("error") or "(无)"))
                self.after(0, lambda: set_probe(msg))

        # PAC + 手动代理配置
        cfg_row = ttk.Frame(card_b, style="Inner.TFrame")
        cfg_row.pack(fill="x", pady=(8, 6))
        pac_text = tk.Text(cfg_row, height=8, bg="#0a1424", fg="#cfe6ff",
                           font=("Menlo", 10), relief="flat", wrap="word",
                           padx=10, pady=8)
        pac_text.pack(fill="x")
        qr_holder = None
        qr_box = ttk.Frame(card_b, style="Inner.TFrame")
        qr_box.pack(fill="x", pady=(6, 0))
        if HAS_QR:
            qr_holder = tk.Label(qr_box, bg="#ffffff", bd=0)
            qr_holder.pack(side="left")
            ttk.Label(qr_box,
                      text="手机扫码直接打开 PAC URL (适合 WiFi 代理选「自动」)",
                      style="Muted.TLabel", justify="left",
                      wraplength=520).pack(side="left", padx=(12, 0))
        else:
            ttk.Label(qr_box, text="(未安装 Pillow+qrcode, 仅文字)",
                      style="Muted.TLabel").pack(side="left")

        setup_url_lbl = ttk.Label(card_b, text="(还没生成设置页)",
                                  style="Muted.TLabel", wraplength=780)
        setup_url_lbl.pack(anchor="w", pady=(6, 4))

        def gen_configs():
            ip = ip_var.get().strip()
            port = port_var.get().strip() or "8080"
            if not ip:
                messagebox.showwarning("IP 缺失", "请先填路由器 LAN IP", parent=win)
                return
            setup_url = "http://%s:%s/" % (ip, port)
            # 把 setup URL 复制到剪贴板
            try:
                self.clipboard_clear()
                self.clipboard_append(setup_url)
                self.update_idletasks()
            except Exception:
                pass
            setup_url_lbl.configure(text="设置页: %s  (已复制)" % setup_url)

            pac = build_router_pac(ip, int(port) if str(port).isdigit() else 8080)
            # 通过 data URL 形式给手机访问 PAC (路由器自身开代理不一定有 /proxy.pac)
            pac_inline = "data:application/x-ns-proxy-autoconfig;base64," + __import__("base64").b64encode(
                pac.encode("utf-8")).decode("ascii")
            cfg = ("路由器代理设置:\n"
                   "  路由器 IP: %s\n  端口: %s\n\n"
                   "PAC 文件内容 (复制到路由器 /www/proxy.pac, 或用下面 data URL):\n"
                   "%s\n"
                   "PAC data URL (手机上「自动代理」填这个, 路由器无需托管文件):\n"
                   "%s\n\n"
                   "手动代理配置:\n"
                   "  服务器: %s\n"
                   "  端口:   %s\n"
                   "  绕过:   localhost, 127.*, 10.*, 192.168.*, *.local\n"
                   % (ip, port, pac.strip(), pac_inline, ip, port))
            pac_text.delete("1.0", "end")
            pac_text.insert("1.0", cfg)
            if HAS_QR and qr_holder is not None:
                try:
                    qr_image = qrcode.make(pac_inline).resize((130, 130))
                    photo = ImageTk.PhotoImage(qr_image)
                    qr_holder.configure(image=photo)
                    qr_holder.image = photo
                except Exception:
                    pass

        def copy_pac_data_url():
            ip = ip_var.get().strip()
            port_str = port_var.get().strip() or "8080"
            try:
                port_int = int(port_str)
            except ValueError:
                port_int = 8080
            import base64 as _b64
            pac = build_router_pac(ip, port_int).encode("utf-8")
            data_url = "data:application/x-ns-proxy-autoconfig;base64," + _b64.b64encode(pac).decode("ascii")
            self._copy_text(data_url)

        cfg_actions = ttk.Frame(card_b, style="Inner.TFrame")
        cfg_actions.pack(fill="x", pady=(8, 0))
        ttk.Button(cfg_actions, text="生成 PAC + 手动代理配置 + 设置页",
                   style="Accent.TButton", command=gen_configs).pack(side="left")
        ttk.Button(cfg_actions, text="复制 PAC data URL",
                   style="Gray.TButton",
                   command=copy_pac_data_url).pack(side="left", padx=(8, 0))

        # ========== C. 在路由器上启动代理 (按固件分步) ==========
        card_c = ttk.Frame(scroll_frame, style="Inner.TFrame")
        card_c.pack(fill="x", pady=(0, 16))
        ttk.Label(card_c, text="C. 在路由器上启动 HTTP 代理 (按固件分步)",
                  style="Section.TLabel").pack(anchor="w")

        tabs = ttk.Notebook(card_c)
        tabs.pack(fill="x", pady=(8, 0))

        def make_tab(parent, body):
            txt = tk.Text(parent, height=10, bg="#0a1424", fg="#cfe6ff",
                          font=("PingFang SC", 10), relief="flat", wrap="word",
                          padx=12, pady=10)
            txt.pack(fill="both", expand=True)
            txt.insert("1.0", body)

        # OpenWrt
        tab_owrt = ttk.Frame(tabs, style="Inner.TFrame")
        tabs.add(tab_owrt, text="OpenWrt")
        make_tab(tab_owrt, (
            "OpenWrt 18.06+ 安装 HTTP 代理 (推荐 luci-app-squid 或 tinyproxy):\n\n"
            "1. SSH 登录路由器 (默认 192.168.1.1, 端口 22):\n"
            "   ssh root@192.168.1.1\n\n"
            "2. 安装 tinyproxy (轻量, 推荐校园网):\n"
            "   opkg update && opkg install tinyproxy\n\n"
            "3. 编辑 /etc/config/tinyproxy:\n"
            "   config tinyproxy\n"
            "       option Port 8080\n"
            "       option Allow 192.168.0.0/16\n"
            "       option Allow 10.0.0.0/8\n"
            "       option Allow 172.16.0.0/12\n\n"
            "4. 启动:\n"
            "   /etc/init.d/tinyproxy enable\n"
            "   /etc/init.d/tinyproxy start\n\n"
            "5. 在防火墙 (Firewall → Traffic Rules) 放行 8080/TCP。\n\n"
            "※ 想做国内外分流可在 OpenWrt 上加 passwall / shadowsocks-libev + luci-app-shadowsocks。\n"
            "※ Web 界面版 (luci-app-squid) 在 LuCI → Services → Squid。\n"
        ))

        # Padavan
        tab_pad = ttk.Frame(tabs, style="Inner.TFrame")
        tabs.add(tab_pad, text="Padavan (老毛子)")
        make_tab(tab_pad, (
            "Padavan (老毛子固件, 常见于斐讯 K2P / 小米 R3) 内置 HTTP 代理:\n\n"
            "1. 登录路由器管理页 → 高级设置 → 系统管理 → 服务\n"
            "2. 找到 「HTTP 代理」 / 「Squid」 / 「Tinyproxy」 启用开关 → 打开\n"
            "3. 端口填 8080\n"
            "4. 允许网段填 192.168.0.0/16\n"
            "5. 应用 → 路由器自动启动代理\n\n"
            "※ 不同 Padavan 编译版本菜单略有差异, 找不到「HTTP 代理」就先到\n"
            "   「扩展功能」 → 「脚本」 里手写启动命令:\n"
            "   tinyproxy -c /etc/tinyproxy.conf -d\n"
            "※ 防火墙: 「安全设置 → 防火墙」放行 8080/TCP。\n"
        ))

        # Merlin
        tab_merlin = ttk.Frame(tabs, style="Inner.TFrame")
        tabs.add(tab_merlin, text="Merlin (华硕)")
        make_tab(tab_merlin, (
            "Asuswrt-Merlin (华硕路由器):\n\n"
            "1. 路由器管理页 → 「USB 应用」 → 「Download Master」 安装 entware\n"
            "2. SSH 登录 → opkg install tinyproxy\n"
            "3. 编辑 /opt/etc/tinyproxy/tinyproxy.conf:\n"
            "   Port 8080\n"
            "   Allow 192.168.0.0/16\n"
            "4. 启动: /opt/etc/init.d/S80tinyproxy start\n\n"
            "或者用 Merlin 自带的「JFFS 脚本」:\n"
            "   Administration → System → Persistent JFFS2 partition → Enable\n"
            "   在 /jffs/scripts/services-start 末尾加:\n"
            "     #!/bin/sh\n"
            "     tinyproxy -c /jffs/config/tinyproxy.conf -d &\n\n"
            "※ 防火墙: 「Firewall → IPv4 Firewall」 加 8080/TCP ACCEPT。\n"
        ))

        # iKuaiOS
        tab_ikuai = ttk.Frame(tabs, style="Inner.TFrame")
        tabs.add(tab_ikuai, text="iKuaiOS (爱快)")
        make_tab(tab_ikuai, (
            "iKuaiOS (爱快路由):\n\n"
            "1. 登录爱快管理页 → 「系统设置」 → 「高级设置」\n"
            "2. 「HTTP 代理」 / 「Squid」 启用 (部分版本需在「插件中心」先装 Squid 插件)\n"
            "3. 端口 8080, 允许网段 192.168.0.0/16\n"
            "4. 应用 → 重启路由\n\n"
            "※ 商业路由系统通常代理功能有限, 推荐改刷 OpenWrt 获得完整体验。\n"
        ))

        # 通用 fallback
        tab_other = ttk.Frame(tabs, style="Inner.TFrame")
        tabs.add(tab_other, text="其它 / 不确定")
        make_tab(tab_other, (
            "不确定路由器能不能装代理? 三个快速判断:\n\n"
            "1. 看「路由器检测」窗口 → 品牌/型号 → 浏览器搜「<品牌> <型号> OpenWrt 适配」\n"
            "2. 进 https://openwrt.org/toh/start 查 ToH (Table of Hardware)\n"
            "3. 看「路由器中继」窗口里的固件查询段\n\n"
            "常见可刷 OpenWrt 的品牌: 斐讯 K2/K2P/K3 / 小米 R3/R4 / 极路由 / TP-LINK 部分型号 /\n"
            "华硕 (Merlin 基于 Asuswrt) / 网件 (Netgear) 部分型号 / 红米 / 360 / 联想 Newifi。\n\n"
            "刷机有风险, 请:\n"
            "  - 确认型号精确匹配, 错刷会变砖\n"
            "  - 用网线刷, 绝不 WiFi 刷\n"
            "  - 备份原厂固件 (breed / uboot)\n"
            "  - 第一次刷机建议找同型号教程贴逐行对照\n\n"
            "我能帮你做的事: 品牌识别 + 固件入口查询 + 步骤生成; "
            "具体刷机风险自己评估。\n"
        ))

        # ========== D. 手机端配置步骤 ==========
        card_d = ttk.Frame(scroll_frame, style="Inner.TFrame")
        card_d.pack(fill="x", pady=(0, 16))
        ttk.Label(card_d, text="D. 手机端配置 (iOS / Android)",
                  style="Section.TLabel").pack(anchor="w")

        phone_box = tk.Text(card_d, height=10, bg="#09101c", fg="#b7c4d8",
                            font=("PingFang SC", 10), relief="flat", wrap="word",
                            padx=12, pady=10, state="disabled")
        phone_box.pack(fill="x", pady=(6, 8))

        def set_phone(text):
            phone_box.configure(state="normal")
            phone_box.delete("1.0", "end")
            phone_box.insert("1.0", text)
            phone_box.configure(state="disabled")

        def fill_phone():
            ip = ip_var.get().strip()
            port = port_var.get().strip() or "8080"
            if not ip:
                messagebox.showwarning("IP 缺失", "请先填路由器 IP", parent=win)
                return
            base = ("前置: 手机连路由器的 WiFi (不需要登录校园网, "
                    "WiFi 认证页面关掉即可)。\n\n")
            ios = ("【iOS】\n"
                   "  1. 设置 → Wi-Fi → 点已连的路由器 WiFi 右边 ⓘ\n"
                   "  2. 拉到最下 → 「配置代理」→ 「手动」\n"
                   "  3. 服务器: %s   端口: %s\n"
                   "  4. 如需认证, 关闭「鉴定」或填路由器后台设的用户名密码\n"
                   "  5. 存储 → 打开 Safari 访问任意网站测试\n\n" % (ip, port))
            and_ = ("【Android】(以 MIUI / OneUI / 原生为例, 各家菜单类似)\n"
                    "  1. 设置 → WLAN → 长按 / 编辑当前 WiFi → 高级选项\n"
                    "  2. 代理 → 「手动」\n"
                    "  3. 代理主机名: %s   代理端口: %s\n"
                    "  4. 绕过内网: 填 ,localhost,127.*,10.*,192.168.*\n"
                    "  5. 保存 → 打开浏览器测试\n\n"
                    "  ※ 想用 PAC 自动代理: 把「代理」切到「自动」, "
                    "「PAC URL」填上方生成的 data URL (用「复制 PAC data URL」按钮)。\n\n" % (ip, port))
            common = ("【通用提示】\n"
                      "  • 手机不会登录校园网 = 不会产生账号并发 = 不会触发学校反共享检测。\n"
                      "  • 路由器自身的 NAT/认证 只算 1 个名额, 下挂多少手机都共享这 1 个名额。\n"
                      "  • 出故障: 在本窗口点「探测」, 确认路由器 8080 还在跑代理。\n"
                      "  • HTTPS 网站需要路由器代理支持 CONNECT 方法 (squid/tinyproxy 都默认支持)。\n")
            set_phone(base + ios + and_ + common)

        d_actions = ttk.Frame(card_d, style="Inner.TFrame")
        d_actions.pack(fill="x")
        ttk.Button(d_actions, text="填充手机配置步骤 (按当前 IP/端口)",
                   style="Accent.TButton", command=fill_phone).pack(side="left")

        # ========== 底部按钮 ==========
        actions = ttk.Frame(scroll_frame, style="Inner.TFrame")
        actions.pack(fill="x", pady=(20, 6))
        ttk.Button(actions, text="完成", style="Gray.TButton",
                   command=win.destroy).pack(side="right")
        ttk.Button(actions, text="打开路由器管理页",
                   style="Gray.TButton",
                   command=lambda: (state["report"] and webbrowser.open(
                       state["report"].get("admin_url") or "")) or messagebox.showwarning(
                           "暂未识别", "请先点「识别我的路由器」", parent=win)
                   ).pack(side="right", padx=(0, 8))