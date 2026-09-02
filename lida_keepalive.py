# -*- coding: utf-8 -*-
"""
立达校园网保活守护 (LidaNet KeepAlive) - 优化版
原理: 借鉴 csaslu/LidaNetDaemon (Dr.COM drcom/login 接口)
优化:
  1. 双重检测: 认证页标题 + 外网连通性 (避免假在线)
  2. 详细日志: 记录每次掉线/重登时间, 用于统计掉线规律
  3. 防抖: 掉线后立即重登, 重试最多10次
  4. 开机自启: 配合 Windows 任务计划程序
用法: python lida_keepalive.py [--once]  (--once 只检测一次, 用于测试)
"""
import json
import os
import re
import sys
import time
import datetime
import urllib.request
import urllib.parse
import socket

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "keepalive.log")

# Dr.COM 登录方式后缀
SUFFIX = {"unicom": "@unicom", "cmcc": "@cmcc", "teacher": ""}
METHOD_NAME = {"unicom": "联通", "cmcc": "移动", "teacher": "教师"}

AUTH_URL = "http://192.168.16.3/"
LOGIN_URL = "http://192.168.16.3/drcom/login?"


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def log(msg):
    line = "[%s] %s" % (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), msg)
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def http_get(url, timeout=6):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Referer": "http://192.168.16.3/",
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read()
        return resp.status, body


def decode_gbk(body):
    try:
        return body.decode("gbk", errors="replace")
    except Exception:
        return body.decode("utf-8", errors="replace")


def check_auth():
    """检查认证状态: True=已登录(注销页), False=未登录(上网登录页)"""
    try:
        status, body = http_get(AUTH_URL, timeout=6)
        if status != 200:
            return False
        text = decode_gbk(body)
        m = re.search(r"<title>([^<]+)</title>", text, re.I)
        if not m:
            return False
        title = m.group(1).strip()
        return title == "注销页"
    except Exception:
        return False


def check_internet():
    """检查真实外网连通 (防止登录页可达但外网被拦的假在线)"""
    targets = ["http://www.baidu.com/", "http://www.qq.com/"]
    for t in targets:
        try:
            socket.setdefaulttimeout(6)
            status, _ = http_get(t, timeout=6)
            if status in (200, 301, 302):
                return True
        except Exception:
            continue
    return False


def try_login(cfg):
    suffix = SUFFIX.get(cfg.get("login_type", "unicom"), "@unicom")
    params = [
        ("callback", "dr1003"),
        ("DDDDD", cfg["username"] + suffix),
        ("upass", cfg["password"]),
        ("0MKKey", "123456"),
        ("R1", "0"),
        ("R2", ""),
        ("R3", "0"),
        ("R6", "0"),
        ("para", "00"),
        ("v6ip", ""),
        ("terminal_type", "1"),
        ("lang", "zh-cn"),
        ("jsVersion", "4.1.3"),
        ("v", "2509"),
    ]
    url = LOGIN_URL + urllib.parse.urlencode(params)
    try:
        status, body = http_get(url, timeout=15)
        if status == 200 and b"dr1003" in body:
            return True
        return False
    except Exception:
        return False


def ensure_login(cfg):
    for i in range(10):
        if try_login(cfg):
            return True
        time.sleep(2)
    return False


def main():
    once = "--once" in sys.argv
    cfg = load_config()
    interval = int(cfg.get("interval", 60))
    username = cfg["username"]
    method = METHOD_NAME.get(cfg.get("login_type", "unicom"), "联通")

    log("=" * 60)
    log("立达校园网保活守护启动 | 账号 %s | 通道 %s | 间隔 %ds" % (username, method, interval))

    while True:
        logged_in = check_auth()
        internet_ok = check_internet()

        if logged_in and internet_ok:
            log("在线正常 (认证页OK + 外网OK)")
        elif logged_in and not internet_ok:
            log("警告: 认证页显示在线但外网不通 (假在线/被静默冻结), 尝试重新登录...")
            if ensure_login(cfg):
                log("重新登录完成")
            else:
                log("重新登录失败!")
        elif not logged_in:
            log("检测到掉线! 尝试自动登录...")
            if ensure_login(cfg):
                log("自动登录成功")
            else:
                log("自动登录失败 (稍后重试)")
        else:
            log("异常状态, 稍后重试")

        if once:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
