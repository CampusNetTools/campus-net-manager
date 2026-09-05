# -*- coding: utf-8 -*-
"""新手向导与帮助 Mixin (自 app_gui.py 拆分)"""
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


class WizardMixin:
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
            title.configure(text="方式 B：副路由器中继扩展信号")
            set_body("副路由器的中继目标是什么？\n\n"
                     "【校园】副路由器想连接的是……\n"
                     "  ① 校园网 LIDA-UNIVERSITY（常在学校）\n\n"
                     "【家庭】副路由器想连接的是……\n"
                     "  ② 主路由器的 WiFi（主路由接光猫，常在家）\n\n"
                     "请点下方按钮选择，或点「重新检测」直接按默认(校园网)引导。\n\n"
                     "（副路由器设定中继后，会连接这个上游 WiFi，扩大信号范围）")
            btn_act.configure(text="① 校园网", command=lambda: enter_plan_b_detect("LIDA-UNIVERSITY", True))
            btn_act.pack(side="right")
            btn_act2.configure(text="② 主路由器WiFi", state="normal",
                               command=lambda: enter_plan_b_detect("主路由器的WiFi", False))
            btn_prev.pack(side="left")
            btn_prev.configure(command=lambda: show_plan_choice())

            def enter_plan_b_detect(target_ssid, need_auth):
                state["target_ssid"] = target_ssid
                state["need_auth"] = need_auth
                title.configure(text="方式 B：副路由器中继「%s」" % target_ssid)
                set_body("正在检测副路由器...\n\n（请确认电脑当前连接的是【副路由器】的 WiFi）")
                btn_act.configure(text="重新检测", state="normal",
                                  command=lambda: enter_plan_b_detect(target_ssid, need_auth))
                btn_act2.configure(state="disabled")

                def detect():
                    brand, gw, guide = core.router_guide(target_ssid, need_auth)
                    state["brand"], state["gw"], state["guide"] = brand, gw, guide
                    head = "检测到副路由器：%s\n管理地址：http://%s\n\n" % (brand or "未知品牌", gw or "无法获取")
                    if need_auth:
                        up_txt = "校园网 %s" % target_ssid
                    else:
                        up_txt = "主路由器的 WiFi「%s」" % target_ssid
                    if not gw:
                        tail = "没有检测到副路由器网关。\n请先连接【副路由器】的 WiFi（不是校园网/主路由直连），再点「重新检测」。"
                    else:
                        tail = ("👇 让副路由器中继连接「%s」（%s）：\n\n" % (target_ssid, up_txt)
                                + guide +
                                "\n\n完成后：副路由会扩展「%s」的信号范围，手机/电脑连副路由(或主路由)都能上网。" % target_ssid)
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


