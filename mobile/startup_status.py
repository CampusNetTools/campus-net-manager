"""Pure initial network-status decision for the Android UI and its tests."""


def initial_network_status(auth, auth_url):
    """Return (message, healthy, error_type) without touching UI state."""
    try:
        if not auth.auth_reachable(auth_url):
            return "非校园网环境（认证服务器不可达）", None, None

        authenticated = auth.check_auth(auth_url)
        internet = auth.check_internet()
        if authenticated and internet:
            return "校园网在线（已认证 · 可上网）", True, None
        if authenticated:
            return "已认证但外网不通", False, None
        return "校园网未认证（需要登录）", False, None
    except Exception as exc:
        return "网络状态检测失败，请稍后重试", False, type(exc).__name__
