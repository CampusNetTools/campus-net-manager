# -*- coding: utf-8 -*-
"""「Clash 节点管理」窗口 Mixin (v5.4.2)。

把路由器上 mihomo(Clash Meta) 的节点能力搬进管家, 全部走工作台的令牌鉴权转发
端点 ``/cgi-bin/proxy-api.sh``, 不保存面板密钥、不依赖 SSH:

  1. 实时节点列表: 名称 / 协议(VLESS、Hysteria2...) / 延迟 / 是否当前使用
  2. 测速: 单节点延迟、按协议批量测延迟(小并发, 不打满中继)、真实下载带宽
  3. 切换节点: 双击或按钮切到指定节点; 一键挑最快的可用节点; 「自动择优」交给
     路由器上的 url-test 组
  4. 协议筛选: 只测/只显示某一个协议的节点(校园网对 UDP 态度不稳定, Hy2 需单独看)
  5. 换一个可用节点: 直接触发路由器上的节点轮换看门狗 (rotate.sh)
  6. 透明接管开关: 复用工作台的限时试用/关闭操作(高风险动作, 全部二次确认)
  7. 订阅更新: 打开既有的「VPN 订阅 · 安全导入」窗口

设计取舍: 网络计算全部丢到线程, 回主线程统一 ``self.after(0, ...)`` 刷 UI;
解析/排序等纯逻辑放在 ``core.clash_api``, 便于单元测试。
"""
import threading
import time
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from tkinter import messagebox, ttk
from urllib import request as urlrequest
from urllib.error import HTTPError, URLError

from core import clash_api as clash

from gui.theme import *  # noqa: F401,F403

TREE_STYLE = "Clash.Treeview"
TEST_WORKERS = 4
BATCH_LIMIT = 60
SPEED_BYTES = 5 * 1024 * 1024
SPEED_URLS = (
    "https://speed.cloudflare.com/__down?bytes=%d" % SPEED_BYTES,
    "https://cachefly.cachefly.net/5mb.test",
)
PROTO_CHOICES = ["全部", "VLESS", "Hysteria2"]


def _fmt_delay(delay):
    return clash.format_delay(delay)


