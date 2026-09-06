# -*- coding: utf-8 -*-
"""深色主题常量 + 排版系统 (自 app_gui.py 拆分)"""

# ---------- 颜色 ----------
BG = "#0b1220"
CARD = "#131d2e"
CARD2 = "#1b2940"
METRIC = "#17243a"
BORDER = "#2a3a53"
FG = "#f3f7fc"
MUTED = "#8fa1ba"
ACCENT = "#4f7cff"
ACCENT_HOVER = "#416de8"
GREEN = "#32c48d"
RED = "#f06478"
YELLOW = "#f1b84b"

# ---------- 字体 ----------
FONT = ("PingFang SC", 11)
FONT_S = ("PingFang SC", 10)
FONT_M = ("PingFang SC", 13, "bold")
FONT_L = ("PingFang SC", 24, "bold")
FONT_MONO = ("Menlo", 10)        # 日志 / 等宽数字

# ---------- 排版 8px 网格 ----------
# 大多数窗口的内边距统一为 PAD_XL/PAD_M
PAD_XS = 4
PAD_S = 8
PAD_M = 12
PAD_L = 16
PAD_XL = 20
PAD_XXL = 24

# 卡片四角内边距 (横, 纵) —— 主窗走小, 子窗略大
# Card padding 主窗: card内边距; 子窗: (24, 22)
CARD_PAD_MAIN = (12, 10)         # 主窗功能卡片
CARD_PAD_SUB = (24, 22)          # 子窗口外框
WINDOW_PAD = (18, 18)            # 子窗口外框留白

# 段间距 (垂直): 上一段结束到本段标题
GAP_SECTION = 20
GAP_FORM_ROW = 14
GAP_LABEL_TO_FIELD = 6
GAP_FIELD_TO_HINT = 4
GAP_BUTTON_X = 8                 # 横向按钮间距

# 字段说明自动换行宽度
DESC_WRAP_FEATURE = 220
DESC_WRAP_FORM = 460
DESC_WRAP_DIALOG = 560
DESC_WRAP_LONG = 600


