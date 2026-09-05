#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本号单源同步工具。

唯一权威版本号: keepalive_core.py 的 APP_VERSION。
本脚本把它同步到其余位置, 消除"三同步"人肉步骤(历史教训: v2.9.4 只改 GUI 漏改
APP_VERSION, 构建产物版本号回退)。

用法:
    python scripts/sync_version.py          # 同步 README 徽章并校验 CHANGELOG
    python scripts/sync_version.py --check  # 只校验不同步, 不一致时退出码 1 (CI 用)
"""
import os
import re
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_FILE = os.path.join(PROJECT_DIR, "keepalive_core.py")
README_FILE = os.path.join(PROJECT_DIR, "README.md")
CHANGELOG_FILE = os.path.join(PROJECT_DIR, "CHANGELOG.md")

BADGE_RE = re.compile(r"(badge/下载-v)[0-9]+\.[0-9]+\.[0-9]+(-green)")


def read_app_version():
    with open(CORE_FILE, encoding="utf-8") as f:
        m = re.search(r'^APP_VERSION\s*=\s*"([0-9]+\.[0-9]+\.[0-9]+)"', f.read(), re.M)
    if not m:
        sys.exit("错误: 未在 keepalive_core.py 找到 APP_VERSION")
    return m.group(1)


def check_changelog(version):
    with open(CHANGELOG_FILE, encoding="utf-8") as f:
        head = f.read(2000)
    return ("## v%s" % version) in head


def sync_readme(version, check_only):
    with open(README_FILE, encoding="utf-8") as f:
        content = f.read()
    m = BADGE_RE.search(content)
    if not m:
        print("警告: README.md 未找到下载徽章, 跳过")
        return True
    current = m.group(0)
    expected = "badge/下载-v%s-green" % version
    if current == expected:
        return True
    if check_only:
        print("不一致: README 徽章 %s, 应为 %s" % (current, expected))
        return False
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(BADGE_RE.sub(lambda _m: expected, content, count=1))
    print("已同步 README 徽章: -> v%s" % version)
    return True


def main():
    check_only = "--check" in sys.argv
    version = read_app_version()
    ok = True
    if not check_changelog(version):
        print("不一致: CHANGELOG.md 顶部缺少 ## v%s 条目" % version)
        ok = False
    if not sync_readme(version, check_only):
        ok = False
    if ok:
        print("版本号一致: v%s (APP_VERSION / CHANGELOG / README)" % version)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
