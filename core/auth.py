# -*- coding: utf-8 -*-
"""Dr.COM 认证与联网检测 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import netinfo, portal  # noqa: F401

__all__ = ['auth_reachable', 'http_get', 'decode_gbk', 'check_auth', '_probe_matches_expected', 'check_internet', 'check_network_paths', 'try_login', 'ensure_login']

# 禁用系统/环境变量代理的 opener: 认证探测、登录请求必须走本机真实网络路径。
# 走系统代理(Clash/v2rayN 等)时, 探测结果反映的是代理出口, 会误判认证状态,
# 登录请求甚至可能因代理无法访问校园网内网认证服务器而失败。
_DIRECT_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))

# 认证服务器可达性防抖: 单次探测失败(链路抖动 / 认证服务器瞬时繁忙 / DNS 抖动)
# 不代表已经离开校园网。连续 _UNREACHABLE_STRIKES 次不可达才翻转为"不在校园网",
# 中间沿用上一次的判定 —— 否则守护会在"校园网/非校园网"之间来回横跳: 每跳一次
# 就多一轮 subprocess 探测 + 一次 30s 休眠 + 一次误判策略变更。
_UNREACHABLE_STRIKES = 3
_reach_state = {}          # auth_url -> (连续失败次数, 上次判定)
_reach_lock = threading.Lock()


def _probe_auth_url(auth_url):
    """单次探测认证服务器是否可达(不带防抖)。"""
    try:
        status, _ = http_get(auth_url, timeout=5, physical=True)
        return status == 200
    except Exception:
        return False


def auth_reachable(auth_url, debounce=True):
    """认证服务器是否可达 (判定是否校园网环境)。

    debounce=True(默认) 给守护循环的"环境判定"用: 抗抖动, 连续 3 次失败才翻转。
    debounce=False 用于"此刻就要真相"的场景(重登失败后判断链路是否真断、界面展示、
    自动切档案的依据) —— 这些地方用滞后值会造成误导或误切档案。
    """
    ok = _probe_auth_url(auth_url)
    if not debounce:
        with _reach_lock:
            _reach_state[auth_url] = (0 if ok else _UNREACHABLE_STRIKES, ok)
        return ok
    with _reach_lock:
        fails, last = _reach_state.get(auth_url, (0, False))
        if ok:
            result, fails = True, 0
        else:
            fails += 1
            result = False if fails >= _UNREACHABLE_STRIKES else last
        _reach_state[auth_url] = (fails, result)
        return result


# ---------- 网络检测 ----------
def http_get(url, timeout=6, physical=False):
    """获取 URL；macOS 的校园认证请求可强制走物理网卡，避免被 VPN 路由接管。"""
    if physical and (common.IS_MACOS or common.IS_WINDOWS):
        interface = netinfo.get_physical_interface()
        if interface:
            curl = "/usr/bin/curl" if common.IS_MACOS else "curl"
            try:
                # Windows 下 curl.exe 是控制台程序, 必须隐藏窗口, 否则每次探测都会闪黑框
                run_kwargs = {"capture_output": True, "timeout": timeout + 2}
                if common.IS_WINDOWS:
                    run_kwargs["creationflags"] = _NO_WINDOW
                result = subprocess.run(
                    [curl, "--silent", "--show-error", "--max-time", str(timeout),
                     "--noproxy", "*",
                     "--interface", interface, "--output", "-", "--write-out", "\n%{http_code}",
                     "--user-agent", "Mozilla/5.0 AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
                     url],
                    **run_kwargs)
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
    with _DIRECT_OPENER.open(req, timeout=timeout) as resp:
        return resp.status, resp.read()


def decode_gbk(body):
    try:
        return body.decode("gbk", errors="replace")
    except Exception:
        return body.decode("utf-8", errors="replace")


_LOGOUT_TITLES = ("注销页", "注销", "logout", "log out", "log off", "signed out", "已注销")


def _authed_from_page(text):
    """从认证页正文判定是否"已登录"。

    多判据的原因: 旧实现只认死 `<title>注销页</title>` —— 学校一换 Dr.COM 固件版本
    或改语言(标题变成 Logout / 注销 / 已注销), 判定立刻失效, 界面永远显示"掉线",
    守护则每个周期都重登一次, 把别的设备挤下线。

    判据(命中任一即认为已登录):
      1) <title> 是注销页的常见写法
      2) 页面同时含 Dr.COM 特征(drcom)与注销语义(logout/注销) —— 未登录的认证页
         只有"登录"字样, 不会同时出现注销语义, 所以这个组合是可靠的。
    """
    match = re.search(r"<title>\s*([^<]{0,40}?)\s*</title>", text or "", re.I)
    title = match.group(1).strip() if match else ""
    if title and title.lower() in _LOGOUT_TITLES:
        return True
    lowered = (text or "").lower()
    return "drcom" in lowered and re.search(r"(logout|注销)", lowered) is not None


def check_auth(auth_url=common.DEFAULT_AUTH_URL):
    """True=已登录(注销页), False=未登录/不可达"""
    try:
        status, body = http_get(auth_url, timeout=6, physical=True)
        if status != 200:
            return False
        return _authed_from_page(decode_gbk(body))
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


def ensure_login(profile, on_log=None, attempts=6, base_delay=2, max_delay=10,
                 fast_attempts=2):
    """尝试登录(含重试)。返回 True=成功。

    相对旧实现(固定 10 次 × 2s)的三点改进:
    1) **先探一次认证服务器**: 明确不可达时只做 fast_attempts 次快速重试就收工 ——
       校园网链路断开时, 旧实现会干等 10 次 try_login(每次最长 15s)才回到主循环,
       期间界面像卡死、用户点退出也没反应。宁可早点回主循环重新判定环境。
    2) 重试间隔指数退避(2/4/8/10…), 给认证服务器恢复留缓冲, 又不至于空转太久。
    3) 总尝试次数收敛到 6 次, 最坏阻塞从 150s+ 降到 90s 量级。

    探测结论只用来"减少重试次数", 不用来直接跳过登录 —— 探测本身可能抖动,
    不能让一次抖动导致这轮完全不登录。
    """
    auth_url = profile.get("auth_url", common.DEFAULT_AUTH_URL)
    reachable = auth_reachable(auth_url, debounce=False)
    if not reachable:
        attempts = min(attempts, max(1, fast_attempts))
        if on_log:
            on_log("认证服务器不可达, 只快速重试 %d 次(校园网链路可能已断开)" % attempts)
    delay = base_delay
    for i in range(attempts):
        if try_login(profile):
            return True
        if on_log:
            on_log("登录重试 %d/%d 失败" % (i + 1, attempts))
        if i + 1 >= attempts:
            break
        time.sleep(delay)
        delay = min(max_delay, delay * 2)
    return False


# ---------- 守护线程 ----------