class ClashNodesMixin:
    """「Clash 节点管理」窗口。"""

    # ------------------------------------------------------------------ 窗口
    def show_clash_nodes_window(self):
        existing = getattr(self, "_clash_window", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                self._clash_refresh()
                return existing
        except Exception:
            pass

        self._clash_nodes = []
        self._clash_delays = {}
        self._clash_busy = False

        win = tk.Toplevel(self)
        self._clash_window = win
        win.title("Clash 节点管理")
        win.configure(bg=BG)
        win.geometry("920x700")
        win.minsize(760, 540)
        win.transient(self)

        self._clash_setup_style()

        card = ttk.Frame(win, style="Card.TFrame", padding=CARD_PAD_SUB)
        card.pack(fill="both", expand=True, padx=WINDOW_PAD[0], pady=WINDOW_PAD[1])
        card.columnconfigure(0, weight=1)
        card.rowconfigure(4, weight=1)

        ttk.Label(card, text="Clash 节点管理", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w")
        lbl_sub = ttk.Label(
            card,
            text=("直接管理路由器上的 mihomo(Clash) 节点: 看延迟、测带宽、切节点、换协议。"
                  "全部经工作台令牌转发, 不保存面板密钥、不需要 SSH。"),
            style="Muted.TLabel", wraplength=800)
        lbl_sub.grid(row=1, column=0, sticky="w", pady=(6, 12))

        # ---------- 连接参数 (复用工作台配置) ----------
        bar = ttk.Frame(card, style="Card.TFrame")
        bar.grid(row=2, column=0, sticky="ew")
        conf = self._rc_settings()
        self._clash_url_label = ttk.Label(
            bar, text="路由器 %s:%s" % (conf["host"], conf["port"]), style="Field.TLabel")
        self._clash_url_label.grid(row=0, column=0, sticky="w")
        ttk.Button(bar, text="刷新", command=self._clash_refresh).grid(
            row=0, column=1, padx=(14, 6))
        ttk.Button(bar, text="路由器后台工作台", style="Gray.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "router_console", self.show_router_console_window)).grid(
            row=0, column=2, padx=(0, 6))
        ttk.Button(bar, text="打开 Web 面板", style="Gray.TButton",
                   command=self._clash_open_panel).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(bar, text="修改连接参数", style="Quiet.TButton",
                   command=lambda: self._fwin_open_legacy(
                       "router_console", self.show_router_console_window)).grid(
            row=0, column=4)

        # ---------- 筛选 / 测速 ----------
        filt = ttk.Frame(card, style="Card.TFrame")
        filt.grid(row=3, column=0, sticky="ew", pady=(12, 6))
        filt.columnconfigure(3, weight=1)
        ttk.Label(filt, text="协议", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self._clash_proto = tk.StringVar(value="全部")
        cmb = ttk.Combobox(filt, textvariable=self._clash_proto, values=PROTO_CHOICES,
                           state="readonly", width=12)
        cmb.grid(row=0, column=1, sticky="w", padx=(8, 14))
        cmb.bind("<<ComboboxSelected>>", lambda _e: self._clash_fill_tree())
        ttk.Label(filt, text="搜索", style="Field.TLabel").grid(row=0, column=2, sticky="w")
        self._clash_query = tk.StringVar()
        ent = ttk.Entry(filt, textvariable=self._clash_query)
        ent.grid(row=0, column=3, sticky="ew", padx=(8, 14))
        ent.bind("<KeyRelease>", lambda _e: self._clash_fill_tree())
        ttk.Button(filt, text="测选中", style="Gray.TButton",
                   command=self._clash_test_selected).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(filt, text="全部测速", command=self._clash_test_all).grid(
            row=0, column=5, padx=(0, 6))
        ttk.Button(filt, text="一键选最快", style="Accent.TButton",
                   command=self._clash_pick_fastest).grid(row=0, column=6)

        # ---------- 节点表 ----------
        wrap = ttk.Frame(card, style="Inner.TFrame")
        wrap.grid(row=4, column=0, sticky="nsew")
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        cols = ("node", "proto", "delay", "cur")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", style=TREE_STYLE,
                            selectmode="browse")
        for key, text, width, anchor in (
                ("node", "节点", 420, "w"), ("proto", "协议", 110, "center"),
                ("delay", "延迟", 100, "center"), ("cur", "使用中", 70, "center")):
            tree.heading(key, text=text, command=lambda k=key: self._clash_sort(k))
            tree.column(key, width=width, anchor=anchor,
                        stretch=(key == "node"))
        tree.grid(row=0, column=0, sticky="nsew")
        bar2 = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        bar2.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=bar2.set)
        tree.bind("<Double-1>", lambda _e: self._clash_apply_selected())
        tree.tag_configure("current", foreground="#8de5c3")
        tree.tag_configure("dead", foreground="#f06478")
        self._clash_tree = tree

        # ---------- 状态 ----------
        self._clash_head = ttk.Label(card, text="正在读取路由器代理状态…",
                                     style="Muted.TLabel", wraplength=800)
        self._clash_head.grid(row=5, column=0, sticky="w", pady=(10, 6))
        self._clash_detail = tk.Text(card, height=4, width=1, bg="#09101c", fg="#b7c4d8",
                                     font=("PingFang SC", 9), relief="flat", wrap="word",
                                     padx=10, pady=8, state="disabled")
        self._clash_detail.grid(row=6, column=0, sticky="ew")

        # ---------- 操作 ----------
        acts = ttk.Frame(card, style="Card.TFrame")
        acts.grid(row=7, column=0, sticky="ew", pady=(12, 0))
        for i in range(4):
            acts.columnconfigure(i, weight=1, uniform="clashact")
        buttons = [
            ("切换到选中节点", self._clash_apply_selected, "Accent.TButton", False),
            ("自动择优(url-test)", lambda: self._clash_apply_named("自动选择"),
             "Gray.TButton", False),
            ("换一个可用节点", self._clash_rotate, "Gray.TButton", False),
            ("下载测速", self._clash_speed_test, "Gray.TButton", False),
            ("更新订阅", self._clash_open_subscription, "Gray.TButton", False),
            ("当前设备透明试用120秒",
             lambda: self._rc_action("enable_transparent", confirm=True), "Gray.TButton", False),
            ("关闭透明接管",
             lambda: self._rc_action("disable_transparent", confirm=True), "Gray.TButton", False),
            ("复制节点名", self._clash_copy_name, "Quiet.TButton", False),
        ]
        for idx, (text, cb, style, danger) in enumerate(buttons):
            ttk.Button(acts, text=text, style=style, command=cb).grid(
                row=idx // 4, column=idx % 4, sticky="ew", padx=(0, 6), pady=(0, 6))

        lbl_hint = ttk.Label(
            card,
            text=("说明: 延迟只代表握手往返, 便宜节点常有「能握手、过不了流量」的情况, "
                  "所以切换后建议点「下载测速」确认真实带宽。透明接管会让整个局域网的流量"
                  "自动走代理, 风险较高, 默认只用「当前设备试用120秒」。"),
            style="Muted.TLabel", wraplength=800, justify="left")
        lbl_hint.grid(row=8, column=0, sticky="w", pady=(6, 0))

        win.protocol("WM_DELETE_WINDOW",
                     lambda: (setattr(self, "_clash_window", None), win.destroy()))

        def _on_resize(_event=None):
            try:
                wpx = win.winfo_width() - 96
                if wpx > 260:
                    lbl_sub.configure(wraplength=wpx)
                    lbl_hint.configure(wraplength=wpx)
                    self._clash_head.configure(wraplength=wpx)
            except Exception:
                pass

        win.bind("<Configure>", _on_resize)
        win.after(80, lambda: self._rc_autosize(win))
        self._clash_refresh()
        return win

    def _clash_setup_style(self):
        """深色主题的 Treeview 样式(幂等, 重复调用无副作用)。"""
        try:
            style = ttk.Style(self)
            style.configure(TREE_STYLE, background="#0d1626", fieldbackground="#0d1626",
                            foreground="#dbe6f5", font=FONT_S, rowheight=24, borderwidth=0)
            style.configure(TREE_STYLE + ".Heading", background=CARD2, foreground=MUTED,
                            font=FONT_S, relief="flat", padding=(8, 6))
            style.map(TREE_STYLE, background=[("selected", "#243a5e")],
                      foreground=[("selected", "#ffffff")])
            style.map(TREE_STYLE + ".Heading", background=[("active", "#22314b")])
        except Exception:
            pass

    # ------------------------------------------------------------------ 数据
    def _clash_conf(self):
        conf = self._rc_settings()
        return conf["host"], conf["port"], conf["token"]

    def _clash_refresh(self):
        if getattr(self, "_clash_busy", False):
            return
        host, port, token = self._clash_conf()
        self._clash_set_head("正在读取 %s:%s …" % (host, port), None)

        def worker():
            try:
                version = clash.api_version(host, port, token, timeout=10)
                group = clash.api_group(host, port, token)
                proxies = clash.api_proxies(host, port, token)
                nodes = clash.build_nodes(proxies, group)
                # 顺带探一次「本机经路由器代理」的真实连通性(纯只读)
                code = clash.sniff_local_proxy(host, timeout=8)
                self.after(0, lambda: self._clash_render(version, group, nodes, code))
            except clash.ClashApiError as exc:
                self.after(0, lambda err=exc: self._clash_fail(str(err)))
            except Exception as exc:                      # noqa: BLE001 - UI 兜底
                self.after(0, lambda err=exc: self._clash_fail("读取失败: %s" % err))

        threading.Thread(target=worker, daemon=True).start()

    def _clash_render(self, version, group, nodes, probe_code=None):
        self._clash_nodes = nodes
        self._clash_current = clash.selection_now(group)
        self._clash_fill_tree()
        alive = [n for n in nodes if n.get("alive")]
        stat = {}
        for node in nodes:
            stat[node["proto"]] = stat.get(node["proto"], 0) + 1
        proto_txt = "  ".join("%s %d" % (k, v) for k, v in sorted(stat.items()))
        head = ("当前节点: %s   |   共 %d 个节点 (%s)   |   mihomo %s   |   在线 %d"
                % (self._clash_current or "未知", len(nodes), proto_txt,
                   version.get("version", "-"), len(alive)))
        if probe_code is not None:
            head += "   |   代理探活 HTTP %s %s" % (
                probe_code, "正常" if probe_code == 204 else "不通")
        self._clash_set_head(head, probe_code == 204)
        if probe_code is not None and probe_code != 204:
            self._clash_log(
                "经路由器显式代理探活返回 %s (期望 204)。\n"
                "说明当前选中的节点「过不了流量」, 可以点「换一个可用节点」或"
                "「一键选最快」自动换掉它。\n"
                "（你自己的直连上网不受影响: 这只影响手动把代理设成路由器 7890 的设备。）"
                % probe_code)

    def _clash_fill_tree(self):
        tree = getattr(self, "_clash_tree", None)
        if tree is None:
            return
        try:
            if not tree.winfo_exists():
                return
        except Exception:
            return
        proto = self._clash_proto.get()
        query = (self._clash_query.get() or "").strip().lower()
        rows = []
        for node in getattr(self, "_clash_nodes", []):
            if proto != "全部" and node["proto"] != proto:
                continue
            if query and query not in node["name"].lower():
                continue
            rows.append(node)
        rows = clash.sort_nodes(rows)
        self._clash_rows = rows
        tree.delete(*tree.get_children())
        for idx, node in enumerate(rows):
            delay = self._clash_delays.get(node["name"], node.get("delay"))
            tags = []
            if node["current"]:
                tags.append("current")
            if delay is None and node["name"] in self._clash_delays:
                tags.append("dead")
            tree.insert("", "end", iid=str(idx),
                        values=(node["name"], node["proto"], _fmt_delay(delay),
                                "● 使用中" if node["current"] else ""),
                        tags=tags)

    def _clash_set_head(self, text, ok=None):
        try:
            if not self._clash_head.winfo_exists():
                return
        except Exception:
            return
        self._clash_head.configure(text=text)
        try:
            if ok is True:
                self._clash_head.configure(foreground="#31c48d")
            elif ok is False:
                self._clash_head.configure(foreground="#ef5960")
            else:
                self._clash_head.configure(foreground=MUTED)
        except Exception:
            pass

    def _clash_log(self, text):
        """只刷新详情区, 不动顶部状态行(避免覆盖测速/刷新的进度提示)。"""
        try:
            box = self._clash_detail
            if not box.winfo_exists():
                return
        except Exception:
            return
        box.configure(state="normal")
        box.delete("1.0", "end")
        box.insert("1.0", text)
        box.configure(state="disabled")

    def _clash_fail(self, msg):
        self._clash_set_head("无法读取路由器代理接口: %s" % msg, False)
        self._clash_log("读取失败: %s\n\n排查:\n"
                        "  1) 路由器是否在线、能否打开「路由器后台工作台」\n"
                        "  2) 工作台令牌是否与路由器一致(默认 20050927)\n"
                        "  3) 路由器上是否已部署代理接口 "
                        "/data/other_vol/console/cgi-bin/proxy-api.sh" % msg)

    # ------------------------------------------------------------------ 操作
    def _clash_selected_node(self):
        tree = getattr(self, "_clash_tree", None)
        rows = getattr(self, "_clash_rows", [])
        if tree is None or not rows:
            return None
        sel = tree.selection()
        if not sel:
            return None
        try:
            idx = int(sel[0])
        except (TypeError, ValueError):
            return None
        return rows[idx] if 0 <= idx < len(rows) else None

    def _clash_sort(self, key):
        rows = getattr(self, "_clash_rows", [])
        if key == "node":
            self._clash_nodes = clash.sort_nodes(self._clash_nodes, by="name")
        elif key == "proto":
            self._clash_nodes = sorted(self._clash_nodes, key=lambda n: n["proto"])
        else:
            self._clash_nodes = clash.sort_nodes(self._clash_nodes, by="delay")
        self._clash_fill_tree()

    def _clash_apply_selected(self):
        node = self._clash_selected_node()
        if node is None:
            messagebox.showinfo("未选择节点", "请先在列表里点一个节点（双击即可切换）。",
                                parent=self._clash_window)
            return
        self._clash_apply_named(node["name"])

    def _clash_apply_named(self, name):
        if not name:
            return
        host, port, token = self._clash_conf()

        def worker():
            try:
                clash.api_select(host, port, token, name)
                code = clash.sniff_local_proxy(host, timeout=10)
                if code == 204:
                    self.after(0, lambda: self._clash_log(
                        "已切换到「%s」\n经路由器代理探活 HTTP 204 —— 隧道可用。\n"
                        "想确认真实带宽可以再点「下载测速」。" % name))
                else:
                    self.after(0, lambda: self._clash_log(
                        "已切换到「%s」, 但探活返回 %s。\n"
                        "这个节点可能「能握手、过不了流量」, 建议点「换一个可用节点」或"
                        "「一键选最快」。" % (name, code)))
                self.after(300, self._clash_refresh)
            except clash.ClashApiError as exc:
                self.after(0, lambda err=exc: self._clash_log("切换失败: %s" % err))

        self._clash_set_head("正在切换到「%s」…" % name, None)
        threading.Thread(target=worker, daemon=True).start()

    def _clash_rotate(self):
        """调用路由器上的轮换看门狗(强制换一个已验证可用的节点)。"""
        if not messagebox.askyesno(
                "换一个可用节点",
                "将让路由器上的轮换看门狗立刻换到下一个可用节点。\n"
                "期间代理会有约 10 秒的短暂中断（你的直连上网不受影响）。确定继续吗？",
                parent=self._clash_window):
            return
        self._rc_action("rotate_node")
        self._clash_set_head("已请求路由器轮换节点, 约 10 秒后自动刷新…", None)
        self.after(12000, self._clash_refresh)
        self.after(12000, lambda: self._clash_log(
            "已触发轮换看门狗。若探活仍失败, 说明候选节点普遍不可用, "
            "建议更新订阅或在「路由器后台工作台」查看 rotate.log。"))

    def _clash_open_panel(self):
        host, _port, _token = self._clash_conf()
        base = "http://%s:9091/ui" % host
        try:
            webbrowser.open(base)
            self._clash_log("已尝试打开 mihomo 面板:\n%s\n\n面板需要密码时才用得上; "
                            "本窗口的功能不需要它。" % base)
        except Exception as exc:
            messagebox.showwarning("打开失败", str(exc), parent=self._clash_window)

    def _clash_open_subscription(self):
        self._fwin_open_legacy("vpn_subscription", self.show_subscription_window)
        self.after(1500, self._clash_refresh)

    def _clash_copy_name(self):
        node = self._clash_selected_node()
        if node is None:
            return
        try:
            self.clipboard_clear()
            self.clipboard_append(node["name"])
            self._clash_log("已复制节点名:\n%s" % node["name"])
        except Exception:
            pass

    # ------------------------------------------------------------------ 测速
    def _clash_target_nodes(self, single=False):
        if single:
            node = self._clash_selected_node()
            return [node] if node else []
        rows = list(getattr(self, "_clash_rows", []))
        return rows

    def _clash_test_selected(self):
        nodes = self._clash_target_nodes(single=True)
        if not nodes:
            messagebox.showinfo("未选择节点", "请先在列表里点一个节点。",
                                parent=self._clash_window)
            return
        self._clash_run_delay(nodes)

    def _clash_test_all(self):
        nodes = self._clash_target_nodes()
        if not nodes:
            return
        if len(nodes) > BATCH_LIMIT and not messagebox.askyesno(
                "节点较多",
                "当前筛选出 %d 个节点, 逐个测速会持续较久(约 %d 秒), "
                "并且会占用中继带宽。要继续吗？\n\n建议先把「协议」改成 VLESS 只测一类。"
                % (len(nodes), max(1, len(nodes) * 2 // TEST_WORKERS)),
                parent=self._clash_window):
            return
        self._clash_run_delay(nodes)

    def _clash_run_delay(self, nodes):
        if getattr(self, "_clash_busy", False):
            messagebox.showinfo("正在测速", "上一轮测速还没结束, 请稍等。",
                                parent=self._clash_window)
            return
        host, port, token = self._clash_conf()
        total = len(nodes)
        self._clash_busy = True
        done = {"n": 0, "ok": 0}
        self._clash_set_head("正在测速 0/%d …" % total, None)

        def one(node):
            delay = clash.api_delay(host, port, token, node["name"])
            done["n"] += 1
            if delay:
                done["ok"] += 1
            self._clash_delays[node["name"]] = delay
            self.after(0, self._clash_fill_tree)
            self.after(0, lambda: self._clash_set_head(
                "正在测速 %d/%d (可用 %d) …" % (done["n"], total, done["ok"]), None))

        def worker():
            try:
                with ThreadPoolExecutor(max_workers=TEST_WORKERS) as pool:
                    list(pool.map(one, nodes))
            finally:
                self._clash_busy = False
                summary = "测速完成: %d/%d 可用" % (done["ok"], total)
                if done["ok"]:
                    best = clash.fastest_node(
                        [dict(n, delay=self._clash_delays.get(n["name"]))
                         for n in nodes])
                    if best:
                        summary += ", 最快是「%s」(%s)" % (
                            best["name"], _fmt_delay(best["delay"]))
                self.after(0, lambda: self._clash_log(
                    summary + "\n\n延迟最低不代表带宽最好; 便宜节点常出现"
                    "「能握手、过不了流量」, 建议切换后再点一次「下载测速」。"))

        threading.Thread(target=worker, daemon=True).start()

    def _clash_pick_fastest(self):
        rows = [n for n in getattr(self, "_clash_rows", []) if n.get("alive")]
        if not rows:
            return
        host, port, token = self._clash_conf()
        total = len(rows)
        self._clash_set_head("正在挑最快节点 (先测 %d 个)…" % total, None)

        def worker():
            results = []
            with ThreadPoolExecutor(max_workers=TEST_WORKERS) as pool:
                delays = list(pool.map(
                    lambda n: clash.api_delay(host, port, token, n["name"]), rows))
            for node, delay in zip(rows, delays):
                self._clash_delays[node["name"]] = delay
                if delay:
                    results.append((delay, node["name"]))
            self.after(0, self._clash_fill_tree)
            if not results:
                self.after(0, lambda: self._clash_log("没有测到可用节点, 建议更新订阅。"))
                return
            results.sort()
            delay, name = results[0]
            try:
                clash.api_select(host, port, token, name)
            except clash.ClashApiError as exc:
                self.after(0, lambda err=exc: self._clash_log("切换失败: %s" % err))
                return
            code = clash.sniff_local_proxy(host, timeout=10)
            self.after(0, lambda: self._clash_log(
                "已切到最快的可用节点「%s」(%d ms)\n经代理探活: HTTP %s\n"
                "共测 %d 个, 可用 %d 个。" % (name, delay, code, total, len(results))))
            self.after(300, self._clash_refresh)

        threading.Thread(target=worker, daemon=True).start()

    def _clash_speed_test(self):
        host, port, _ = self._clash_conf()
        node = self._clash_selected_node()
        label = node["name"] if node else (getattr(self, "_clash_current", "") or "当前节点")
        if not messagebox.askyesno(
                "下载测速",
                "将通过路由器代理下载 5 MB 测试数据, 占用 5~15 秒带宽。\n"
                "目标是 %s。继续吗？" % label, parent=self._clash_window):
            return
        self._clash_set_head("正在下载测速 (5 MB)…", None)

        def worker():
            proxy = "http://%s:7890" % host
            opener = urlrequest.build_opener(urlrequest.ProxyHandler(
                {"http": proxy, "https": proxy}))
            last_err = ""
            for url in SPEED_URLS:
                try:
                    started = time.monotonic()
                    got = 0
                    with opener.open(url, timeout=30) as resp:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            got += len(chunk)
                            if got >= SPEED_BYTES * 2:
                                break
                    elapsed = time.monotonic() - started
                    mbps = clash.throughput_mbps(got, elapsed)
                    self.after(0, lambda: self._clash_log(
                        "下载测速完成: %.1f MB / %.1f 秒 = %.2f Mbps\n(经 %s 代理, 目标 %s)"
                        % (got / 1048576.0, elapsed, mbps, host, label)))
                    return
                except (HTTPError, URLError, OSError) as exc:
                    last_err = str(exc)
            self.after(0, lambda: self._clash_log(
                "下载测速失败: %s\n说明当前节点过不了真实流量(常见的「假活」节点), "
                "建议点「换一个可用节点」。" % last_err))

        threading.Thread(target=worker, daemon=True).start()
