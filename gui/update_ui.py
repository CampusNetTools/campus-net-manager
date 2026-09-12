# -*- coding: utf-8 -*-
"""自动更新 UI Mixin: 启动后台检查 / 更新弹窗 / 下载进度 / 自替换重启。"""
import os
import subprocess
import sys
import tempfile
import threading
import webbrowser
import zipfile
import tkinter as tk
from tkinter import ttk, messagebox

import keepalive_core as core
import updater

from gui.theme import *  # noqa: F401,F403


class UpdateUiMixin:
    # ---------- 入口 ----------

    def _startup_update_check(self):
        """App 启动后延迟调用: 节流 + 跳过版本, 静默失败。"""
        core.ensure_preferences(self.cfg)
        prefs = self.cfg
        if not prefs.get("auto_update_check", True):
            return
        if not updater.should_auto_check(prefs):
            return
        updater.mark_checked(prefs)
        try:
            core.save_config(self.cfg)
        except Exception:
            pass
        self._bg_check_update(manual=False)

    def _bg_check_update(self, manual=True, on_result=None):
        """检查更新。on_result(info) 提供后: 结果通过回调回报(内联 UI 用), 不再依赖弹窗。"""
        self._log("正在检查更新…" if manual else "后台自动检查更新…")

        def work():
            info = updater.check_for_update(core.APP_VERSION)
            self._log(("发现新版本 %s" % info["tag"]) if info else "更新检查无结果")
            self.after(0, lambda: self._on_update_checked(info, manual, on_result))
        threading.Thread(target=work, daemon=True).start()

    def _on_update_checked(self, info, manual, on_result=None):
        if not info:
            if on_result:
                on_result(None)
                return
            if manual:
                messagebox.showinfo("检查更新", "当前已是最新版本 v%s" % core.APP_VERSION, parent=self)
            return
        core.ensure_preferences(self.cfg)
        prefs = self.cfg
        if not manual and not updater.should_notify(prefs, info["tag"]):
            return
        if on_result:
            on_result(info)
            return
        try:
            self._show_update_dialog(info)
            self._log("更新弹窗已创建")
        except Exception as exc:
            self._log("更新弹窗创建失败: %r" % exc)
            try:
                messagebox.showinfo("发现新版本", "发现新版本 %s" % info["tag"], parent=self)
            except Exception:
                pass

    # ---------- 弹窗 ----------

    def _show_update_dialog(self, info):
        # 先恢复主窗口可见(在托盘/后台时先回前台), 否则 Toplevel 可能不显示
        try:
            if self.state() == "withdrawn":
                self.deiconify()
            self.lift()
        except Exception:
            pass
        win = tk.Toplevel(self)
        win.title("发现新版本 %s" % info["tag"])
        win.configure(bg=BG)
        win.geometry("520x420")
        win.transient(self)
        # 置前防漏看: 窗口在托盘/后台时 Toplevel 可能不可见
        try:
            win.deiconify()
            win.lift()
            win.attributes("-topmost", True)
            win.after(800, lambda: win.attributes("-topmost", False))
            win.focus_force()
        except Exception:
            pass

        tk.Label(win, text="发现新版本 %s（当前 v%s）" % (info["tag"], core.APP_VERSION),
                 bg=BG, fg=FG, font=FONT_M).pack(anchor="w", padx=16, pady=(16, 4))
        tk.Label(win, text="更新内容：", bg=BG, fg=MUTED, font=FONT_S).pack(anchor="w", padx=16)

        notes = tk.Text(win, height=12, bg=CARD, fg=FG, font=FONT_S, relief="flat",
                        highlightthickness=1, highlightbackground=BORDER, wrap="word")
        notes.insert("1.0", info["notes"] or "（无更新说明）")
        notes.configure(state="disabled")
        notes.pack(fill="both", expand=True, padx=16, pady=8)

        btns = tk.Frame(win, bg=BG)
        btns.pack(fill="x", padx=16, pady=(4, 16))

        def do_update():
            win.destroy()
            self._do_update(info)

        def skip_version():
            core.ensure_preferences(self.cfg)
            self.cfg["update_skip_version"] = info["tag"]
            try:
                core.save_config(self.cfg)
            except Exception:
                pass
            win.destroy()

        tk.Button(btns, text="立即更新", command=do_update,
                  bg=ACCENT, fg="white", relief="flat", font=FONT,
                  activebackground=ACCENT_HOVER).pack(side="left")
        tk.Button(btns, text="稍后", command=win.destroy,
                  bg=CARD2, fg=FG, relief="flat", font=FONT).pack(side="left", padx=8)
        tk.Button(btns, text="跳过此版本", command=skip_version,
                  bg=CARD2, fg=MUTED, relief="flat", font=FONT).pack(side="left")
        tk.Button(btns, text="去 Release 页", command=lambda: webbrowser.open(info["page"]),
                  bg=CARD2, fg=MUTED, relief="flat", font=FONT).pack(side="right")

    # ---------- 下载与自替换 ----------

    def _do_update(self, info):
        asset = updater.pick_asset(info["assets"])
        if not asset or not asset.get("url"):
            messagebox.showwarning("自动更新", "未找到本平台的安装包，将打开发布页手动下载。", parent=self)
            webbrowser.open(info["page"])
            return
        if not getattr(sys, "frozen", False):
            # 开发模式(源码运行)不做自替换, 打开 Release 页
            webbrowser.open(info["page"])
            return

        win = tk.Toplevel(self)
        win.title("正在下载更新")
        win.configure(bg=BG)
        win.geometry("420x120")
        win.transient(self)
        win.protocol("WM_DELETE_WINDOW", lambda: None)
        tk.Label(win, text="正在下载 %s …" % asset["name"], bg=BG, fg=FG, font=FONT).pack(pady=(18, 6))
        bar = ttk.Progressbar(win, length=360, mode="determinate")
        bar.pack(pady=6)

        dest = os.path.join(tempfile.gettempdir(), asset["name"])

        def work():
            def progress(done, total):
                pct = (done * 100.0 / total) if total else 0
                self.after(0, lambda: bar.configure(value=pct, maximum=100))
            try:
                # 先解析期望哈希(GitHub digest 或 SHA256SUMS), 下载后立即校验:
                # 网络中间人/半截下载/被替换的包一律挡在"替换运行"之前。
                expected = updater.resolve_expected_sha256(info.get("assets"), asset)
                updater.download(asset["url"], dest, progress=progress)
                ok, msg = updater.verify_download(dest, expected)
                self.after(0, lambda m=msg: self._log("更新包校验: %s" % m))
                if not ok:
                    try:
                        os.remove(dest)
                    except OSError:
                        pass
                    raise RuntimeError("%s\n\n已删除下载的文件, 未做替换。" % msg)
                self.after(0, lambda: self._apply_downloaded(win, dest, asset["name"]))
            except Exception as e:
                # err=e 绑定默认参数: except 块结束后 e 会被删除, lambda 稍后
                # 由事件循环调用时会抛 NameError, 更新失败提示就永远弹不出来。
                self.after(0, lambda err=e: self._on_update_failed(win, info, err))
        threading.Thread(target=work, daemon=True).start()

    def _on_update_failed(self, win, info, err):
        win.destroy()
        self._log("更新下载失败: %s" % err)
        if messagebox.askyesno("自动更新", "下载失败：%s\n\n是否打开发布页手动下载？" % err, parent=self):
            webbrowser.open(info["page"])

    def _apply_downloaded(self, win, path, name):
        win.destroy()
        try:
            if core.IS_MACOS:
                import shutil
                extract_dir = tempfile.mkdtemp(prefix="cnm_update_app_")
                with zipfile.ZipFile(path) as zf:
                    zf.extractall(extract_dir)
                apps = [d for d in os.listdir(extract_dir) if d.endswith(".app")]
                if not apps:
                    raise RuntimeError("压缩包内未找到 .app")
                new_app = os.path.join(extract_dir, apps[0])
                current_app = core.BASE_DIR  # frozen .app 的根目录即 BASE_DIR 的上级推导见下
                # frozen 时 BASE_DIR 指向 .app/Contents/Resources 或 app 支持目录;
                # 自替换以 sys.executable 回溯 .app 根
                exe = sys.executable
                if ".app/Contents/MacOS" in exe:
                    current_app = exe.split(".app/Contents/MacOS")[0] + ".app"
                # 清理同目录旧版本 .app(历史英文名 CampusNetManager.app 等)。
                app_dir = os.path.dirname(current_app)
                stale_apps = updater.find_stale_apps(app_dir, current_app)
                script = updater.write_apply_script(
                    updater.macos_apply_script(current_app, new_app, stale_apps=stale_apps),
                    ".sh")
                subprocess.Popen(["/bin/bash", script],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                current_exe = sys.executable
                exe_dir = os.path.dirname(current_exe)
                # 新 exe 用中文临时名(与正式名「校园网连接管家.exe」一致),
                # 覆盖后不再残留英文 CampusNetManager_new.exe。
                new_exe = os.path.join(exe_dir, "校园网连接管家_new.exe")
                # 先清掉上一轮残留的 _new.exe(若上次更新中途中断, 该残留文件
                # 偶发被 Defender 短持锁, 下面 move 覆盖它必抛 WinError 32)。
                updater.unlink_quietly(new_exe)
                # 用 shutil.move + Windows 文件锁自动重试替换裸调用。
                # 旧实现是 shutil.move 无重试, Defender/PopServ 偶发短持锁直接
                # 弹 WinError 32, 误导用户以为"自动更新失败"。最多重试 6 次, 累计
                # 等待 ≤16s, 完全覆盖 Defender 短锁的 0.5~2s 持续时长。
                updater.move_with_retry(path, new_exe)
                # 最终统一成规范中文名「校园网连接管家.exe」: 无论用户当前跑的是
                # 英文名(CampusNetManager.exe)还是带版本号(…-v5.1.0-win64.exe),
                # 更新后都重命名成中文规范名, 并把旧 exe 一并清掉 —— 目录里只留最新一个。
                final_exe = os.path.join(exe_dir, "校园网连接管家.exe")
                # 枚举同目录旧版本 exe(中文名/英文名/带版本号), 排除最终文件与当前 exe。
                stale = updater.find_stale_executables(exe_dir, current_exe)
                script = updater.write_apply_script(
                    updater.windows_apply_script(current_exe, new_exe,
                                                 stale_exe=stale, final_exe=final_exe),
                    ".bat")
                subprocess.Popen(["cmd", "/c", script],
                                 creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            messagebox.showinfo("自动更新", "下载完成，应用将退出并自动完成更新。", parent=self)
            self.after(800, self.on_close)
        except Exception as e:
            self._log("应用更新失败: %s" % e)
            messagebox.showerror("自动更新", "应用更新失败：%s" % e, parent=self)
