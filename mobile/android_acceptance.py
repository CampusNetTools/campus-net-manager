"""Test-only Android emulator probes, included only in acceptance builds."""
import json
import os

try:
    from guard_service import load_profile_data, write_profile
except ImportError:  # Allow source-level contract tests outside python-for-android.
    from .guard_service import load_profile_data, write_profile


PROFILE_FIXTURE_NAME = "acceptance-profile.json"
PROFILE_STORE_FILE = "profile.enc"
PROFILE_STORE_PREFIX = "CNM_ANDROID_PROFILE_STORE_"


def run_profile_store_probe(user_data_dir):
    """Encrypt/decrypt a synthetic profile in the app's Android Keystore UID.

    The fixture has empty username/password and a loopback-only auth URL. It is
    supplied to a debuggable emulator install through ``run-as`` and is never
    included in the APK or used for a network login.
    """
    user_data_dir = os.path.abspath(user_data_dir)
    candidates = (
        os.path.join(user_data_dir, PROFILE_FIXTURE_NAME),
        os.path.join(os.path.dirname(user_data_dir), PROFILE_FIXTURE_NAME),
    )
    fixture_path = next((path for path in candidates if os.path.isfile(path)), None)
    if fixture_path is None:
        return None

    with open(fixture_path, encoding="utf-8") as stream:
        expected = json.load(stream)
    if not isinstance(expected, dict) or expected.get("username") or expected.get("password"):
        raise ValueError("acceptance fixture must not contain account credentials")
    if expected.get("auth_url") != "http://127.0.0.1:9/":
        raise ValueError("acceptance fixture must use its loopback-only endpoint")

    encrypted_path = os.path.join(user_data_dir, PROFILE_STORE_FILE)
    if os.path.exists(encrypted_path):
        actual = load_profile_data(encrypted_path)
        action = "RESTART"
    else:
        write_profile(encrypted_path, expected)
        actual = load_profile_data(encrypted_path)
        action = "WRITE"
    if actual != expected:
        raise ValueError("encrypted profile round-trip did not preserve the synthetic fixture")
    return PROFILE_STORE_PREFIX + action + "_PASS"
