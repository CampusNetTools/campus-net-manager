# -*- coding: utf-8 -*-
"""公共导入与常量 (自 keepalive_core.py 拆分)"""

__all__ = ['BASE_DIR', '_NO_WINDOW', 'json', 'os', 're', 'copy', 'socket', 'subprocess', 'sys', 'threading', 'time', 'datetime', 'concurrent', 'ipaddress', 'plistlib', 'traceback', 'urllib', 'ET', 'uuid', 'IS_WINDOWS', 'IS_MACOS', 'CONFIG_PATH', 'LOG_PATH', 'LOCK_PATH', 'HISTORY_PATH', 'KEYCHAIN_SERVICE', 'DEFAULT_AUTH_URL', 'LIDA_PROFILE_ID', 'LIDA_PROFILE_NAME', 'LIDA_SSID', 'SUFFIX', 'METHOD_NAME']

# -*- coding: utf-8 -*-
"""
校园网连接管家 - 核心模块 (KeepAlive Core)
- 多档案: 每个 WiFi/接入环境一套配置, 按 SSID 自动匹配
- 环境识别: 认证服务器可达 = 校园网环境; 不可达 = 非校园网, 自动休眠不误登
- 接入方式无关: 有线直连 / WiFi 直连 / 经路由器中继 均可工作
- 检测: 认证页标题 + 外网连通 双重检测; 掉线自动重登 (Dr.COM drcom/login)
CLI 和桌面 App 共用本模块
"""
import json
import os
import re
import copy
import socket
import subprocess
import sys
import threading
import time
import datetime
import concurrent.futures
import ipaddress
import plistlib
import traceback
import urllib.request
import urllib.parse
import urllib.error
import xml.etree.ElementTree as ET
import uuid

IS_WINDOWS = os.name == "nt"
IS_MACOS = sys.platform == "darwin"
_MAC_APP_SUPPORT = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "CampusNetManager")

# 打包成 exe 后, 配置/日志跟随 exe 所在目录 (否则会写到临时解压目录导致丢失)
if getattr(sys, "frozen", False) and IS_MACOS:
    # .app 的 Contents/MacOS 目录不是用户数据目录，不能把配置写进应用包。
    BASE_DIR = _MAC_APP_SUPPORT
elif getattr(sys, "frozen", False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.makedirs(BASE_DIR, exist_ok=True)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")
LOG_PATH = os.path.join(BASE_DIR, "keepalive.log")
LOCK_PATH = os.path.join(BASE_DIR, "keepalive.lock")
HISTORY_PATH = os.path.join(BASE_DIR, "network_history.jsonl")
KEYCHAIN_SERVICE = "com.campusnettools.campusnetmanager"

DEFAULT_AUTH_URL = "http://192.168.16.3/"
LIDA_PROFILE_ID = "lida-campus"
LIDA_PROFILE_NAME = "立达校园网"
LIDA_SSID = "LIDA-UNIVERSITY"

SUFFIX = {"unicom": "@unicom", "cmcc": "@cmcc", "teacher": ""}
METHOD_NAME = {"unicom": "联通", "cmcc": "移动", "teacher": "教师"}


# ---------- 配置 ----------

# Windows 隐藏子进程控制台窗口标志 (v2.x 遗留, 供 netinfo/speed/sysutils 使用)
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0
