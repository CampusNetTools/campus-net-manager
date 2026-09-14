# -*- coding: utf-8 -*-
"""系统托盘图标测试: 验证图标生成函数不抛异常 + 尺寸正确 + 不依赖 tk。"""
import os
import sys
import unittest


# 不依赖 tkinter / pystray, 直接读源文件避开顶部 import。
def _load_make_tray_icon():
    """从 gui/tray.py 源码里提取 _make_tray_icon 函数字节码执行。

    项目测试机(Python 3.13 managed) 没装 tkinter, 直接 `import gui.tray`
    会 ModuleNotFoundError; 用 runpy 加载模块捕获异常路径太重, 这里
    直接执行源文件里相关行 (无 tkinter 依赖路径)。"""
    src_path = os.path.join(
        os.path.dirname(__file__), "..", "gui", "tray.py")
    with open(src_path, encoding="utf-8") as f:
        src = f.read()
    # 截到 class TrayMixin 之后, 取出 _make_tray_icon 函数字符串
    idx = src.find("class TrayMixin")
    if idx < 0:
        raise RuntimeError("TrayMixin not found in tray.py")
    # 找到方法定义 (4 空格缩进的 def _make_tray_icon)
    fn_start = src.find("def _make_tray_icon", idx)
    fn_end = src.find("\n    def ", fn_start + 1)
    body = src[fn_start:fn_end]
    # 把方法脱壳成顶层函数 (去掉 self, 加 PIL import)
    env = {}
    exec(compile(
        "from PIL import Image, ImageDraw, ImageFont\n"
        "import math\n"
        + body.replace("def _make_tray_icon(self):",
                      "def _make_tray_icon():"),
        "<tray.py extract>", "exec"), env)
    return env["_make_tray_icon"]


class TrayIconTests(unittest.TestCase):
    def setUp(self):
        self.make_icon = _load_make_tray_icon()

    def test_returns_pil_image_with_expected_size(self):
        img = self.make_icon()
        self.assertEqual(img.size, (64, 64))
        self.assertIn(img.mode, ("RGBA", "RGB"))

    def test_draws_green_disk_with_white_glyph(self):
        """验证图标是绿底 + 白字(不是空绿圆)。

        之前版本的 bug: 仅画了绿圆, 默认位图字体 8x8 像素, 64x64 上
        几乎不可见, 缩到 16x16 完全糊化, 用户看到的就是纯绿圆点。
        现在必须能看到白色像素(字 + 描边)。
        """
        from PIL import Image
        img = self.make_icon().convert("RGB")
        # 圆盘绿色像素占比应 > 50% (背景大圆)
        green = 0
        white = 0
        total = img.size[0] * img.size[1]
        for x in range(img.size[0]):
            for y in range(img.size[1]):
                r, g, b = img.getpixel((x, y))
                if g > r and g > b and g > 100:  # 绿色
                    green += 1
                elif r > 200 and g > 200 and b > 200:  # 白色
                    white += 1
        self.assertGreater(green / total, 0.5,
                           "绿色背景圆占比应 > 50%")
        self.assertGreater(white / total, 0.05,
                           "白色字形占比应 > 5% (字 + 描边可见)")

    def test_survives_resize_to_tray_size(self):
        """缩到 32/16/24 后仍有可识别的白色字形(像素占比 > 5%)。

        之前版本(图标只有绿圆 + 小字)的 bug: 64x64 缩到 16x16 后
        「网」字几乎完全糊化, 整个图标变成纯绿点。"""
        from PIL import Image
        img = self.make_icon().convert("RGB")

        def white_ratio(img):
            """统计白色像素占比(R>200 G>200 B>200)。"""
            total = img.size[0] * img.size[1]
            white = 0
            for x in range(img.size[0]):
                for y in range(img.size[1]):
                    p = img.getpixel((x, y))
                    if p[0] > 200 and p[1] > 200 and p[2] > 200:
                        white += 1
            return white / total

        # 64x64 原图: 字 + 描边, 白色占比应 > 8%
        self.assertGreater(white_ratio(img), 0.08,
                           "64x64 白色像素太少, 字体可能没加载")

        # 缩到托盘实际尺寸: 缩放后仍能识别字形
        # 不同缩放尺寸阈值不同: 32x32 是主流, 16x16 字会被吃成几像素
        thresholds = {32: 0.05, 24: 0.03, 16: 0.01}
        for size, threshold in thresholds.items():
            small = img.resize((size, size), Image.LANCZOS)
            r = white_ratio(small)
            self.assertGreater(
                r, threshold,
                "缩到 %dx%d 后白色像素占比 %.1f%% < %.1f%%, 「网」字已糊掉"
                % (size, size, r * 100, threshold * 100))


if __name__ == "__main__":
    unittest.main()