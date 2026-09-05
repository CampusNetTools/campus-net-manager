# -*- coding: utf-8 -*-
"""测速窗口 Mixin (自 app_gui.py 拆分)"""
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


class SpeedWindowMixin:
    def show_speed_test(self):
        """轻量测速：可测当前 VPN 路径，也可在 macOS 上绑定物理网卡绕过 VPN。"""
        win = tk.Toplevel(self)
        win.title("网络测速")
        win.configure(bg=BG)
        win.geometry("680x570")
        win.resizable(False, False)
        win.transient(self)

        card = ttk.Frame(win, style="Card.TFrame", padding=(24, 20))
        card.pack(fill="both", expand=True, padx=16, pady=16)
        ttk.Label(card, text="网络测速", style="DialogTitle.TLabel").pack(anchor="w")
        subtitle = ttk.Label(card, text="", style="Muted.TLabel")
        subtitle.pack(anchor="w", pady=(4, 12))
        vpn_row = ttk.Frame(card, style="Inner.TFrame")
        vpn_row.pack(fill="x")
        vpn_dot = tk.Label(vpn_row, text="●", fg=MUTED, bg=CARD, font=("Arial", 11))
        vpn_dot.pack(side="left", padx=(0, 8))
        vpn_status = ttk.Label(vpn_row, text="正在识别 VPN…", style="Card.TLabel")
        vpn_status.pack(side="left")

        def refresh_speed_plan():
            plan = core.automatic_speed_test_plan()
            if plan["compare"]:
                vpn_dot.configure(fg=GREEN)
                vpn_status.configure(text="已检测到 VPN，将自动对比两种连接")
                subtitle.configure(text="自动测试经过 VPN 与未经过 VPN的网络；预计使用约 24 MB 流量")
            elif plan["vpn_active"]:
                vpn_dot.configure(fg=YELLOW)
                vpn_status.configure(text="已检测到 VPN，当前系统仅测试 VPN 连接")
                subtitle.configure(text="本次预计使用约 12 MB 流量")
            else:
                vpn_dot.configure(fg=MUTED)
                vpn_status.configure(text="未检测到 VPN，将测试当前网络")
                subtitle.configure(text="本次预计使用约 12 MB 流量")
            return plan

        refresh_speed_plan()

        result_box = ttk.Frame(card, style="Surface.TFrame", padding=(14, 14))
        result_box.pack(fill="both", expand=True, pady=(16, 12))
        for col in range(3):
            result_box.columnconfigure(col, weight=1)
        for row in range(2):
            result_box.rowconfigure(row, weight=1)
        values = {}
        subtexts = {}
        metrics = (("latency", "延迟"), ("download", "下载"), ("upload", "上传"),
                   ("jitter", "抖动"), ("success", "请求成功率"), ("quality", "网络质量"))
        for index, (key, title) in enumerate(metrics):
            row, col = divmod(index, 3)
            cell = ttk.Frame(result_box, style="Metric.TFrame", padding=(12, 10))
            cell.grid(row=row, column=col, sticky="nsew", padx=4, pady=4)
            cell.columnconfigure(0, weight=1)
            ttk.Label(cell, text=title, style="MetricTitle.TLabel").grid(row=0, column=0)
            label = ttk.Label(cell, text="—", style="MetricValue.TLabel")
            label.grid(row=1, column=0, pady=(5, 4))
            sublabel = ttk.Label(cell, text=" ", style="MetricSub.TLabel", anchor="center")
            sublabel.grid(row=2, column=0, sticky="ew")
            values[key] = label
            subtexts[key] = sublabel
        path_label = ttk.Label(result_box, text="点击下方按钮开始自动测速", style="SurfaceMuted.TLabel")
        path_label.grid(row=2, column=0, columnspan=3, pady=(10, 2))
        detail_label = ttk.Label(result_box, text="", style="SurfaceMuted.TLabel")
        detail_label.grid(row=3, column=0, columnspan=3)

        def set_metric_hints():
            hints = {
                "latency": "TCP/TLS 校正", "download": "当前路径", "upload": "当前路径",
                "jitter": "越低越稳定", "success": "6 次请求", "quality": "综合评分",
            }
            for key, text in hints.items():
                subtexts[key].configure(text=text)

        def clear_metric_subtexts():
            for label in subtexts.values():
                label.configure(text=" ")

        def set_running(running, comparing=False):
            btn.configure(state="disabled" if running else "normal",
                          text=("正在自动对比…" if comparing else "测速中…") if running else "开始测速")

        def render(result):
            values["latency"].configure(text="%.0f ms" % result["latency_ms"])
            values["download"].configure(text="%.1f Mbps" % result["download_mbps"])
            values["upload"].configure(text="%.1f Mbps" % result["upload_mbps"])
            values["jitter"].configure(text="%.1f ms" % result["jitter_ms"])
            values["success"].configure(text="%.0f%%" % result["success_rate"])
            values["quality"].configure(text="%d · %s" % (result["quality_score"], result["quality_grade"]))
            path_label.configure(text=result["path_label"])
            detail_label.configure(text="接口：%s    测试流量：%.1f MB" % (
                result["interface"] or "系统默认", result["traffic_mb"]))

        def finish(result=None, error=None):
            set_running(False)
            if error:
                path_label.configure(text="测速失败：%s" % error)
                self._log("测速失败: %s" % error)
                return
            render(result)
            set_metric_hints()
            self._log("测速完成 [%s] 延迟 %.0fms / 下载 %.1fMbps / 上传 %.1fMbps" % (
                result["path_label"], result["latency_ms"], result["download_mbps"], result["upload_mbps"]))

        def finish_compare(results=None, error=None, errors=None):
            set_running(False)
            if error:
                path_label.configure(text="VPN 对比失败：%s" % error)
                return
            vpn_result, physical_result = results
            # 单路径容错: 若某一路径失败, 展示成功的路径, 并对失败路径给出文字提示
            if vpn_result is None and physical_result is None:
                path_label.configure(text="两条路径均测速失败：%s" % ("；".join(errors) if errors else "未知错误"))
                return
            if physical_result is None:
                # 只有 VPN 路径成功
                render(vpn_result)
                set_metric_hints()
                detail_label.configure(text="直连网络路径测速失败，已显示经过 VPN 的结果" +
                                       ("（%s）" % errors[0] if errors else ""))
                path_label.configure(text="当前显示：经过 VPN 的测速结果（直连路径失败）")
                self._log("测速完成 [仅VPN路径] 延迟 %.0fms / 下载 %.1fMbps / 上传 %.1fMbps%s"
                          % (vpn_result["latency_ms"], vpn_result["download_mbps"],
                             vpn_result["upload_mbps"], ("；直连失败: %s" % errors[0]) if errors else ""))
                return
            if vpn_result is None:
                # 只有直连(physical)路径成功
                render(physical_result)
                set_metric_hints()
                detail_label.configure(text="经过 VPN 的路径测速失败，已显示直连网络结果" +
                                       ("（%s）" % errors[0] if errors else ""))
                path_label.configure(text="当前显示：直连网络测速结果（VPN 路径失败）")
                self._log("测速完成 [仅直连路径] 延迟 %.0fms / 下载 %.1fMbps / 上传 %.1fMbps%s"
                          % (physical_result["latency_ms"], physical_result["download_mbps"],
                             physical_result["upload_mbps"], ("；VPN失败: %s" % errors[0]) if errors else ""))
                return
            render(vpn_result)
            latency_delta = vpn_result["latency_ms"] - physical_result["latency_ms"]
            down_change = (vpn_result["download_mbps"] / max(physical_result["download_mbps"], 0.01) - 1.0) * 100.0
            up_change = (vpn_result["upload_mbps"] / max(physical_result["upload_mbps"], 0.01) - 1.0) * 100.0
            jitter_delta = vpn_result["jitter_ms"] - physical_result["jitter_ms"]
            comparison = {
                "latency": "直连 %.0f ms  ·  VPN %+.0f ms" % (physical_result["latency_ms"], latency_delta),
                "download": "直连 %.1f Mbps  ·  VPN %+.0f%%" % (physical_result["download_mbps"], down_change),
                "upload": "直连 %.1f Mbps  ·  VPN %+.0f%%" % (physical_result["upload_mbps"], up_change),
                "jitter": "直连 %.1f ms  ·  VPN %+.1f ms" % (physical_result["jitter_ms"], jitter_delta),
                "success": "直连 %.0f%%  ·  VPN %.0f%%" % (physical_result["success_rate"], vpn_result["success_rate"]),
                "quality": "直连 %d · %s" % (physical_result["quality_score"], physical_result["quality_grade"]),
            }
            for key, text in comparison.items():
                subtexts[key].configure(text=text)
            path_label.configure(text="当前显示：经过 VPN 的测速结果")
            detail_label.configure(text="已自动与直连网络对比    每种连接约 %.1f MB" % vpn_result["traffic_mb"])

        def start():
            plan = refresh_speed_plan()
            compare = plan["compare"]
            set_running(True, comparing=compare)
            for label in values.values():
                label.configure(text="…")
            clear_metric_subtexts()
            def progress(text):
                self.after(0, lambda value=text: path_label.configure(text=value))
            def work():
                try:
                    if compare:
                        vpn_result = None
                        physical_result = None
                        errors = []
                        try:
                            vpn_result = core.run_speed_test("current", progress=progress)
                        except Exception as exc:
                            errors.append("经过 VPN 路径测速失败：%s" % exc)
                        try:
                            physical_result = core.run_speed_test("physical", progress=progress)
                        except Exception as exc:
                            errors.append("直连网络路径测速失败：%s" % exc)
                        # 两条路径独立容错: 只要有一条成功就展示结果, 失败路径用 None 占位提示
                        self.after(0, lambda v=vpn_result, p=physical_result, e=errors:
                                   finish_compare(results=(v, p), errors=e))
                    else:
                        result = core.run_speed_test("current", progress=progress)
                        self.after(0, lambda: finish(result=result))
                except Exception as exc:
                    error = str(exc)
                    callback = finish_compare if compare else finish
                    self.after(0, lambda value=error, target=callback: target(error=value))
            threading.Thread(target=work, daemon=True).start()

        actions = ttk.Frame(card, style="Inner.TFrame")
        actions.pack(fill="x")
        actions.columnconfigure(0, weight=1)
        btn = ttk.Button(actions, text="开始测速", style="Accent.TButton", command=start)
        btn.grid(row=0, column=0, sticky="ew")


