# -*- coding: utf-8 -*-
"""Android foreground keepalive worker shared by the APK service and tests."""
import datetime as dt
import json
import os
import threading
import time

from core import auth, config


KEEPALIVE_INTERVAL = 60
STATE_STALE_AFTER = 150
ANDROID_CREDENTIAL_STORE = "org.campusnettools.campusnetmanager.CampusCredentialStore"


def _timestamp(now=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt.timezone.utc)
    return now.astimezone(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def state_path_for(profile_path):
    return os.path.join(os.path.dirname(os.path.abspath(profile_path)), "guard-state.json")


def _android_encrypt(plaintext):
    from jnius import autoclass
    return str(autoclass(ANDROID_CREDENTIAL_STORE).encrypt(plaintext))


def _android_decrypt(ciphertext):
    from jnius import autoclass
    return str(autoclass(ANDROID_CREDENTIAL_STORE).decrypt(ciphertext))


def load_profile_data(path):
    with open(path, encoding="utf-8") as stream:
        stored = stream.read()
    if path.endswith(".enc"):
        stored = _android_decrypt(stored)
    data = json.loads(stored)
    if not isinstance(data, dict):
        raise ValueError("profile must be an object")
    return data


def load_profile_data_if_present(path):
    """Return an empty profile on first launch; preserve errors for corrupt files."""
    try:
        return load_profile_data(path)
    except FileNotFoundError:
        return {}


def write_profile(path, profile):
    """Atomically update the private profile so the service never reads half a file."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    stored = json.dumps(profile, ensure_ascii=False)
    if path.endswith(".enc"):
        stored = _android_encrypt(stored)
    with open(temp_path, "w", encoding="utf-8") as stream:
        stream.write(stored)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass
    os.replace(temp_path, path)


def write_state(path, state):
    """Atomically write status without ever persisting account credentials."""
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temp_path = path + ".tmp"
    payload = dict(state)
    payload["updated_at"] = _timestamp()
    with open(temp_path, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False)
        stream.flush()
        os.fsync(stream.fileno())
    try:
        os.chmod(temp_path, 0o600)
    except OSError:
        pass
    os.replace(temp_path, path)
    return payload


def read_profile(path):
    data = load_profile_data(path)
    profile = config.default_profile("手机档案")
    profile.update({
        "username": str(data.get("username", "")).strip(),
        "password": str(data.get("password", "")),
        "login_type": str(data.get("method", data.get("login_type", "cmcc"))),
        "auth_url": str(data.get("auth_url", auth.DEFAULT_AUTH_URL)).strip()
                   or auth.DEFAULT_AUTH_URL,
    })
    return profile


def check_once(profile_path, state_path=None, auth_client=None, now=None):
    """Run one serialized auth/internet check and return a credential-free status."""
    client = auth_client or auth
    checked_at = _timestamp(now)
    state_file = state_path or state_path_for(profile_path)
    try:
        profile = read_profile(profile_path)
        auth_url = profile["auth_url"]
        if not client.auth_reachable(auth_url):
            state = {"enabled": True, "status": "outside-campus",
                     "message": "认证服务器不可达，保活暂时休眠。",
                     "checked_at": checked_at}
        else:
            authenticated = bool(client.check_auth(auth_url))
            internet = bool(client.check_internet())
            if authenticated and internet:
                state = {"enabled": True, "status": "online",
                         "message": "校园网在线，保活运行中。",
                         "checked_at": checked_at, "last_success_at": checked_at}
            else:
                recovered = bool(client.ensure_login(profile))
                verified = (recovered and bool(client.check_auth(auth_url))
                            and bool(client.check_internet()))
                state = {"enabled": True,
                         "status": "online" if verified else "reconnecting",
                         "message": ("掉线已恢复并复检通过。" if verified
                                     else "检测到掉线，正在尝试恢复。"),
                         "checked_at": checked_at}
                if verified:
                    state["last_success_at"] = checked_at
        return write_state(state_file, state)
    except Exception as exc:
        # Keep logs/status free of server response bodies and account data.
        return write_state(state_file, {
            "enabled": True, "status": "error",
            "message": "保活检查失败（%s）。" % type(exc).__name__,
            "checked_at": checked_at,
        })


def run_guard_service(profile_path, state_path=None, interval=KEEPALIVE_INTERVAL,
                      stop_event=None, auth_client=None):
    """Run one check immediately, then wait between non-overlapping checks."""
    stop_event = stop_event or threading.Event()
    state_file = state_path or state_path_for(profile_path)
    write_state(state_file, {"enabled": True, "status": "starting",
                             "message": "校园网保活服务正在启动。"})
    try:
        while not stop_event.is_set():
            check_once(profile_path, state_file, auth_client=auth_client)
            if stop_event.wait(max(1, int(interval))):
                break
    finally:
        write_state(state_file, {"enabled": False, "status": "stopped",
                                 "message": "校园网保活已停止。"})


def state_is_fresh(state, now=None, max_age=STATE_STALE_AFTER):
    """Whether the foreground worker has written a recent check timestamp."""
    if not isinstance(state, dict) or not state.get("enabled"):
        return False
    raw = state.get("checked_at") or state.get("updated_at")
    if not raw:
        return False
    try:
        stamp = dt.datetime.fromisoformat(raw.replace("Z", "+00:00"))
        now = now or dt.datetime.now(dt.timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=dt.timezone.utc)
        return 0 <= (now - stamp).total_seconds() <= max_age
    except (TypeError, ValueError):
        return False
