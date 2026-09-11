# -*- coding: utf-8 -*-
"""档案与配置管理 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401

__all__ = ['default_profile', 'default_preferences', 'ensure_preferences', '_profile_secret_id', 'keychain_set', 'keychain_get', 'keychain_delete', 'dpapi_encrypt', 'dpapi_decrypt', '_secret_backend', 'lida_profile', 'ensure_lida_profile', 'load_config', 'save_config', 'config_for_export', 'notification_enabled', 'normalized_notification_settings']

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
        "history_log_path": "",  # 用户指定的网络稳定性历史保存位置; 留空用默认 ~/Library/Application Support/CampusNetManager/network_history.jsonl
        "kick_guard": True,   # 防踢: 周期性刷新登录, 让本机/路由器会话保持最新不被挤掉
        "auto_update_check": True,      # 启动时自动检查 GitHub 新版本(20小时间隔)
        "update_skip_version": "",      # 用户选择跳过的版本 tag
        "update_last_check": "",        # 上次检查时间 ISO
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
    for key in ("history_enabled", "history_log_path", "kick_guard",
                "auto_update_check", "update_skip_version", "update_last_check"):
        if key not in cfg:
            cfg[key] = defaults[key]
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


def _secret_backend():
    """当前平台的"系统级密钥库"标识。

    macOS 用钥匙串(密码存系统库, 配置文件只留引用); Windows 用 DPAPI
    (密码用当前用户凭据加密后仍存配置文件, 但落地即密文)。
    Windows 上没有等价于钥匙串的进程外凭据库, DPAPI 是官方推荐的用户态方案。
    注意判断顺序: macOS 优先, 否则测试里同时 patch IS_MACOS=True 时会走错分支。
    """
    if common.IS_MACOS:
        return "keychain"
    if common.IS_WINDOWS:
        return "dpapi"
    return ""


# ---------- Windows DPAPI (消灭 Windows 下明文密码落盘) ----------
def _dpapi_crypt(data, protect):
    """调用 Win32 CryptProtectData / CryptUnprotectData, 失败返回 None。

    CryptProtectData 与 CryptUnprotectData 的参数个数相同(7 个), 可共用一套
    argtypes; 不显式声明 argtypes 时 ctypes 会把指针当 int 传, 64 位下会崩。
    """
    import ctypes
    from ctypes import wintypes

    class DATA_BLOB(ctypes.Structure):
        _fields_ = [("cbData", wintypes.DWORD),
                    ("pbData", ctypes.POINTER(ctypes.c_byte))]

    crypto = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    proto = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
             ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
             ctypes.POINTER(DATA_BLOB)]
    fn = crypto.CryptProtectData if protect else crypto.CryptUnprotectData
    fn.argtypes = proto
    fn.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]

    src_buf = ctypes.create_string_buffer(bytes(data), len(data))
    blob_in = DATA_BLOB(len(data), ctypes.cast(src_buf, ctypes.POINTER(ctypes.c_byte)))
    blob_out = DATA_BLOB()
    if not fn(ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        return None
    try:
        return ctypes.string_at(blob_out.pbData, blob_out.cbData)
    finally:
        kernel.LocalFree(blob_out.pbData)


def dpapi_encrypt(text):
    """用当前 Windows 用户凭据加密, 返回可落盘的 base64 字符串; 失败返回 ""。

    密文与「用户 + 机器」绑定: 把 config.json 拷到别的机器/别的用户账号下
    无法解密(密码会退化为空, 需重填), 这正是我们想要的隔离。
    """
    if not text or not common.IS_WINDOWS:
        return ""
    try:
        import base64
        blob = _dpapi_crypt(text.encode("utf-8"), protect=True)
        return base64.b64encode(blob).decode("ascii") if blob else ""
    except Exception:
        return ""


def dpapi_decrypt(token):
    """解密 dpapi_encrypt 的产物; 失败(换机器/换用户/密文损坏)返回 ""。"""
    if not token or not common.IS_WINDOWS:
        return ""
    try:
        import base64
        blob = _dpapi_crypt(base64.b64decode(token), protect=False)
        return blob.decode("utf-8", errors="replace") if blob else ""
    except Exception:
        return ""


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


def _is_legacy_seed_profile(profile):
    """识别 v5 之前的遗留种子档案。

    v5 起新建档案必带 profile_type 字段, 且保存时会带 preset 标记 ——
    因此"既无 profile_type 又无 preset 且未绑定 SSID"的档案只可能来自旧版本。
    用它区分"需要原位升级的遗留默认档案"和"用户自建的同名档案"。
    """
    return ("profile_type" not in profile and "preset" not in profile
            and not (profile.get("ssid") or "").strip())


def ensure_lida_profile(cfg):
    """无损补齐立达专属档案，保留已有账号、密码和用户自定义档案。

    历史教训: 旧实现会把任何名为「校园网」的空 SSID 档案无条件改名并绑定
    LIDA SSID —— 用户在 v5 里自建的同名"任意网络"档案会被静默改写语义
    (绑定 SSID 后不再匹配其他网络, 界面会变成"无匹配档案")。
    现在只迁移真正的旧版遗留种子档案, 且 lida_migrated 标记保证整个迁移
    只做一次, 之后即使用户再建同名档案也不会被动过。
    """
    profiles = cfg.setdefault("profiles", [])
    for profile in profiles:
        if (profile.get("preset") == common.LIDA_PROFILE_ID
                or (profile.get("ssid") or "").strip().upper() == common.LIDA_SSID):
            if profile.get("preset") != common.LIDA_PROFILE_ID:
                profile["preset"] = common.LIDA_PROFILE_ID
                return True
            return False

    # 将早期默认“校园网”档案原位升级，避免复制账号密码或制造重复档案。
    if not cfg.get("lida_migrated"):
        for profile in profiles:
            if (_is_legacy_seed_profile(profile)
                    and profile.get("name") in ("校园网", "立达校园网WiFi")
                    and profile.get("auth_url", common.DEFAULT_AUTH_URL) == common.DEFAULT_AUTH_URL):
                old_name = profile.get("name")
                profile.update({"name": common.LIDA_PROFILE_NAME, "ssid": common.LIDA_SSID,
                                "gateway": profile.get("gateway", ""), "preset": common.LIDA_PROFILE_ID})
                if cfg.get("active_profile") == old_name:
                    cfg["active_profile"] = common.LIDA_PROFILE_NAME
                # 迁移是一次性动作: 打上标记, 下次不再扫描(用户后续自建的同名档案安全)
                cfg["lida_migrated"] = True
                return True

    profiles.insert(0, lida_profile())
    if not cfg.get("active_profile"):
        cfg["active_profile"] = common.LIDA_PROFILE_NAME
    cfg["lida_migrated"] = True
    return True


# 配置读写锁: 守护线程(自动切档案)与 GUI(保存档案)并发读写同一文件,
# 无锁时 deepcopy/写文件交错可能丢失更新或写出半截文件。
# 用可重入锁: load_config 持锁期间会调用 save_config(内部再取锁), 普通锁会死锁。
_CONFIG_LOCK = threading.RLock()


def load_config():
    """加载配置。文件损坏(半写/手改出错)时不再抛异常炸掉整个 App:
    备份损坏文件为 config.json.corrupt-<时间戳>, 重建默认配置 ——
    历史教训: save_config 非原子写 + 强杀进程会产生半截 JSON, 导致启动即崩。"""
    with _CONFIG_LOCK:
        if not os.path.exists(common.CONFIG_PATH):
            cfg = {"profiles": [lida_profile()], "active_profile": common.LIDA_PROFILE_NAME,
                   "auth_history": [common.DEFAULT_AUTH_URL]}
            ensure_preferences(cfg)
            return cfg
        try:
            with open(common.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if not isinstance(cfg, dict):
                raise ValueError("config.json 顶层不是对象")
        except Exception:
            try:
                stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                os.replace(common.CONFIG_PATH,
                           common.CONFIG_PATH + ".corrupt-" + stamp)
                try:
                    from core import sysutils as _sysutils
                    _sysutils.log("配置文件损坏已备份为 config.json.corrupt-%s, 已重建默认配置" % stamp)
                except Exception:
                    pass
            except Exception:
                pass
            cfg = {"profiles": [lida_profile()], "active_profile": common.LIDA_PROFILE_NAME,
                   "auth_history": [common.DEFAULT_AUTH_URL]}
            ensure_preferences(cfg)
            return cfg
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
        # 首次升级时把旧版明文密码迁移进系统密钥库(macOS 钥匙串 / Windows DPAPI)；
        # 配置文件只保留引用(macOS)或密文(Windows), 不再落明文。
        if _secret_backend() == "keychain":
            for profile in cfg.get("profiles", []):
                password = profile.get("password", "")
                secret_id = _profile_secret_id(profile)
                if password and keychain_set(secret_id, password):
                    profile["password_store"] = "keychain"
                    changed = True
                elif profile.get("password_store") == "keychain":
                    profile["password"] = keychain_get(secret_id)
        elif _secret_backend() == "dpapi":
            for profile in cfg.get("profiles", []):
                if profile.get("password_store") == "dpapi":
                    if not profile.get("password"):
                        profile["password"] = dpapi_decrypt(profile.get("password_enc", ""))
                    if not profile.get("password"):
                        # 密文解不开(换个用户/换台电脑/文件损坏): 清掉残骸并明确提示,
                        # 不要让用户面对"密码框空的但登录一直失败"的哑谜。
                        profile["password_store"] = ""
                        profile.pop("password_enc", None)
                        changed = True
                        try:
                            from core import sysutils as _sysutils
                            _sysutils.log("档案「%s」的密码无法用当前 Windows 用户解密"
                                          "(配置可能来自其他电脑), 已清空, 请重新填写"
                                          % profile.get("name", "?"))
                        except Exception:
                            pass
                elif profile.get("password"):
                    # 旧版明文密码: 标记迁移, 由随后的 save 加密落盘
                    profile["password_store"] = "dpapi"
                    changed = True
        if changed:
            _save_config_locked(cfg)   # 已持锁, 走内部实现避免重入开销
        return cfg


def save_config(cfg, sync_secrets=False):
    with _CONFIG_LOCK:
        _save_config_locked(cfg, sync_secrets)


def _save_config_locked(cfg, sync_secrets=False):
    ensure_preferences(cfg)
    disk_cfg = copy.deepcopy(cfg)
    backend = _secret_backend()
    for profile, disk_profile in zip(cfg.get("profiles", []), disk_cfg.get("profiles", [])):
        password = profile.get("password", "")
        if backend == "keychain":
            secret_id = _profile_secret_id(profile)
            disk_profile["secret_id"] = secret_id
            if password and (sync_secrets or profile.get("password_store") != "keychain"):
                if not keychain_set(secret_id, password):
                    raise RuntimeError("无法把密码保存到 macOS 钥匙串")
                profile["password_store"] = "keychain"
            if profile.get("password_store") == "keychain":
                disk_profile["password"] = ""
                disk_profile["password_store"] = "keychain"
        elif backend == "dpapi":
            if password:
                # DPAPI 是进程内加密(无子进程开销), 每次保存都重新加密 ——
                # 顺带修掉"password_store 已是 dpapi 就跳过写盘"导致改了密码
                # 但密文还是旧值的隐患。
                token = dpapi_encrypt(password)
                if not token:
                    raise RuntimeError("无法用 Windows DPAPI 加密密码, 已中止保存以保护明文")
                disk_profile["password"] = ""
                disk_profile["password_store"] = "dpapi"
                disk_profile["password_enc"] = token
            else:
                # 密码被清空: 一并清掉密文, 不留旧密码残骸
                disk_profile.pop("password_enc", None)
                disk_profile["password_store"] = ""
    # 原子写: 先写临时文件再 os.replace, 避免写一半崩溃/断电损坏配置
    tmp_path = common.CONFIG_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(disk_cfg, f, ensure_ascii=False, indent=2)
    os.replace(tmp_path, common.CONFIG_PATH)


def config_for_export(cfg):
    """导出可迁移但不含密码的安全配置。"""
    exported = copy.deepcopy(cfg)
    for profile in exported.get("profiles", []):
        profile["password"] = ""
        for key in ("secret_id", "password_store", "password_enc"):
            profile.pop(key, None)
    return exported


def notification_enabled(cfg, category):
    settings = cfg.get("notifications", {})
    return settings.get("enabled", True) and settings.get(category, True)


def normalized_notification_settings(enabled, categories):
    """总开关关闭时，所有子通知同步关闭。"""
    result = {"enabled": bool(enabled)}
    result.update({key: bool(value) if enabled else False for key, value in categories.items()})
    return result
