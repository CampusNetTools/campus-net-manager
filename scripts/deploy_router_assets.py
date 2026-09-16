# -*- coding: utf-8 -*-
"""把 router_assets/ 里的脚本推送到小米路由器 (base64 over SSH, 无需 SFTP)。

为什么用 base64 over SSH
------------------------
小米 RD08 的 dropbear 没开 SFTP 子系统, ``paramiko`` 的 ``open_sftp()`` 会直接报
``EOF during negotiation``。所以走 exec_command + base64 分块传, 远端 decode 成文件。

为什么每个文件都要先备份
------------------------
覆盖式推送没有退路。``BACKUP_DIR`` 里按 ``<文件名>.<时间戳>`` 归档, 任何一次推送
都能回滚 —— 这条对"绝不变砖"是硬要求。

凭据
----
**不写在本文件里**。按优先级取:
  1. 命令行 ``--pwd``、``--host``
  2. 环境变量 ``ROUTER_PWD`` / ``ROUTER_HOST``
  3. 本机 ``config.json`` 的 ``router_console.token`` (即工作台令牌, 与 SSH 口令一致)

用法
----
    python scripts/deploy_router_assets.py --list            # 只看映射表, 不连设备
    python scripts/deploy_router_assets.py                   # 推送全部
    python scripts/deploy_router_assets.py console-index.html  # 只推一个
    python scripts/deploy_router_assets.py --no-backup       # 跳过备份(不建议)
"""
import argparse
import base64
import datetime
import hashlib
import json
import os
import sys

import paramiko

# 非 UTF-8 控制台(cp1252)上 print 中文会抛 UnicodeEncodeError, 推送脚本会在"全部
# 推送完成"那一行崩掉 —— 文件其实已经传上去了, 却报失败。统一改成 UTF-8。
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, ValueError):
    pass

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCAL = os.path.join(REPO_ROOT, "router_assets")
BACKUP_DIR = "/data/other_vol/proxy/backup"

# 本地文件 -> (远端路径, mode)
# mode 一律按路由器上实测的现值填写, 避免推送时把权限改成"看起来更安全"但
# 与既有行为不一致的值 (例如 guard.sh 现值是 666)。
MAP = [
    # --- 工作台页面 + CGI (web 可执行目录) ---
    ("console-index.html", "/data/other_vol/console/index.html", "644"),
    ("console-action.sh", "/data/other_vol/console/cgi-bin/action.sh", "755"),
    ("console-status.sh", "/data/other_vol/console/cgi-bin/status.sh", "755"),
    ("proxy-api.sh", "/data/other_vol/console/cgi-bin/proxy-api.sh", "755"),
    ("proxy-config.sh", "/data/other_vol/console/cgi-bin/proxy-config.sh", "755"),
    # --- 代理目录 (不经 web) ---
    ("proxy-rotate.sh", "/data/other_vol/proxy/rotate.sh", "755"),
    ("proxy-guard.sh", "/data/other_vol/proxy/guard.sh", "666"),
    ("proxy-start.sh", "/data/other_vol/proxy/start.sh", "666"),
    ("proxy-stop.sh", "/data/other_vol/proxy/stop.sh", "666"),
    ("proxy-trial.sh", "/data/other_vol/proxy/trial.sh", "700"),
    ("proxy-direct.sh", "/data/other_vol/proxy/direct.sh", "700"),
    ("proxy-watch.sh", "/data/other_vol/proxy/watch.sh", "700"),
]


def _relax_paramiko():
    """小米 dropbear 较老, 只提供 ssh-rsa 主机密钥, 新版 paramiko 默认禁用。"""
    for attr, extra in (
        ("_preferred_keys", ("ssh-rsa", "rsa-sha2-256", "rsa-sha2-512")),
        ("_preferred_ciphers", ("aes128-ctr", "aes192-ctr", "aes256-ctr")),
        ("_preferred_macs", ("hmac-sha1", "hmac-sha2-256")),
    ):
        cur = list(getattr(paramiko.Transport, attr, ()) or ())
        for name in reversed(extra):
            if name not in cur:
                cur.insert(0, name)
        setattr(paramiko.Transport, attr, tuple(cur))


def _token_from_config():
    """本机 config.json 里的工作台令牌 (与 SSH 口令同一个)。"""
    for cand in (os.path.join(REPO_ROOT, "config.json"),
                 os.path.join(REPO_ROOT, "core", "config.json")):
        if not os.path.exists(cand):
            continue
        try:
            with open(cand, encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        tok = ((data.get("router_console") or {}).get("token") or "").strip()
        if tok:
            return tok
    return ""


def run(cli, cmd, timeout=60):
    _, out, err = cli.exec_command(cmd, timeout=timeout)
    return (out.read().decode("utf-8", "replace").strip(),
            err.read().decode("utf-8", "replace").strip())


def backup(cli, remote, stamp):
    out, _ = run(cli, "if [ -f %s ]; then mkdir -p %s && cp -p %s %s/%s.%s && echo OK; "
                      "else echo ABSENT; fi"
                      % (remote, BACKUP_DIR, remote, BACKUP_DIR,
                         remote.split("/")[-1], stamp))
    return out


def main():
    ap = argparse.ArgumentParser(description="推送 router_assets 到小米路由器")
    ap.add_argument("files", nargs="*", help="只推这几个 (默认全部)")
    ap.add_argument("--host", default=os.environ.get("ROUTER_HOST", "192.168.31.1"))
    ap.add_argument("--pwd", default=os.environ.get("ROUTER_PWD") or _token_from_config())
    ap.add_argument("--list", action="store_true", help="只打印映射表")
    ap.add_argument("--no-backup", action="store_true")
    args = ap.parse_args()

    if args.list:
        for name, remote, mode in MAP:
            print("%-22s -> %-52s %s" % (name, remote, mode))
        return 0

    if not args.pwd:
        print("缺少口令: 用 --pwd / ROUTER_PWD 提供, 或确保 config.json 里已存工作台令牌")
        return 2

    _relax_paramiko()
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    cli = paramiko.SSHClient()
    cli.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    cli.connect(args.host, 22, "root", password=args.pwd, timeout=15,
                allow_agent=False, look_for_keys=False)

    failed = []
    for name, remote, mode in MAP:
        if args.files and name not in args.files:
            continue
        with open(os.path.join(LOCAL, name), "rb") as fh:
            data = fh.read()
        local_sha = hashlib.sha256(data).hexdigest()

        if not args.no_backup:
            print("%-22s 备份: %s" % (name, backup(cli, remote, stamp)))

        b64 = base64.b64encode(data).decode("ascii")
        tmp = remote + ".new"
        # 先写临时文件再原子替换, 避免推到一半断连留下半个文件
        run(cli, "rm -f %s" % tmp)
        for i in range(0, len(b64), 3000):
            run(cli, "printf '%%s' '%s' >> %s" % (b64[i:i + 3000], tmp))
        out, err = run(cli, "base64 -d %s > %s && chmod %s %s && rm -f %s && "
                            "sha256sum %s | cut -d' ' -f1"
                            % (tmp, remote, mode, remote, tmp, remote))
        remote_sha = out.strip()
        ok = remote_sha == local_sha
        if not ok:
            failed.append(name)
        print("%-22s -> %s" % (name, remote))
        print("   mode %s   sha256 %s  %s"
              % (mode, local_sha[:16], "OK" if ok else "!! 远端=%s %s" % (remote_sha[:16], err)))
    cli.close()

    if failed:
        print("\n失败: %s" % ", ".join(failed))
        return 1
    print("\n全部推送完成, 备份在 %s" % BACKUP_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
