#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""版本号单源同步工具。

唯一权威版本号: keepalive_core.py 的 APP_VERSION。
本脚本把它同步到桌面元数据、Android Buildozer spec 与文档, 消除人肉多处维护
造成构建产物版本号回退的问题。

用法:
    python scripts/sync_version.py          # 同步 Android spec / README 并校验 CHANGELOG
    python scripts/sync_version.py --check  # 只校验不同步, 不一致时退出码 1 (CI 用)
"""
import os
import re
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE_FILE = os.path.join(PROJECT_DIR, "keepalive_core.py")
README_FILE = os.path.join(PROJECT_DIR, "README.md")
CHANGELOG_FILE = os.path.join(PROJECT_DIR, "CHANGELOG.md")
MOBILE_SPEC_FILE = os.path.join(PROJECT_DIR, "mobile", "buildozer.spec")

BADGE_RE = re.compile(
    r"(badge/PR%20Candidate-v)[0-9]+\.[0-9]+\.[0-9]+(-blue)"
)


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
    matches = list(BADGE_RE.finditer(content))
    if len(matches) != 1:
        print("错误: README.md 必须恰有一个 PR Candidate 版本徽章")
        return False
    match = matches[0]
    current = match.group(0)
    expected = "badge/PR%%20Candidate-v%s-blue" % version
    if current == expected:
        return True
    if check_only:
        print("不一致: README 候选版本徽章 %s, 应为 %s" % (current, expected))
        return False
    updated = content[: match.start()] + expected + content[match.end() :]
    with open(README_FILE, "w", encoding="utf-8") as f:
        f.write(updated)
    print("已同步 README 候选版本徽章: -> v%s" % version)
    return True


def sync_mobile_spec(version, check_only):
    """Keep the Android package version aligned with the single source of truth."""
    with open(MOBILE_SPEC_FILE, encoding="utf-8") as f:
        content = f.read()
    pattern = re.compile(r"^(version\s*=\s*)([^\s#]+)(\s*(?:#.*)?)$", re.M)
    matches = list(pattern.finditer(content))
    if len(matches) != 1:
        print("错误: mobile/buildozer.spec 必须恰有一条 version = ...")
        return False
    match = matches[0]
    if match.group(2) == version:
        return True
    if check_only:
        print(
            "不一致: Android Buildozer spec 版本 %s, 应为 %s"
            % (match.group(2), version)
        )
        return False
    updated = content[: match.start(2)] + version + content[match.end(2) :]
    with open(MOBILE_SPEC_FILE, "w", encoding="utf-8") as f:
        f.write(updated)
    print("已同步 Android Buildozer spec: -> v%s" % version)
    return True


def main():
    # Windows CI 控制台默认 cp1252, 打印中文会 UnicodeEncodeError
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    check_only = "--check" in sys.argv
    version = read_app_version()
    ok = True
    if not check_changelog(version):
        print("不一致: CHANGELOG.md 顶部缺少 ## v%s 条目" % version)
        ok = False
    if not sync_mobile_spec(version, check_only):
        ok = False
    if not sync_readme(version, check_only):
        ok = False
    if ok:
        print(
            "版本号一致: v%s (APP_VERSION / Android / CHANGELOG / PR Candidate badge)"
            % version
        )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
