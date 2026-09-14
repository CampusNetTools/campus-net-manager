# -*- coding: utf-8 -*-
"""系统托盘 Mixin (自 app_gui.py 拆分)"""
import os  # noqa: F401
import queue  # noqa: F401
import threading  # noqa: F401
import webbrowser  # noqa: F401
import tkinter as tk  # noqa: F401
from tkinter import ttk, messagebox, filedialog  # noqa: F401

import keepalive_core as core  # noqa: F401
import shared_proxy  # noqa: F401
from PIL import Image, ImageDraw, ImageFont, ImageTk  # noqa: F401

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


class TrayMixin:
    def _make_tray_icon(self):
        """生成系统托盘图标, 64x64 缩到 16x16~32x32 后仍清晰。

        Windows 托盘实际渲染尺寸仅 16~24px, 64x64 图缩放后:
        - 绿色实心圆缩放后仍能保留 (粗形状)
        - 「网」字如用 PIL 默认位图字体 (极小) 则糊化消失

        现在改用 truetype 字体大字号 (>=32px) + 描边强化; truetype
        不可用时降级到几何网状图形 (放射线+节点), 不依赖字体。
        """
        img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # 绿色实心圆 (校园网主题色 #4cc38a)
        d.ellipse([3, 3, 61, 61], fill="#4cc38a")
        cx, cy = 32, 32

        # 优先 truetype 大字号中文 (Win 系统字体目录 + Linux 常见字体)
        font = None
        candidates = [
            (r"C:\Windows\Fonts\msyh.ttc", 0),       # 微软雅黑
            (r"C:\Windows\Fonts\msyh.ttc", 1),       # 微软雅黑 粗
            (r"C:\Windows\Fonts\msyhbd.ttc", 0),     # 微软雅黑 Bold
            (r"C:\Windows\Fonts\simhei.ttf", 0),     # 黑体
            (r"C:\Windows\Fonts\simsun.ttc", 0),     # 宋体
            ("/System/Library/Fonts/PingFang.ttc", 0),   # macOS 苹方
            ("/System/Library/Fonts/STHeiti Medium.ttc", 0),  # macOS 黑体
            ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),  # Linux 文泉驿
        ]
        for path, idx in candidates:
            try:
                font = ImageFont.truetype(path, 36, index=idx)
                break
            except Exception:
                continue

        if font is not None:
            # 居中绘制「网」字: PIL 的 d.text() 锚点 (0,0) 对应字形 bbox[0],bbox[1]
            # (含 bearing 溢出), 视觉中心 = (tx+bbox[0]+tw/2, ty+bbox[1]+th/2)。
            # 令视觉中心 = (cx, cy) 解出 tx, ty。
            text = "网"
            bbox = d.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
            tx = cx - bbox[0] - tw // 2
            ty = cy - bbox[1] - th // 2
            # 4 向绿色描边 (与底色同色, 缩到 16x16 时描边会被部分吃掉,
            # 但剩下的笔画仍然清晰, 不会糊成绿圆)
            for dx, dy in ((-2, 0), (2, 0), (0, -2), (0, 2)):
                d.text((tx + dx, ty + dy), text, font=font, fill="#4cc38a")
            d.text((tx, ty), text, font=font, fill="#ffffff")
        else:
            # truetype 不可用: 几何网状 (4 根白色放射线 + 中心节点)
            import math
            for ang in (45, 135, 225, 315):
                a = math.radians(ang)
                x2 = cx + int(22 * math.cos(a))
                y2 = cy + int(22 * math.sin(a))
                d.line([(cx, cy), (x2, y2)], fill="#ffffff", width=3)
            d.ellipse([cx - 5, cy - 5, cx + 5, cy + 5], fill="#ffffff")
        return img

    def _make_tray(self):
        """创建托盘。macOS 用 NSStatusItem(pyobjc, 主线程安全)——
        pystray 在 macOS 新版上后台线程跑 NSApplication 会 SIGTRAP
        (NSUpdateCycleInitialize, v5.0.3 及之前每次最小化到托盘都崩)。
        返回 True 表示托盘可用。"""
        if core.IS_MACOS:
            try:
                from gui.tray_mac import MacTray
                self._tray = MacTray("🌐 校园网管家",
                                     self._show_from_tray, self._quit_from_tray)
                return True
            except Exception as e:
                try:
                    self._log("菜单栏托盘创建失败: %r" % e)
                except Exception:
                    pass
                return False
        if HAS_TRAY:
            menu = pystray.Menu(
                pystray.MenuItem("打开主界面", self._show_from_tray),
                pystray.MenuItem("退出", self._quit_from_tray))
            self._tray = pystray.Icon("CampusNetManager", self._make_tray_icon(),
                                      "校园网连接管家", menu)
            threading.Thread(target=self._tray.run, daemon=True).start()
            return True
        return False

    def _hide_to_tray(self):
        self.withdraw()
        if not getattr(self, "_tray", None):
            if not self._make_tray():
                # 托盘不可用: 不能让窗口凭空消失, 恢复显示
                self.deiconify()
                try:
                    self._log("托盘不可用, 窗口保持显示")
                except Exception:
                    pass

    def _show_from_tray(self):
        if getattr(self, "_tray", None):
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        self.deiconify()
        self.lift()
        self.attributes("-topmost", True)
        self.after(300, lambda: self.attributes("-topmost", False))

    def _quit_from_tray(self):
        if getattr(self, "_tray", None):
            try:
                self._tray.stop()
            except Exception:
                pass
            self._tray = None
        self.stop_daemon()
        console = getattr(self, "_console", None)
        if console and getattr(console, "running", False):
            try:
                console.stop()
            except Exception:
                pass
        self.destroy()
        # macOS: Tk 销毁后 AppKit/线程残留偶发 SIGTRAP 假崩溃;
        # 清理已全部完成(守护/代理/控制台/配置), 硬退出保平安。
        if core.IS_MACOS:
            os._exit(0)

    def on_close(self):
        if self.daemon and self.daemon.is_alive():
            if self._make_tray() or getattr(self, "_tray", None):
                self.withdraw()
                self._log("已最小化到菜单栏，守护继续运行（点菜单栏 🌐 图标可恢复）")
                return
            if not messagebox.askyesno("停止守护?", "守护正在运行。\n关闭窗口将停止连接管家，确定关闭吗？"):
                return
            self.stop_daemon()
        console = getattr(self, "_console", None)
        if console and console.running:
            console.stop()
        self.destroy()
        # macOS: 同 _quit_from_tray, 避免退出阶段 AppKit 假崩溃弹窗
        if core.IS_MACOS:
            os._exit(0)


