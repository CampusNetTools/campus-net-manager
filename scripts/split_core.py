#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 keepalive_core.py 机械拆分为 core/ 包。

约定:
- 每个子模块头部 `from core.common import *` + `from core import common`
- 跨模块函数调用统一改为 `模块名.函数(` 风格, 常量改为 `common.X`
- 这样测试 patch 只需指向"定义所在模块"一个固定位置
"""
import re

SRC = "keepalive_core.py"
with open(SRC, encoding="utf-8") as f:
    lines = f.readlines()

# (锚点起始正则, 归属模块) —— 按文件顺序, 第一条命中的锚点之前的归上一个模块
CHUNKS = [
    ("common",  r"^# -\*- coding"),
    ("config",  r"^def default_profile\("),
    ("history", r"^def record_network_history\("),
    ("netinfo", r"^def _run_decode\("),
    ("speed",   r"^def _curl_speed_request\("),
    ("router",  r"^OUI_BRANDS = \{"),
    ("portal",  r"^class _NoRedirect"),
    ("netinfo", r"^def get_connection_mode\("),   # get_connection_mode 挪到 netinfo
    ("matching",r"^def profile_has_credentials\("),
    ("auth",    r"^def auth_reachable\("),
    ("sysutils",r"^def now_str\("),
    ("auth",    r"^def http_get\("),              # http_get 起到 ensure_login 归 auth
    ("daemon",  r"^class KeepAliveDaemon"),
    ("sysutils",r"^def keep_awake_start\("),
    ("facade",  r"^APP_VERSION = "),
]

# 找锚点行号
anchors = []
for mod, pat in CHUNKS:
    rx = re.compile(pat)
    for i, ln in enumerate(lines):
        if rx.search(ln):
            anchors.append((i, mod))
            break
    else:
        raise SystemExit("锚点未找到: %s" % pat)
anchors.sort()
anchors.append((len(lines), None))

# 切 chunk: (模块, [行])
chunks = []
for (start, mod), (end, _) in zip(anchors, anchors[1:]):
    chunks.append((mod, lines[start:end]))

# 收集每个模块拥有的顶层名字
DEF_RE = re.compile(r"^(?:def|class)\s+([A-Za-z_][A-Za-z_0-9]*)")
CONST_RE = re.compile(r"^\s*([A-Z][A-Z_0-9]+)\s*=")
owner = {}
module_lines = {}
for mod, chunk in chunks:
    module_lines.setdefault(mod, []).extend(chunk)
for mod, chunk in chunks:
    for ln in chunk:
        m = DEF_RE.match(ln) or CONST_RE.match(ln)
        if m:
            owner[m.group(1)] = mod
# keep_awake 变量
owner.setdefault("_keep_awake_proc", "sysutils")
owner.setdefault("_keep_awake_lock", "sysutils")
owner["_AUTOSTART_NAME"] = "sysutils"
owner["_MAC_LAUNCH_LABEL"] = "sysutils"
owner["AUTOSTART_CMD"] = "sysutils"

COMMON_CONSTS = {n for n, m in owner.items() if m == "common"}

def rewrite(mod, text):
    """跨模块引用加前缀。"""
    for name, own in sorted(owner.items(), key=lambda kv: -len(kv[0])):
        if own == mod or own == "facade":
            continue
        if name.startswith("_") and not name.startswith("_run") and not name.startswith("_curl") \
           and not name.startswith("_profile") and not name.startswith("_fmt") \
           and not name.startswith("_brand") and not name.startswith("_arp") \
           and not name.startswith("_private") and not name.startswith("_origin") \
           and not name.startswith("_same") and not name.startswith("_portal") \
           and not name.startswith("_extract") and not name.startswith("_probe") \
           and not name.startswith("_latency") and not name.startswith("_trim") \
           and not name.startswith("_NoRedirect") and not name.startswith("_keep_awake") \
           and not name.startswith("_AUTOSTART") and not name.startswith("_MAC"):
            continue
        # 函数调用: name(  ->  own.name(
        text = re.sub(r"(?<![\w.])%s\(" % re.escape(name), "%s.%s(" % (own, name), text)
        # 常量裸引用 (全大写)
        if name.isupper():
            text = re.sub(r"(?<![\w.])%s\b(?!\s*[=(])" % re.escape(name),
                          "%s.%s" % (own, name), text)
    return text

HEADER = '''# -*- coding: utf-8 -*-
"""%(title)s (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
'''

TITLES = {
    "common": "公共导入与常量",
    "config": "档案与配置管理",
    "history": "网络历史记录与断网时间线",
    "netinfo": "系统网络信息探测",
    "speed": "测速与网络质量评分",
    "router": "路由器探测/体检/中继指引",
    "portal": "认证服务器( captive portal )探测",
    "matching": "档案匹配与校园网环境判定",
    "auth": "Dr.COM 认证与联网检测",
    "sysutils": "日志/通知/自启/电源断言/单实例锁",
    "daemon": "保活守护线程",
}

def module_names(mod, text):
    """该模块文本中引用了哪些其他模块。"""
    refs = set()
    for other in set(owner.values()) - {mod, "facade", "common"}:
        if re.search(r"\b%s\.\w+" % other, text):
            refs.add(other)
    return refs

import os
os.makedirs("core", exist_ok=True)
with open("core/__init__.py", "w", encoding="utf-8") as f:
    f.write("")

for mod, chunk in module_lines.items():
    if mod == "facade":
        continue
    text = "".join(chunk)
    if mod != "common":
        text = rewrite(mod, text)
    refs = module_names(mod, text)
    if mod == "common":
        refs = set()  # common 永不依赖其他子模块; "config.json" 等字符串会误匹配
    # 模块自身顶层名字全部进 __all__ (含下划线, 供 facade star-import re-export)
    names = []
    for ln in chunk:
        m = DEF_RE.match(ln) or CONST_RE.match(ln)
        if m and m.group(1) not in names:
            names.append(m.group(1))
        if mod == "common":
            # 标准库 import 绑定名也要 re-export (子模块靠 from core.common import * 获得)
            im = re.match(r"^import\s+[\w.]+\s+as\s+(\w+)", ln) or re.match(r"^import\s+(\w+)", ln)
            if im and im.group(1) not in names:
                names.append(im.group(1))
    if mod == "common":
        body = '# -*- coding: utf-8 -*-\n"""%s (自 keepalive_core.py 拆分)"""\n' % TITLES[mod]
    else:
        body = HEADER % {"title": TITLES[mod]}
        if refs:
            body += "from core import %s  # noqa: F401\n" % ", ".join(sorted(refs))
    body += "\n__all__ = %r\n\n" % names + text.rstrip() + "\n"
    with open("core/%s.py" % mod, "w", encoding="utf-8") as f:
        f.write(body)
    print("写入 core/%s.py (%d 行, 引用: %s)" % (mod, len(chunk), ",".join(sorted(refs)) or "无"))

# facade: APP_VERSION 起到文件尾
facade_text = "".join(module_lines["facade"])
facade_text = rewrite("facade", facade_text)
refs = module_names("facade", facade_text)

FACADE = '''# -*- coding: utf-8 -*-
"""
校园网连接管家 - 核心模块门面 (facade)

v3.0.0 起实现拆分到 core/ 包, 本文件只re-export, 保持
`import keepalive_core` / `patch.object(keepalive_core, ...)` 旧代码可用。
唯一权威版本号: 本文件 APP_VERSION。
"""
import os  # noqa: F401  (测试 patch core.os)
import subprocess  # noqa: F401  (测试 patch core.subprocess)
import sys  # noqa: F401

from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core.config import *  # noqa: F401,F403
from core.history import *  # noqa: F401,F403
from core.netinfo import *  # noqa: F401,F403
from core.speed import *  # noqa: F401,F403
from core.router import *  # noqa: F401,F403
from core.portal import *  # noqa: F401,F403
from core.matching import *  # noqa: F401,F403
from core.auth import *  # noqa: F401,F403
from core.sysutils import *  # noqa: F401,F403
from core.daemon import *  # noqa: F401,F403
%(refs)s


%(body)s
'''
ref_line = ("from core import %s  # noqa: F401" % ", ".join(sorted(refs))) if refs else ""
with open("keepalive_core.py", "w", encoding="utf-8") as f:
    f.write(FACADE % {"refs": ref_line, "body": facade_text.rstrip()})
print("重写 keepalive_core.py (facade, 引用: %s)" % (",".join(sorted(refs)) or "无"))
