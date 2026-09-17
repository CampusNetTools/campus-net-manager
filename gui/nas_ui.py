# -*- coding: utf-8 -*-
"""「NAS 管家」窗口 Mixin (v5.5.0)。

把路由器 NAS(alist + rclone WebDAV 桥 + TP-Link USB 盘) 的日常使用搬进管家:

  1. 服务状态: alist / rclone / tailscale 是否在跑、网页端是否可达、Tailscale IP
     —— 全部经工作台令牌转发端点 /cgi-bin/nas-api.sh, 不需要 SSH
  2. 服务控制: 启动 / 停止 / 重启(路由器侧幂等看门狗兜底)
  3. 网页端入口: 一键用系统浏览器打开 alist Web UI
  4. 文件管理: 浏览目录、上传、下载、删除、新建文件夹(直连 alist HTTP API/WebDAV)

凭据安全: alist 的登录口令用 Windows DPAPI 加密后存 config.json 的 ``nas`` 段,
仓库/public 发布里绝不出现明文 —— 与 VPN 订阅地址同一套存储机制。

线程模型与 ClashNodesMixin 完全一致: 工作线程只允许通过 ``self._nas_ui(fn)`` 把
更新排进队列(主线程 ``_nas_pump`` 每 80ms 消费), 绝不跨线程直接调 tkinter。
"""
import queue
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, simpledialog, ttk

from core import nas_api

import keepalive_core as core

from gui.theme import *  # noqa: F401,F403

TREE_STYLE = "Nas.Treeview"
DEFAULT_HOST = "192.168.31.1:5244"
DEFAULT_USER = "admin"
PROGRESS_MIN_INTERVAL = 0.5     # 上传/下载进度写日志的最小间隔(秒)


