# -*- coding: utf-8 -*-
"""Dr.COM 认证与联网检测 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import netinfo, portal  # noqa: F401

__all__ = ['auth_reachable', 'http_get', 'decode_gbk', 'check_auth', '_probe_matches_expected', 'check_internet', 'check_network_paths', 'try_login', 'ensure_login']

def auth_reachable(auth_url):
    """认证服务器是否可达 (判定是否校园网环境)"""
    try:
        status, _ = http_get(auth_url, timeout=5, physical=True)
        return status == 200
    except Exception:
        return False


# ---------- 网络检测 ----------
def http_get(url, timeout=6, physical=False):
    """获取 URL；macOS 的校园认证请求可强制走物理网卡，避免被 VPN 路由接管。"""
    if common.IS_MACOS and physical:
        interface = netinfo.get_physical_interface()
        if interface:
            try:
                result = subprocess.run(
                    ["/usr/bin/curl", "--silent", "--show-error", "--max-time", str(timeout),
                     "--noproxy", "*",
                     "--interface", interface, "--output", "-", "--write-out", "\n%{http_code}",
                     "--user-agent", "Mozilla/5.0 AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
                     url],
                    capture_output=True, timeout=timeout + 2)
                if result.returncode == 0 and b"\n" in result.stdout:
                    body, raw_status = result.stdout.rsplit(b"\n", 1)
                    return int(raw_status), body
                raise OSError(result.stderr.decode("utf-8", errors="replace") or "物理网卡请求失败")
            except Exception as exc:
                raise urllib.error.URLError(exc)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        "Referer": url,
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def decode_gbk(body):
    try:
        return body.decode("gbk", errors="replace")
    except Exception:
        return body.decode("utf-8", errors="replace")


def check_auth(auth_url=common.DEFAULT_AUTH_URL):
    """True=已登录(注销页), False=未登录/不可达"""
    try:
        status, body = http_get(auth_url, timeout=6, physical=True)
        if status != 200:
            return False
        text = decode_gbk(body)
        m = re.search(r"<title>([^<]+)</title>", text, re.I)
        return bool(m and m.group(1).strip() == "注销页")
    except Exception:
        return False


def _probe_matches_expected(result):
    probe = result["probe"]
    expected_body = probe.get("body", "")
    return (result.get("status") == probe["status"]
            and (not expected_body or expected_body in result.get("body", "")))


def check_internet(physical=False):
    """严格联网检测：只有 204 或预期正文才算在线，认证页 200/302 不算外网。"""
    probes = portal.CAPTIVE_PROBES[:4]
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(probes)) as pool:
        results = list(pool.map(lambda probe: portal._run_captive_probe(probe, physical=physical), probes))
    return any(_probe_matches_expected(result) for result in results)


def check_network_paths():
    """分别检查当前系统/VPN路径和校园网物理路径，避免把 VPN 异常误报为校园网假在线。"""
    vpn = netinfo.vpn_active()
    if vpn and common.IS_MACOS:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            current_future = pool.submit(check_internet, False)
            physical_future = pool.submit(check_internet, True)
            current = current_future.result()
            physical = physical_future.result()
    else:
        current = check_internet(False)
        physical = current
    return {"vpn": vpn, "current": current, "physical": physical}


# ---------- 登录 ----------
def try_login(profile):
    suffix = common.SUFFIX.get(profile.get("login_type", "cmcc"), "@cmcc")
    auth_url = profile.get("auth_url", common.DEFAULT_AUTH_URL)
    host = auth_url.split("/")[2] if "//" in auth_url else auth_url
    params = [
        ("callback", "dr1003"),
        ("DDDDD", profile["username"] + suffix),
        ("upass", profile["password"]),
        ("0MKKey", "123456"),
        ("R1", "0"), ("R2", ""), ("R3", "0"), ("R6", "0"),
        ("para", "00"), ("v6ip", ""),
        ("terminal_type", "1"), ("lang", "zh-cn"),
        ("jsVersion", "4.1.3"), ("v", "2509"),
    ]
    url = "http://%s/drcom/login?%s" % (host, urllib.parse.urlencode(params))
    try:
        status, body = http_get(url, timeout=15, physical=True)
        return status == 200 and b"dr1003" in body
    except Exception:
        return False


def ensure_login(profile, on_log=None):
    for i in range(10):
        if try_login(profile):
            return True
        if on_log:
            on_log("登录重试 %d/10 失败" % (i + 1))
        time.sleep(2)
    return False


# ---------- 守护线程 ----------
