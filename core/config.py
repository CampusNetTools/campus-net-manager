# -*- coding: utf-8 -*-
"""档案与配置管理 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401

__all__ = ['default_profile', 'default_preferences', 'ensure_preferences', '_profile_secret_id', 'keychain_set', 'keychain_get', 'keychain_delete', 'lida_profile', 'ensure_lida_profile', 'load_config', 'save_config', 'config_for_export', 'notification_enabled', 'normalized_notification_settings']

def default_profile(name="校园网", profile_type="campus"):
    return {
        "name": name,
        "profile_type": profile_type,  # "campus"=校园网认证(登录保活) / "wifi"=普通WiFi/热点(只检测断网,不登录)
        "ssid": "",            # 绑定的 WiFi 名, 留空=默认档案(任意网络)
        "username": "",
        "password": "",
        "login_type": "cmcc",  # cmcc / unicom / teacher
        "auth_url": common.DEFAULT_AUTH_URL if profile_type == "campus" else "",
        "interval": 60,
    }


def default_preferences():
    return {
        "history_enabled": False,
        "kick_guard": True,   # 防踢: 周期性刷新登录, 让本机/路由器会话保持最新不被挤掉
        "notifications": {
            "enabled": True,
            "disconnect": True,
            "recovery": True,
            "failure": True,
            "device": True,
        },
    }


def ensure_preferences(cfg):
    changed = False
    defaults = default_preferences()
    if "history_enabled" not in cfg:
        cfg["history_enabled"] = defaults["history_enabled"]
        changed = True
    notifications = cfg.setdefault("notifications", {})
    for key, value in defaults["notifications"].items():
        if key not in notifications:
            notifications[key] = value
            changed = True
    return changed


def _profile_secret_id(profile):
    secret_id = profile.get("secret_id")
    if not secret_id:
        secret_id = "profile-" + uuid.uuid4().hex
        profile["secret_id"] = secret_id
    return secret_id


def keychain_set(secret_id, password):
    """把密码写入当前用户的 macOS 钥匙串。"""
    if not common.IS_MACOS or not secret_id:
        return False
    result = subprocess.run(
        ["/usr/bin/security", "add-generic-password", "-U", "-s", common.KEYCHAIN_SERVICE,
         "-a", secret_id, "-w", password], capture_output=True, timeout=10)
    return result.returncode == 0


def keychain_get(secret_id):
    if not common.IS_MACOS or not secret_id:
        return ""
    result = subprocess.run(
        ["/usr/bin/security", "find-generic-password", "-w", "-s", common.KEYCHAIN_SERVICE,
         "-a", secret_id], capture_output=True, timeout=10)
    return result.stdout.decode("utf-8", errors="replace").rstrip("\r\n") if result.returncode == 0 else ""


def keychain_delete(secret_id):
    if not common.IS_MACOS or not secret_id:
        return False
    result = subprocess.run(
        ["/usr/bin/security", "delete-generic-password", "-s", common.KEYCHAIN_SERVICE,
         "-a", secret_id], capture_output=True, timeout=10)
    return result.returncode == 0


def lida_profile():
    """立达学校内置档案；账号密码保持空白，由用户本人填写。"""
    profile = default_profile(common.LIDA_PROFILE_NAME)
    profile.update({
        "preset": common.LIDA_PROFILE_ID,
        "ssid": common.LIDA_SSID,
        "gateway": "",
        "auth_url": common.DEFAULT_AUTH_URL,
        "login_type": "cmcc",
        "interval": 60,
    })
    return profile


def ensure_lida_profile(cfg):
    """无损补齐立达专属档案，保留已有账号、密码和用户自定义档案。"""
    profiles = cfg.setdefault("profiles", [])
    for profile in profiles:
        if (profile.get("preset") == common.LIDA_PROFILE_ID
                or (profile.get("ssid") or "").strip().upper() == common.LIDA_SSID):
            if profile.get("preset") != common.LIDA_PROFILE_ID:
                profile["preset"] = common.LIDA_PROFILE_ID
                return True
            return False

    # 将早期默认“校园网”档案原位升级，避免复制账号密码或制造重复档案。
    for profile in profiles:
        if (profile.get("name") in ("校园网", "立达校园网WiFi")
                and profile.get("auth_url", common.DEFAULT_AUTH_URL) == common.DEFAULT_AUTH_URL
                and not profile.get("ssid")):
            old_name = profile.get("name")
            profile.update({"name": common.LIDA_PROFILE_NAME, "ssid": common.LIDA_SSID,
                            "gateway": profile.get("gateway", ""), "preset": common.LIDA_PROFILE_ID})
            if cfg.get("active_profile") == old_name:
                cfg["active_profile"] = common.LIDA_PROFILE_NAME
            return True

    profiles.insert(0, lida_profile())
    if not cfg.get("active_profile"):
        cfg["active_profile"] = common.LIDA_PROFILE_NAME
    return True


def load_config():
    if not os.path.exists(common.CONFIG_PATH):
        cfg = {"profiles": [lida_profile()], "active_profile": common.LIDA_PROFILE_NAME,
               "auth_history": [common.DEFAULT_AUTH_URL]}
        ensure_preferences(cfg)
        return cfg
    with open(common.CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    changed = False
    # 兼容旧版单档案结构
    if "profiles" not in cfg:
        p = default_profile("校园网")
        p.update({k: cfg.get(k) for k in ("username", "password", "login_type", "interval") if cfg.get(k) is not None})
        cfg = {"profiles": [p], "active_profile": p["name"]}
        changed = True
    if ensure_lida_profile(cfg):
        changed = True
    if ensure_preferences(cfg):
        changed = True
    # 首次升级时把旧版明文密码迁移进钥匙串；配置文件只保留引用。
    if common.IS_MACOS:
        for profile in cfg.get("profiles", []):
            password = profile.get("password", "")
            secret_id = _profile_secret_id(profile)
            if password and keychain_set(secret_id, password):
                profile["password_store"] = "keychain"
                changed = True
            elif profile.get("password_store") == "keychain":
                profile["password"] = keychain_get(secret_id)
    if changed:
        save_config(cfg)
    return cfg


def save_config(cfg, sync_secrets=False):
    ensure_preferences(cfg)
    disk_cfg = copy.deepcopy(cfg)
    if common.IS_MACOS:
        for profile, disk_profile in zip(cfg.get("profiles", []), disk_cfg.get("profiles", [])):
            secret_id = _profile_secret_id(profile)
            disk_profile["secret_id"] = secret_id
            password = profile.get("password", "")
            if password and (sync_secrets or profile.get("password_store") != "keychain"):
                if not keychain_set(secret_id, password):
                    raise RuntimeError("无法把密码保存到 macOS 钥匙串")
                profile["password_store"] = "keychain"
            if profile.get("password_store") == "keychain":
                disk_profile["password"] = ""
                disk_profile["password_store"] = "keychain"
    with open(common.CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(disk_cfg, f, ensure_ascii=False, indent=2)


def config_for_export(cfg):
    """导出可迁移但不含密码的安全配置。"""
    exported = copy.deepcopy(cfg)
    for profile in exported.get("profiles", []):
        profile["password"] = ""
        profile.pop("secret_id", None)
        profile.pop("password_store", None)
    return exported


def notification_enabled(cfg, category):
    settings = cfg.get("notifications", {})
    return settings.get("enabled", True) and settings.get(category, True)


def normalized_notification_settings(enabled, categories):
    """总开关关闭时，所有子通知同步关闭。"""
    result = {"enabled": bool(enabled)}
    result.update({key: bool(value) if enabled else False for key, value in categories.items()})
    return result