class NasUiMixin:
    """「NAS 管家」窗口。"""

    # ------------------------------------------------------------------ 窗口
    def show_nas_window(self):
        existing = getattr(self, "_nas_window", None)
        try:
            if existing is not None and existing.winfo_exists():
                existing.deiconify()
                existing.lift()
                existing.focus_force()
                return existing
        except Exception:
            pass

        self._nas_busy = False
        self._nas_uiq = queue.Queue()
        self._nas_gen = getattr(self, "_nas_gen", 0) + 1
        self._nas_path = "/nas"
        self._nas_entries = []
        self._nas_token = ""
        self._nas_pass = ""
        self._nas_last_progress = 0.0

        win = tk.Toplevel(self)
        self._nas_window = win
        win.title("NAS 管家")
        win.configure(bg=BG)
        win.geometry("920x680")
        win.minsize(760, 540)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=CARD_PAD_SUB)
        card.pack(fill="both", expand=True, padx=WINDOW_PAD[0], pady=WINDOW_PAD[1])
        card.columnconfigure(0, weight=1)
        card.rowconfigure(5, weight=1)

        ttk.Label(card, text="NAS 管家", style="DialogTitle.TLabel").grid(
            row=0, column=0, sticky="w")
        lbl_sub = ttk.Label(
            card,
            text=("管理路由器上的 NAS(alist): 查看服务状态、启停服务、浏览/上传/下载"
                  " 12TB 照片盘。文件面直连 alist; 服务控制经工作台令牌转发, 不需要"
                  " SSH。登录口令用系统加密存储, 不落明文。"),
            style="Muted.TLabel", wraplength=800)
        lbl_sub.grid(row=1, column=0, sticky="w", pady=(6, 12))

        # ---------- 服务器连接 ----------
        conf = self._nas_conf()
        conn = ttk.Frame(card, style="Card.TFrame")
        conn.grid(row=2, column=0, sticky="ew")
        for col, weight in ((3, 1), (4, 1)):
            conn.columnconfigure(col, weight=weight)
        ttk.Label(conn, text="服务器", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self._nas_host_var = tk.StringVar(value=conf["host"] or DEFAULT_HOST)
        ttk.Entry(conn, textvariable=self._nas_host_var, width=22).grid(
            row=0, column=1, sticky="w", padx=(6, 12))
        ttk.Label(conn, text="用户", style="Field.TLabel").grid(row=0, column=2, sticky="e")
        self._nas_user_var = tk.StringVar(value=conf["user"] or DEFAULT_USER)
        ttk.Entry(conn, textvariable=self._nas_user_var, width=12).grid(
            row=0, column=3, sticky="w", padx=(6, 12))
        ttk.Label(conn, text="密码", style="Field.TLabel").grid(row=0, column=4, sticky="e")
        self._nas_pass_var = tk.StringVar(value=conf["password"])
        ttk.Entry(conn, textvariable=self._nas_pass_var, width=16,
                  show="*").grid(row=0, column=5, sticky="w", padx=(6, 12))
        ttk.Button(conn, text="连接", style="Accent.TButton",
                   command=self._nas_connect).grid(row=0, column=6)

        # ---------- 服务状态 / 控制 ----------
        svc = ttk.Frame(card, style="Card.TFrame")
        svc.grid(row=3, column=0, sticky="ew", pady=(10, 6))
        self._nas_svc_label = ttk.Label(svc, text="服务状态: 未获取", style="Field.TLabel")
        self._nas_svc_label.grid(row=0, column=0, sticky="w")
        ttk.Button(svc, text="刷新状态", style="Gray.TButton",
                   command=self._nas_refresh_status).grid(row=0, column=1, padx=(12, 6))
        ttk.Button(svc, text="启动服务", style="Gray.TButton",
                   command=lambda: self._nas_service("start")).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(svc, text="停止服务", style="Gray.TButton",
                   command=lambda: self._nas_service("stop")).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(svc, text="重启服务", style="Gray.TButton",
                   command=lambda: self._nas_service("restart")).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(svc, text="打开网页端", style="Gray.TButton",
                   command=self._nas_open_web).grid(row=0, column=5)

        # ---------- 浏览工具条 ----------
        bar = ttk.Frame(card, style="Card.TFrame")
        bar.grid(row=4, column=0, sticky="ew", pady=(10, 6))
        bar.columnconfigure(1, weight=1)
        ttk.Label(bar, text="路径", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self._nas_path_var = tk.StringVar(value=self._nas_path)
        ttk.Entry(bar, textvariable=self._nas_path_var).grid(
            row=0, column=1, sticky="ew", padx=(6, 8))
        ttk.Button(bar, text="前往", style="Gray.TButton",
                   command=self._nas_goto).grid(row=0, column=2, padx=(0, 6))
        ttk.Button(bar, text="上级", style="Gray.TButton",
                   command=self._nas_up).grid(row=0, column=3, padx=(0, 6))
        ttk.Button(bar, text="刷新", style="Gray.TButton",
                   command=lambda: self._nas_browse(refresh=True)).grid(row=0, column=4, padx=(0, 6))
        ttk.Button(bar, text="上传文件", style="Gray.TButton",
                   command=self._nas_upload).grid(row=0, column=5, padx=(0, 6))
        ttk.Button(bar, text="新建文件夹", style="Gray.TButton",
                   command=self._nas_mkdir).grid(row=0, column=6)

        # ---------- 文件表 ----------
        wrap = ttk.Frame(card, style="Inner.TFrame")
        wrap.grid(row=5, column=0, sticky="nsew", pady=(4, 0))
        wrap.columnconfigure(0, weight=1)
        wrap.rowconfigure(0, weight=1)
        cols = ("name", "size", "mtime")
        tree = ttk.Treeview(wrap, columns=cols, show="headings", style=TREE_STYLE,
                            selectmode="browse")
        for key, text, width, anchor in (
                ("name", "名称", 440, "w"), ("size", "大小", 120, "e"),
                ("mtime", "修改时间", 170, "center")):
            tree.heading(key, text=text)
            tree.column(key, width=width, anchor=anchor, stretch=(key == "name"))
        tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        tree.configure(yscrollcommand=scrollbar.set)
        tree.bind("<Double-1>", lambda _e: self._nas_enter_dir())
        self._nas_tree = tree

        # ---------- 选中操作 + 日志 ----------
        acts = ttk.Frame(card, style="Card.TFrame")
        acts.grid(row=6, column=0, sticky="ew", pady=(10, 0))
        ttk.Button(acts, text="下载选中", style="Gray.TButton",
                   command=self._nas_download).grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Button(acts, text="删除选中", style="Gray.TButton",
                   command=self._nas_delete).grid(row=0, column=1, sticky="w")
        self._nas_log = tk.Text(card, height=5, width=1, bg="#09101c", fg="#b7c4d8",
                                font=("PingFang SC", 9), relief="flat", wrap="word",
                                padx=10, pady=8, state="disabled")
        self._nas_log.grid(row=7, column=0, sticky="ew", pady=(10, 0))

        def _nas_close():
            self._nas_window = None
            try:
                while True:
                    self._nas_uiq.get_nowait()
            except queue.Empty:
                pass
            except Exception:
                pass
            try:
                win.destroy()
            except Exception:
                pass

        win.protocol("WM_DELETE_WINDOW", _nas_close)

        def _on_resize(_event=None):
            try:
                wpx = win.winfo_width() - 96
                if wpx > 260:
                    lbl_sub.configure(wraplength=wpx)
            except Exception:
                pass

        win.bind("<Configure>", _on_resize)
        win.after(80, lambda: self._rc_autosize(win))
        self._nas_log_line("提示: 双击文件夹进入; 「连接」会登录并列出 /nas。")
        win.after(80, self._nas_pump)
        if conf["password"] or conf["user"]:
            self._nas_connect()
        else:
            self._nas_refresh_status()
        return win

    # ------------------------------------------------- 线程安全的 UI 更新通道
    def _nas_ui(self, fn):
        """工作线程只允许调用这一个方法: 把 UI 更新排队交给主线程(见 ClashNodesMixin._clash_ui)。"""
        ui_queue = getattr(self, "_nas_uiq", None)
        if ui_queue is None:
            return
        try:
            ui_queue.put((getattr(self, "_nas_gen", 0), fn))
        except Exception:                                    # noqa: BLE001 - 绝不能影响工作线程
            pass

    def _nas_pump(self):
        """主线程消费队列(窗口存活期间每 80ms 一次)。"""
        win = getattr(self, "_nas_window", None)
        ui_queue = getattr(self, "_nas_uiq", None)
        if win is None or ui_queue is None:
            return
        try:
            if not win.winfo_exists():
                return
        except Exception:
            return
        gen = getattr(self, "_nas_gen", 0)
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
                continue
            try:
                fn()
            except Exception:                                # noqa: BLE001 - 单条失败不拖垮泵
                pass
        try:
            win.after(80, self._nas_pump)
        except Exception:
            pass

    # ------------------------------------------------------------------ 配置
    def _nas_conf(self):
        """读 NAS 连接配置(config.json 的 nas 段, 口令 DPAPI 加密)。"""
        section = self.cfg.get("nas") or {}
        password = ""
        if section.get("pass_store") == "dpapi":
            password = core.dpapi_decrypt(section.get("pass_enc", ""))
        return {
            "host": str(section.get("host") or DEFAULT_HOST),
            "user": str(section.get("user") or DEFAULT_USER),
            "password": password,
        }

    def _nas_save_conf(self, host, user, password):
        encrypted = core.dpapi_encrypt(password)
        if password and not encrypted:
            raise nas_api.NasApiError("当前系统无法用 DPAPI 加密 NAS 口令, 已拒绝明文保存",
                                      kind="unknown")
        self.cfg["nas"] = {
            "host": host,
            "user": user,
            "pass_store": "dpapi" if encrypted else "",
            "pass_enc": encrypted,
        }
        core.save_config(self.cfg)

    # ------------------------------------------------------------------ 日志
    def _nas_log_line(self, text):
        box = getattr(self, "_nas_log", None)
        if box is None:
            return
        try:
            if not box.winfo_exists():
                return
        except Exception:
            return
        box.configure(state="normal")
        box.insert("end", "%s\n" % text)
        box.see("end")
        box.configure(state="disabled")

    def _nas_fail(self, exc, prefix=""):
        hint = nas_api.error_hint(exc)
        self._nas_log_line("%s%s" % (("%s: " % prefix) if prefix else "", exc))
        if hint:
            self._nas_log_line(hint)

    # ------------------------------------------------------------------ 服务
    def _nas_rc(self):
        conf = self._rc_settings()
        return conf["host"], conf["port"], conf["token"]

    def _nas_refresh_status(self):
        if getattr(self, "_nas_busy", False):
            return
        host, port, token = self._nas_rc()
        try:
            self._nas_svc_label.configure(text="服务状态: 正在查询…")
        except Exception:
            pass

        def worker():
            try:
                data = nas_api.cgi_request(host, port, token, "status")
                self._nas_ui(lambda: self._nas_render_status(data))
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_svc_fail(err))
            except Exception as exc:                        # noqa: BLE001 - UI 兜底
                self._nas_ui(lambda err=exc: self._nas_svc_fail(err, prefix="读取失败"))

        threading.Thread(target=worker, daemon=True).start()

    def _nas_render_status(self, data):
        alist_on = int(data.get("alist") or 0)
        rclone_on = int(data.get("rclone") or 0)
        ts_on = int(data.get("tailscale") or 0)
        web = str(data.get("web") or "")
        ts_ip = str(data.get("ts_ip") or "")
        if alist_on and rclone_on and web == "200":
            text = "服务状态: ● 运行中(alist ✓ rclone ✓ 网页 ✓)"
        elif alist_on or rclone_on:
            text = ("服务状态: ◐ 部分运行(alist %s rclone %s 网页 %s)"
                    % ("✓" if alist_on else "✗", "✓" if rclone_on else "✗",
                       "✓" if web == "200" else "✗"))
        else:
            text = "服务状态: ○ 未运行 — 点「启动服务」(重启路由器后会自动拉起)"
        if ts_on:
            text += "   |   Tailscale ✓ %s" % (ts_ip or "(未授权)")
        else:
            text += "   |   Tailscale ✗"
        self._nas_svc_label.configure(text=text)
        if not (alist_on and rclone_on):
            self._nas_log_line("NAS 服务没有完全运行: 点上方「启动服务」, 约 15-30 秒后刷新。")

    def _nas_svc_fail(self, exc, prefix="读取失败"):
        self._nas_svc_label.configure(text="服务状态: 查询失败(%s)" % exc)
        self._nas_fail(exc, prefix=prefix)

    def _nas_service(self, op):
        if getattr(self, "_nas_busy", False):
            return
        if op == "stop" and not messagebox.askyesno(
                "NAS 管家", "确定停止路由器上的 alist 与 rclone?\n"
                "(文件将暂时无法访问, 路由器重启后看门狗会自动拉起)"):
            return
        host, port, token = self._nas_rc()
        self._nas_log_line("正在%s服务…" % {"start": "启动", "stop": "停止",
                                            "restart": "重启"}[op])

        def worker():
            try:
                data = nas_api.cgi_request(host, port, token, op, timeout=60)
                self._nas_ui(lambda: self._nas_log_line(str(data.get("msg") or "完成")))
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="服务控制失败"))
            except Exception as exc:                        # noqa: BLE001
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="服务控制失败"))

        threading.Thread(target=worker, daemon=True).start()
        # 控制指令是异步生效的, 延迟几秒自动刷一次状态
        self._nas_ui(lambda: self.after(8000, self._nas_refresh_status))

    def _nas_open_web(self):
        host = (self._nas_host_var.get() or DEFAULT_HOST).strip()
        if "://" not in host:
            host = "http://" + host
        webbrowser.open(host + "/")

    # ------------------------------------------------------------- 连接与浏览
    def _nas_token_of(self):
        """拿到(必要时重新登录)alist token; 失败抛 NasApiError(由 worker 捕获)。"""
        if getattr(self, "_nas_token", ""):
            return self._nas_token
        host = self._nas_host_var.get().strip()
        user = self._nas_user_var.get().strip()
        password = self._nas_pass_var.get()
        self._nas_token = nas_api.login(host, user, password)
        return self._nas_token

    def _nas_connect(self):
        if getattr(self, "_nas_busy", False):
            return
        host = self._nas_host_var.get().strip() or DEFAULT_HOST
        user = self._nas_user_var.get().strip() or DEFAULT_USER
        password = self._nas_pass_var.get()
        self._nas_token = ""
        self._nas_log_line("正在连接 %s …" % host)
        self._nas_busy = True

        def worker():
            try:
                self._nas_save_conf(host, user, password)
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="保存配置失败"))
            except Exception as exc:                        # noqa: BLE001 - 加密失败兜底
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="保存配置失败"))
            try:
                token = nas_api.login(host, user, password)
                self._nas_token = token
                entries = nas_api.fs_list(host, token, self._nas_path, refresh=False)
                self._nas_ui(lambda: self._nas_render_entries(entries))
                self._nas_ui(lambda: self._nas_log_line("连接成功。"))
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="连接失败"))
            except Exception as exc:                        # noqa: BLE001 - UI 兜底
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="连接失败"))
            finally:
                self._nas_ui(lambda: setattr(self, "_nas_busy", False))

        threading.Thread(target=worker, daemon=True).start()
        self._nas_refresh_status()

    def _nas_browse(self, path=None, refresh=False):
        if getattr(self, "_nas_busy", False):
            return
        if path:
            self._nas_path = nas_api.join_path(path)
            self._nas_path_var.set(self._nas_path)
        target = self._nas_path_var.get().strip() or "/nas"
        host = self._nas_host_var.get().strip()
        self._nas_busy = True
        self._nas_log_line("读取 %s …" % target)

        def worker():
            try:
                token = self._nas_token_of()
                entries = nas_api.fs_list(host, token, target, refresh=refresh)
                self._nas_ui(lambda: self._nas_render_entries(entries))
            except nas_api.NasApiError as exc:
                if getattr(exc, "kind", "") == "auth":
                    # token 过期 -> 重新登录一次再试
                    try:
                        host2 = self._nas_host_var.get().strip()
                        token2 = nas_api.login(
                            host2, self._nas_user_var.get().strip(),
                            self._nas_pass_var.get())
                        self._nas_token = token2
                        entries = nas_api.fs_list(host2, token2, target, refresh=refresh)
                        self._nas_ui(lambda: self._nas_render_entries(entries))
                    except nas_api.NasApiError as exc2:
                        self._nas_ui(lambda err=exc2: self._nas_fail(err, prefix="重新登录失败"))
                    except Exception as exc2:               # noqa: BLE001 - UI 兜底
                        self._nas_ui(lambda err=exc2: self._nas_fail(err, prefix="重新登录失败"))
                else:
                    self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="读取失败"))
            except Exception as exc:                        # noqa: BLE001 - UI 兜底
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="读取失败"))
            finally:
                self._nas_ui(lambda: setattr(self, "_nas_busy", False))

        threading.Thread(target=worker, daemon=True).start()

    def _nas_render_entries(self, entries):
        self._nas_entries = entries
        tree = getattr(self, "_nas_tree", None)
        if tree is None:
            return
        try:
            if not tree.winfo_exists():
                return
        except Exception:
            return
        tree.delete(*tree.get_children())
        for entry in entries:
            size = "文件夹" if entry["is_dir"] else nas_api.human_size(entry["size"])
            tree.insert("", "end", values=(entry["name"], size, entry["modified"]))
        if not entries:
            self._nas_log_line("(空目录)")

    def _nas_selected(self):
        tree = getattr(self, "_nas_tree", None)
        if tree is None:
            return None
        selected = tree.selection()
        if not selected:
            return None
        values = tree.item(selected[0], "values")
        if not values:
            return None
        name = str(values[0])
        for entry in self._nas_entries:
            if entry["name"] == name:
                return entry
        return None

    def _nas_enter_dir(self):
        entry = self._nas_selected()
        if entry and entry["is_dir"]:
            self._nas_browse(path=nas_api.join_path(self._nas_path_var.get(), entry["name"]))

    def _nas_goto(self):
        self._nas_browse(path=self._nas_path_var.get().strip())

    def _nas_up(self):
        self._nas_browse(path=nas_api.parent_path(self._nas_path_var.get()))

    # ------------------------------------------------------------- 上传/下载
    def _nas_upload(self):
        if getattr(self, "_nas_busy", False):
            return
        local = filedialog.askopenfilename(title="选择要上传的文件")
        if not local:
            return
        name = local.replace("\\", "/").rsplit("/", 1)[-1]
        host = self._nas_host_var.get().strip()
        remote = nas_api.join_path(self._nas_path_var.get(), name)
        if not messagebox.askyesno(
                "NAS 管家", "上传到 %s ?\n(写速约 3 MB/s, 大文件请耐心等待)" % remote):
            return
        self._nas_busy = True
        self._nas_log_line("上传 %s -> %s" % (name, remote))

        def progress(sent, total):
            now = time.time()
            if now - self._nas_last_progress < PROGRESS_MIN_INTERVAL and sent < (total or 0):
                return
            self._nas_last_progress = now
            if total:
                self._nas_ui(lambda s=sent, t=total: self._nas_log_line(
                    "上传中 %.1f%% (%s / %s)" % (s * 100.0 / t, nas_api.human_size(s),
                                                 nas_api.human_size(t))))
            else:
                self._nas_ui(lambda s=sent: self._nas_log_line(
                    "上传中 %s" % nas_api.human_size(s)))

        def worker():
            try:
                token = self._nas_token_of()
                nas_api.upload_file(host, token, local, remote, progress=progress)
                self._nas_ui(lambda: self._nas_log_line("上传完成: %s" % remote))
                self._nas_ui(lambda: self._nas_browse(refresh=False))
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="上传失败"))
            except Exception as exc:                        # noqa: BLE001 - UI 兜底
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="上传失败"))
            finally:
                self._nas_ui(lambda: setattr(self, "_nas_busy", False))

        threading.Thread(target=worker, daemon=True).start()

    def _nas_download(self):
        if getattr(self, "_nas_busy", False):
            return
        entry = self._nas_selected()
        if entry is None:
            messagebox.showinfo("NAS 管家", "先在列表里选中一个文件。")
            return
        if entry["is_dir"]:
            messagebox.showinfo("NAS 管家", "文件夹不支持直接下载, 请进入后选择文件。")
            return
        local = filedialog.asksaveasfilename(
            title="保存到", initialfile=entry["name"])
        if not local:
            return
        host = self._nas_host_var.get().strip()
        user = self._nas_user_var.get().strip()
        password = self._nas_pass_var.get()
        remote = nas_api.join_path(self._nas_path_var.get(), entry["name"])
        self._nas_busy = True
        self._nas_log_line("下载 %s -> %s" % (remote, local))

        def progress(sent, total):
            now = time.time()
            if now - self._nas_last_progress < PROGRESS_MIN_INTERVAL and sent < (total or 0):
                return
            self._nas_last_progress = now
            if total:
                self._nas_ui(lambda s=sent, t=total: self._nas_log_line(
                    "下载中 %.1f%% (%s / %s)" % (s * 100.0 / t, nas_api.human_size(s),
                                                 nas_api.human_size(t))))
            else:
                self._nas_ui(lambda s=sent: self._nas_log_line(
                    "下载中 %s" % nas_api.human_size(s)))

        def worker():
            try:
                nas_api.download_file(host, user, password, remote, local,
                                      progress=progress)
                self._nas_ui(lambda: self._nas_log_line("下载完成: %s" % local))
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="下载失败"))
            except Exception as exc:                        # noqa: BLE001 - UI 兜底
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="下载失败"))
            finally:
                self._nas_ui(lambda: setattr(self, "_nas_busy", False))

        threading.Thread(target=worker, daemon=True).start()

    def _nas_delete(self):
        if getattr(self, "_nas_busy", False):
            return
        entry = self._nas_selected()
        if entry is None:
            messagebox.showinfo("NAS 管家", "先在列表里选中要删除的项。")
            return
        if not messagebox.askyesno(
                "NAS 管家", "确定删除 %s ?\n(删除后无法恢复)" % entry["name"]):
            return
        host = self._nas_host_var.get().strip()
        dir_path = self._nas_path_var.get().strip()
        self._nas_busy = True

        def worker():
            try:
                token = self._nas_token_of()
                nas_api.fs_remove(host, token, dir_path, [entry["name"]])
                self._nas_ui(lambda: self._nas_log_line("已删除: %s" % entry["name"]))
                self._nas_ui(lambda: self._nas_browse(refresh=False))
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="删除失败"))
            except Exception as exc:                        # noqa: BLE001 - UI 兜底
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="删除失败"))
            finally:
                self._nas_ui(lambda: setattr(self, "_nas_busy", False))

        threading.Thread(target=worker, daemon=True).start()

    def _nas_mkdir(self):
        if getattr(self, "_nas_busy", False):
            return
        name = simpledialog.askstring("NAS 管家", "新文件夹名称:", parent=self._nas_window)
        if not name:
            return
        host = self._nas_host_var.get().strip()
        target = nas_api.join_path(self._nas_path_var.get(), name)
        self._nas_busy = True

        def worker():
            try:
                token = self._nas_token_of()
                nas_api.fs_mkdir(host, token, target)
                self._nas_ui(lambda: self._nas_log_line("已创建: %s" % target))
                self._nas_ui(lambda: self._nas_browse(refresh=False))
            except nas_api.NasApiError as exc:
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="创建失败"))
            except Exception as exc:                        # noqa: BLE001 - UI 兜底
                self._nas_ui(lambda err=exc: self._nas_fail(err, prefix="创建失败"))
            finally:
                self._nas_ui(lambda: setattr(self, "_nas_busy", False))

        threading.Thread(target=worker, daemon=True).start()
