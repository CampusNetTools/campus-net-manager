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

设计取舍: 网络计算全部丢到线程, 工作线程只允许通过 ``self._clash_ui(fn)`` 把更新
排进队列(主线程 ``_clash_pump`` 每 80ms 消费一次), 绝不直接跨线程调 tkinter ——
tkinter 不是线程安全的, 详见 ``_clash_ui`` 的说明。解析/排序等纯逻辑放在
``core.clash_api``, 便于单元测试。
"""
import queue
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
SPEED_MIN_BYTES = 262144          # 样本小于 256KB 算不出可信带宽
SPEED_MAX_SECONDS = 20            # 单次下载测速的墙钟上限(socket 超时管不到总时长)
SPEED_URLS = (
    "https://speed.cloudflare.com/__down?bytes=%d" % SPEED_BYTES,
    "https://cachefly.cachefly.net/5mb.test",
)
# 协议下拉框的兜底初值; 每次刷新会按订阅里真实存在的协议重建(见 _clash_sync_proto_choices)
FALLBACK_PROTO_CHOICES = ["全部", "VLESS", "Hysteria2"]


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
        self._clash_rows = []
        self._clash_delays = {}
        self._clash_busy = False
        # 工作线程 -> 主线程的 UI 更新通道(见 _clash_ui 的说明)
        self._clash_uiq = queue.Queue()
        # 代际号: 窗口每次重建都 +1, 让上一代还挂在队列里的陈旧更新被丢弃
        self._clash_gen = getattr(self, "_clash_gen", 0) + 1
        # 排序状态: 之前 _clash_sort 改的是 _clash_nodes 的顺序, 但 _clash_fill_tree
        # 每次都无条件重排, 于是点表头完全没反应。改成把排序意图存成状态。
        self._clash_sort_key = "delay"
        self._clash_sort_desc = False
        self._clash_current = ""

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
        cmb = ttk.Combobox(filt, textvariable=self._clash_proto,
                           values=FALLBACK_PROTO_CHOICES,
                           state="readonly", width=12)
        cmb.grid(row=0, column=1, sticky="w", padx=(8, 14))
        cmb.bind("<<ComboboxSelected>>", lambda _e: self._clash_fill_tree())
        self._clash_proto_box = cmb
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

        def _clash_close():
            # 先摘掉窗口引用(泵会因此停止), 再销毁。还在跑的工作线程只会往队列里
            # 丢东西, 队列本身是纯 Python 的, 不会有跨线程 tkinter 调用。
            self._clash_window = None
            try:
                while True:
                    self._clash_uiq.get_nowait()
            except queue.Empty:
                pass
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _clash_close)

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
        win.after(80, self._clash_pump)
        return win

    # ------------------------------------------------- 线程安全的 UI 更新通道
    def _clash_ui(self, fn):
        """把一次 UI 更新排队交给主线程执行(工作线程只允许调用这一个方法)。

        直接从工作线程调 ``self.after`` 是**不安全**的: tkinter 不是线程安全的,
        mainloop 未运行或正在退出时会直接抛
        ``RuntimeError: main thread is not in main loop``。实测批量测速每测完一个
        节点都要刷新一次界面, 正好是最容易撞上这个问题的场景 —— 一旦抛出, 异常会
        顺着 ``pool.map`` 冒到 worker, 被当成「测速中断」报给用户, 而真实原因跟
        节点毫无关系。

        这里**刻意只做纯 Python 的队列投递**: 连 ``winfo_exists()`` 都不能在这里
        调 —— 那同样是一次跨线程 tkinter 调用(第一版就是这么写的, 结果异常被
        下面的 except 吞掉, 界面再也刷不出来)。窗口是否还活着交给主线程的
        ``_clash_pump`` 判断。
        """
        ui_queue = getattr(self, "_clash_uiq", None)
        if ui_queue is None:
            return
        try:
            ui_queue.put((getattr(self, "_clash_gen", 0), fn))
        except Exception:                               # noqa: BLE001 - 绝不能影响工作线程
            pass

    def _clash_pump(self):
        """在主线程里消费 ``_clash_ui`` 排上来的更新(窗口存活期间每 80ms 一次)。"""
        win = getattr(self, "_clash_window", None)
        ui_queue = getattr(self, "_clash_uiq", None)
        if win is None or ui_queue is None:
            return
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        gen = getattr(self, "_clash_gen", 0)
        while True:
            try:
                item = ui_queue.get_nowait()
            except queue.Empty:
                break
            try:
                item_gen, fn = item
            except (TypeError, ValueError):
                continue
            if item_gen != gen:
                continue                                # 上一个窗口时代的陈旧更新
            try:
                fn()
            except Exception:                           # noqa: BLE001 - 单条失败不拖垮泵
                pass
        try:
            win.after(80, self._clash_pump)
        except Exception:
            pass

    def _clash_refresh_later(self, ms=300):
        """延迟刷新(必须在主线程里调度, 所以绕一次队列)。"""
        self._clash_ui(lambda: self.after(ms, self._clash_refresh))

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
                self._clash_ui(lambda: self._clash_render(version, group, nodes, code))
            except clash.ClashApiError as exc:
                self._clash_ui(lambda err=exc: self._clash_fail(err))
            except Exception as exc:                      # noqa: BLE001 - UI 兜底
                self._clash_ui(lambda err=exc: self._clash_fail(err, prefix="读取失败"))

        threading.Thread(target=worker, daemon=True).start()

    def _clash_render(self, version, group, nodes, probe_code=None):
        self._clash_nodes = nodes
        self._clash_current = clash.selection_now(group)
        # 清掉已经不在订阅里的节点名, 否则换订阅后旧的测速结果会一直挂在字典里,
        # 一旦新订阅出现同名节点还会被当成"刚测过"。
        names = {n["name"] for n in nodes}
        for stale in [k for k in self._clash_delays if k not in names]:
            self._clash_delays.pop(stale, None)
        self._clash_sync_proto_choices(nodes)
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
        if not nodes:
            self._clash_log(
                "路由器上的代理没有任何可用节点。\n\n"
                "排查:\n"
                "  1) 打开「VPN 订阅 · 安全导入」重新部署一次订阅\n"
                "  2) 到「路由器后台工作台」看 mihomo 是否在运行\n"
                "  3) 若刚断电重启过, 代理需要重新部署才会恢复")
            return
        if probe_code is not None and probe_code != 204:
            self._clash_log(
                "经路由器显式代理探活返回 %s (期望 204)。\n"
                "说明当前选中的节点「过不了流量」, 可以点「换一个可用节点」或"
                "「一键选最快」自动换掉它。\n"
                "（你自己的直连上网不受影响: 这只影响手动把代理设成路由器 7890 的设备。）"
                % probe_code)

    def _clash_sync_proto_choices(self, nodes):
        """把协议下拉框的选项同步成订阅里真实存在的协议(保留用户当前选择)。"""
        box = getattr(self, "_clash_proto_box", None)
        if box is None:
            return
        try:
            if not box.winfo_exists():
                return
            choices = clash.protocol_choices(nodes)
            if list(box.cget("values")) != choices:
                box.configure(values=choices)
            if self._clash_proto.get() not in choices:
                self._clash_proto.set("全部")
        except Exception:
            pass

    def _clash_effective_delay(self, node):
        """列表里真正显示的那个延迟: 优先用界面上刚测出来的结果。

        ``node["delay"]`` 来自 mihomo 的历史记录, 用户点过「全部测速」之后它就过期了。
        """
        name = node["name"]
        if name in self._clash_delays:
            return self._clash_delays[name]
        return node.get("delay")

    def _clash_visible_nodes(self):
        """按当前筛选 + 排序状态算出要显示的行(纯计算, 不碰界面)。"""
        proto = self._clash_proto.get()
        query = (self._clash_query.get() or "").strip().lower()
        rows = []
        for node in getattr(self, "_clash_nodes", []):
            if proto != "全部" and node["proto"] != proto:
                continue
            if query and query not in node["name"].lower():
                continue
            rows.append(node)
        key = getattr(self, "_clash_sort_key", "delay")
        if key == "cur":
            # 「使用中」置顶, 便于一眼找到当前出口
            return sorted(rows, key=lambda n: (not n.get("current"), n.get("name", "")))
        # 排序必须用「界面上正在显示的那个延迟」而不是 node["delay"] —— 后者是
        # mihomo 的历史记录。否则用户点完「全部测速」再按延迟排序, 看到的顺序会和
        # 列表里的数字对不上(实测踩到)。
        ranked = clash.sort_nodes(
            [dict(n, delay=self._clash_effective_delay(n)) for n in rows],
            by=key, desc=getattr(self, "_clash_sort_desc", False))
        origin = {n["name"]: n for n in rows}
        return [origin[n["name"]] for n in ranked]

    @staticmethod
    def _clash_row_values(node, delay):
        return (node["name"], node["proto"], _fmt_delay(delay),
                "● 使用中" if node["current"] else "")

    @staticmethod
    def _clash_row_tags(node, name, delays):
        tags = []
        if node["current"]:
            tags.append("current")
        if name in delays and delays.get(name) is None:
            tags.append("dead")
        return tags

    def _clash_fill_tree(self):
        tree = self._clash_tree_ref()
        if tree is None:
            return
        # 记住用户当前选中/滚动到哪一行, 重填后还原 —— 否则每次筛选、刷新、
        # 甚至测速出结果都会把选中清掉, 用户刚点好的节点转眼就没了。
        keep_name = None
        sel = tree.selection()
        if sel:
            prev = getattr(self, "_clash_rows", [])
            try:
                keep_name = prev[int(sel[0])]["name"]
            except (ValueError, IndexError, KeyError):
                keep_name = None
        rows = self._clash_visible_nodes()
        self._clash_rows = rows
        tree.delete(*tree.get_children())
        restore = None
        for idx, node in enumerate(rows):
            delay = self._clash_effective_delay(node)
            tree.insert("", "end", iid=str(idx),
                        values=self._clash_row_values(node, delay),
                        tags=self._clash_row_tags(node, node["name"], self._clash_delays))
            if keep_name is not None and node["name"] == keep_name:
                restore = str(idx)
        if restore is not None:
            try:
                tree.selection_set(restore)
                tree.see(restore)
            except Exception:
                pass

    def _clash_paint_delay(self, name):
        """测速出结果后只重画那一行。

        整表重填会让列表在测速期间不停闪动, 还会把选中和滚动位置冲掉。
        """
        tree = self._clash_tree_ref()
        if tree is None:
            return
        for idx, node in enumerate(getattr(self, "_clash_rows", [])):
            if node["name"] != name:
                continue
            iid = str(idx)
            try:
                if not tree.exists(iid):
                    return
                delay = self._clash_effective_delay(node)
                tree.item(iid, values=self._clash_row_values(node, delay),
                          tags=self._clash_row_tags(node, name, self._clash_delays))
            except Exception:
                pass
            return

    def _clash_tree_ref(self):
        """取 Treeview, 窗口已关/未建时返回 None(所有刷新入口共用这道闸)。"""
        tree = getattr(self, "_clash_tree", None)
        if tree is None:
            return None
        try:
            return tree if tree.winfo_exists() else None
        except Exception:
            return None

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

    def _clash_fail(self, exc, prefix="无法读取路由器代理接口"):
        """失败提示: 头部一行结论 + 详情区按错误类型给不同排查方向。"""
        if isinstance(exc, clash.ClashApiError):
            head = "%s: %s" % (prefix, exc)
            hint = clash.error_hint(exc)
        else:
            head = "%s: %s" % (prefix, exc)
            hint = ("如果是偶发, 先点「刷新」重试; 一直失败请检查与路由器的连接是否正常。")
        body = head + "\n\n排查:\n  " + hint.replace("\n", "\n  ")
        self._clash_set_head(head, False)
        self._clash_log(body)

    def _clash_fail_msg(self, head, hint=""):
        """非异常场景的失败提示(例如「全都测不到」)。"""
        self._clash_set_head(head, False)
        self._clash_log(head + ("\n\n" + hint if hint else ""))

    # ------------------------------------------------------------------ 忙闲
    def _clash_begin_busy(self, head_text):
        """占住「同一时刻只跑一个批量任务」的闸; 已被占用时提示并返回 False。

        测速与「一键选最快」都会开 4 路并发打同一台路由器, 允许它们叠着跑既
        拖慢彼此, 也会让两次结果互相覆盖。
        """
        if getattr(self, "_clash_busy", False):
            messagebox.showinfo("正在忙", "上一轮操作还没结束, 请稍等。",
                                parent=self._clash_window)
            return False
        self._clash_busy = True
        self._clash_set_head(head_text, None)
        return True

    def _clash_end_busy(self):
        self._clash_busy = False

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
        """点击表头排序; 同一列再点一次切换升/降序。

        这里只记录「排序意图」, 真正的排序由 ``_clash_visible_nodes`` 落实。
        之前这个函数直接重排 ``_clash_nodes``, 但 ``_clash_fill_tree`` 每次都
        无条件重排一遍, 结果是点表头完全没有反应。
        """
        mapped = {"node": "name", "proto": "proto", "delay": "delay",
                  "cur": "cur"}.get(key, "delay")
        if getattr(self, "_clash_sort_key", None) == mapped:
            self._clash_sort_desc = not getattr(self, "_clash_sort_desc", False)
        else:
            self._clash_sort_key = mapped
            self._clash_sort_desc = False
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
                    self._clash_ui(lambda: self._clash_log(
                        "已切换到「%s」\n经路由器代理探活 HTTP 204 —— 隧道可用。\n"
                        "想确认真实带宽可以再点「下载测速」。" % name))
                else:
                    self._clash_ui(lambda: self._clash_log(
                        "已切换到「%s」, 但探活返回 %s。\n"
                        "这个节点可能「能握手、过不了流量」, 建议点「换一个可用节点」或"
                        "「一键选最快」。" % (name, code)))
                self._clash_refresh_later(300)
            except clash.ClashApiError as exc:
                self._clash_ui(lambda e=exc: self._clash_fail(e, prefix="切换失败"))
                self._clash_refresh_later(300)
            except Exception as exc:                       # noqa: BLE001 - 线程兜底
                self._clash_ui(lambda e=exc: self._clash_fail(e, prefix="切换失败"))
                self._clash_refresh_later(300)

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
        self._clash_set_head("已请求路由器轮换节点, 约 15 秒后自动刷新…", None)
        # 提示写在刷新之前: after(15s, refresh) 里 refresh 会重设头部状态行,
        # 把提示挤掉, 所以顺序不能反。
        self._clash_log(
            "已触发轮换看门狗。路由器会并行测完全部候选节点、挑延迟最低的切过去, "
            "一般 20~30 秒完成。\n\n若稍后探活仍失败, 说明候选节点普遍不可用: "
            "建议更新订阅, 或在「路由器后台工作台」看 rotate.log 了解详情。")
        self.after(15000, self._clash_refresh)

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
        if not self._clash_begin_busy("正在测速 0/%d …" % len(nodes)):
            return
        host, port, token = self._clash_conf()
        total = len(nodes)
        done = {"n": 0, "ok": 0}

        def one(node):
            delay = clash.api_delay(host, port, token, node["name"])
            done["n"] += 1
            if delay:
                done["ok"] += 1
            self._clash_delays[node["name"]] = delay
            self._clash_ui(lambda nm=node["name"]: self._clash_paint_delay(nm))
            self._clash_ui(lambda: self._clash_set_head(
                "正在测速 %d/%d (可用 %d) …" % (done["n"], total, done["ok"]), None))

        def worker():
            failure = None
            try:
                with ThreadPoolExecutor(max_workers=TEST_WORKERS) as pool:
                    list(pool.map(one, nodes))
            except Exception as exc:                       # noqa: BLE001 - 线程兜底
                failure = exc
            finally:
                self._clash_end_busy()
            if failure is not None:
                # 接口不可达必须明说是「路由器/令牌」的问题。以前异常直接漏出线程,
                # 用户看到的是「测速完成: 0/52 可用」, 会被误导成自己节点全挂了。
                self._clash_ui(lambda e=failure: self._clash_fail(
                    e, prefix="测速中断 (已完成 %d/%d)" % (done["n"], total)))
                return
            summary = "测速完成: %d/%d 可用" % (done["ok"], total)
            if done["ok"]:
                best = clash.fastest_node(
                    [dict(n, delay=self._clash_delays.get(n["name"])) for n in nodes])
                if best:
                    summary += ", 最快是「%s」(%s)" % (best["name"],
                                                   _fmt_delay(best["delay"]))
            self._clash_ui(lambda: self._clash_log(
                summary + "\n\n延迟最低不代表带宽最好; 便宜节点常出现"
                "「能握手、过不了流量」, 建议切换后再点一次「下载测速」。"))
            # 让头部状态行从「正在测速 …」恢复成正常的节点概览(否则会一直卡在那)
            self._clash_ui(self._clash_refresh)

        threading.Thread(target=worker, daemon=True).start()

    def _clash_pick_fastest(self):
        rows = [n for n in getattr(self, "_clash_rows", []) if n.get("alive")]
        if not rows:
            messagebox.showinfo("没有可测节点",
                                "当前筛选下没有可测的节点, 建议先「刷新」或更新订阅。",
                                parent=self._clash_window)
            return
        if not self._clash_begin_busy("正在挑最快节点 (共 %d 个, 先逐个测)…" % len(rows)):
            return
        host, port, token = self._clash_conf()
        total = len(rows)

        def worker():
            results = []
            try:
                with ThreadPoolExecutor(max_workers=TEST_WORKERS) as pool:
                    delays = list(pool.map(
                        lambda n: clash.api_delay(host, port, token, n["name"]), rows))
                for node, delay in zip(rows, delays):
                    self._clash_delays[node["name"]] = delay
                    if delay:
                        results.append((delay, node["name"]))
            except Exception as exc:                       # noqa: BLE001 - 线程兜底
                self._clash_ui(lambda e=exc: self._clash_fail(e, prefix="挑最快节点失败"))
                return
            finally:
                self._clash_end_busy()
                self._clash_ui(self._clash_fill_tree)
            if not results:
                self._clash_ui(lambda: self._clash_fail_msg(
                    "没有测到可用节点",
                    "共测 %d 个节点, 全部没通过延迟测量 —— 说明这批节点都不通了, "
                    "建议更新订阅或更换机场。" % total))
                return
            results.sort()
            delay, name = results[0]
            try:
                clash.api_select(host, port, token, name)
            except clash.ClashApiError as exc:
                self._clash_ui(lambda e=exc: self._clash_fail(e, prefix="切换失败"))
                return
            code = clash.sniff_local_proxy(host, timeout=10)
            self._clash_ui(lambda: self._clash_log(
                "已切到最快的可用节点「%s」(%d ms)\n经代理探活: HTTP %s\n"
                "共测 %d 个, 可用 %d 个。" % (name, delay, code, total, len(results))))
            self._clash_refresh_later(300)

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
        self._clash_set_head("正在下载测速 (约 5 MB)…", None)

        def worker():
            proxy = "http://%s:7890" % host
            opener = urlrequest.build_opener(urlrequest.ProxyHandler(
                {"http": proxy, "https": proxy}))
            last_err = "没有可用的测速源"
            for url in SPEED_URLS:
                started = time.monotonic()
                got = 0
                try:
                    with opener.open(url, timeout=30) as resp:
                        while True:
                            chunk = resp.read(65536)
                            if not chunk:
                                break
                            got += len(chunk)
                            if got >= SPEED_BYTES:
                                break
                            # socket 超时只约束"两次读取之间", 对一根一直滴答的
                            # 慢速管道等于没有上限, 所以自己盯总时长。
                            if time.monotonic() - started > SPEED_MAX_SECONDS:
                                break
                except (HTTPError, URLError, OSError) as exc:
                    last_err = str(exc)
                    continue
                elapsed = time.monotonic() - started
                if got < SPEED_MIN_BYTES:
                    last_err = ("只收到 %.0f KB, 样本太小算不出可信带宽"
                                % (got / 1024.0))
                    continue
                mbps = clash.throughput_mbps(got, elapsed)
                self._clash_ui(lambda g=got, e=elapsed, m=mbps: self._clash_log(
                    "下载测速完成: %.1f MB / %.1f 秒 = %.2f Mbps\n(经 %s 代理, 目标 %s)"
                    % (g / 1048576.0, e, m, host, label)))
                self._clash_ui(self._clash_refresh)
                return
            self._clash_ui(lambda msg=last_err: self._clash_fail_msg(
                "下载测速失败",
                "%s\n\n说明当前节点过不了真实流量(常见的「假活」节点), "
                "建议点「换一个可用节点」。" % msg))
            self._clash_ui(self._clash_refresh)

        threading.Thread(target=worker, daemon=True).start()
