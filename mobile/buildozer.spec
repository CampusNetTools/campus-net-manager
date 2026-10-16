[app]

# (str) Title of your application
title = 校园网连接管家

# (str) Package name
package.name = campusnetmanager

# (str) Package domain (needed for android/ios packaging)
package.domain = org.campusnettools

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas,json

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# 纯 python 依赖; 显式 pin Python/Kivy 以固定 Android 可复现构建输入
requirements = python3==3.11.8,hostpython3==3.11.8,kivy==2.3.1
# API 36 与 Android 14+ 前台服务类型支持
p4a.branch = v2026.05.09

# (str) Supported orientation (one of landscape, sensorLandscape, portrait or all)
orientation = portrait

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 0

# (int) Target Android API, should be as high as possible.
android.api = 36

# (int) Minimum API your APK / AAB will support.
android.minapi = 24

# (str) Android NDK version to use
#android.ndk = 25b

# (bool) Use --private data storage (default) or --dir public storage
#private_storage = True
android.allow_backup = False

# Include x86_64 so CI can install and launch the same APK in an API 36 emulator.
# Keep both ARM ABIs for physical Android devices.
android.archs = arm64-v8a, armeabi-v7a, x86_64

# (list) Permissions
android.permissions = INTERNET, ACCESS_NETWORK_STATE, ACCESS_WIFI_STATE, FOREGROUND_SERVICE, FOREGROUND_SERVICE_SPECIAL_USE, POST_NOTIFICATIONS

# User-started, persistent campus authentication keepalive. Android 14+ requires
# a declared service type and Play Console special-use justification.
services = campusguard:services/campusguard.py:foreground:sticky:foregroundServiceType=specialUse
android.add_src = java

# (int) Android logcat filters to use
#android.logcat_filters = *:S python:D

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
