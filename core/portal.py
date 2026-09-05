# -*- coding: utf-8 -*-
"""认证服务器( captive portal )探测 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import auth, netinfo  # noqa: F401

__all__ = ['_NoRedirect', 'CAPTIVE_PROBES', 'PORTAL_MARKERS', '_origin_url', '_same_site', '_portal_like', '_extract_redirect_urls', '_run_captive_probe', 'discover_auth_servers', 'detect_auth_server']

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


CAPTIVE_PROBES = (
    {"url": "http://connect.rom.miui.com/generate_204", "status": 204, "body": ""},
    {"url": "http://connectivitycheck.gstatic.com/generate_204", "status": 204, "body": ""},
    {"url": "http://www.msftconnecttest.com/connecttest.txt", "status": 200,
     "body": "Microsoft Connect Test"},
    {"url": "http://captive.apple.com/hotspot-detect.html", "status": 200,
     "body": "Success"},
    {"url": "http://www.baidu.com/", "status": 200, "body": "百度一下"},
)

PORTAL_MARKERS = ("dr.com", "drcom", "eportal", "portal", "webauth", "wlan_user_ip",
                  "wlanac", "user_account", "login_method", "bras", "注销页", "认证")


def _origin_url(url):
    """保留 scheme、主机和非默认端口，去除可能包含会话参数的路径与查询串。"""
    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            return None
        host = parsed.hostname
        if ":" in host and not host.startswith("["):
            host = "[%s]" % host
        port = ":%s" % parsed.port if parsed.port else ""
        return "%s://%s%s/" % (parsed.scheme, host, port)
    except (TypeError, ValueError):
        return None


def _same_site(first, second):
    try:
        a = (urllib.parse.urlparse(first).hostname or "").lower()
        b = (urllib.parse.urlparse(second).hostname or "").lower()
        a = a[4:] if a.startswith("www.") else a
        b = b[4:] if b.startswith("www.") else b
        return a == b
    except Exception:
        return False


def _portal_like(text):
    lowered = (text or "").lower()
    return any(marker in lowered for marker in PORTAL_MARKERS)


def _extract_redirect_urls(source_url, headers, body):
    """识别 HTTP Location、HTML meta refresh 和常见 JavaScript 跳转。"""
    found = []
    for match in re.finditer(r"^location:\s*([^\r\n]+)", headers or "", re.I | re.M):
        found.append(urllib.parse.urljoin(source_url, match.group(1).strip()))
    text = body or ""
    patterns = (
        r"http-equiv\s*=\s*['\"]?refresh['\"]?[^>]+content\s*=\s*['\"][^'\"]*url\s*=\s*([^'\";> ]+)",
        r"(?:window\.)?location(?:\.href)?\s*=\s*['\"]([^'\"]+)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.I):
            found.append(urllib.parse.urljoin(source_url, match.group(1).strip()))
    return list(dict.fromkeys(url for url in found if url.startswith(("http://", "https://"))))


def _run_captive_probe(probe, physical=True):
    """执行一个不跟随跳转的 GET，并返回状态、头和小段正文。"""
    url = probe["url"]
    if common.IS_MACOS:
        command = ["/usr/bin/curl", "--silent", "--show-error", "--max-time", "6",
                   "--max-redirs", "0", "--include", "--user-agent",
                   "Mozilla/5.0 AppleWebKit/537.36 Chrome/137.0.0.0 Safari/537.36",
                   "--write-out", "\n__CNM_STATUS__%{http_code}", url]
        if physical:
            interface = netinfo.get_physical_interface()
            if not interface:
                return {"probe": probe, "status": 0, "headers": "", "body": "",
                        "error": "未找到物理网卡"}
            command[7:7] = ["--noproxy", "*", "--interface", interface]
        try:
            result = subprocess.run(command, capture_output=True, timeout=8)
        except Exception as error:
            return {"probe": probe, "status": 0, "headers": "", "body": "", "error": str(error)}
        text = result.stdout.decode("utf-8", errors="replace")
        status_match = re.search(r"__CNM_STATUS__(\d{3})\s*$", text)
        status = int(status_match.group(1)) if status_match else 0
        text = text[:status_match.start()] if status_match else text
        head, _, body = text.partition("\r\n\r\n")
        if not body:
            head, _, body = text.partition("\n\n")
        return {"probe": probe, "status": status, "headers": head, "body": body[:65536]}

    opener = urllib.request.build_opener(_NoRedirect)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with opener.open(request, timeout=6) as response:
            return {"probe": probe, "status": response.status,
                    "headers": str(response.headers),
                    "body": response.read(65536).decode("utf-8", errors="replace")}
    except urllib.error.HTTPError as error:
        return {"probe": probe, "status": error.code, "headers": str(error.headers),
                "body": error.read(65536).decode("utf-8", errors="replace")}
    except Exception as error:
        return {"probe": probe, "status": 0, "headers": "", "body": "", "error": str(error)}


def discover_auth_servers(known_urls=None):
    """从多组 204/正文探针和已知地址发现多个认证服务候选。"""
    candidates = {}
    online = False
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CAPTIVE_PROBES)) as pool:
        results = list(pool.map(lambda probe: _run_captive_probe(probe, physical=True), CAPTIVE_PROBES))

    for result in results:
        probe = result["probe"]
        body = result.get("body", "")
        expected_body = probe.get("body", "")
        if result.get("status") == probe["status"] and (not expected_body or expected_body in body):
            online = True
        combined = "%s\n%s" % (result.get("headers", ""), body)
        redirects = _extract_redirect_urls(probe["url"], result.get("headers", ""), body)
        for redirected in redirects:
            if _same_site(probe["url"], redirected):
                continue
            origin = _origin_url(redirected)
            if not origin:
                continue
            private = False
            try:
                private = ipaddress.ip_address(socket.gethostbyname(urllib.parse.urlparse(origin).hostname)).is_private
            except Exception:
                pass
            if private or _portal_like(redirected + " " + combined):
                candidates[origin] = {
                    "url": origin, "confidence": 100 if private or _portal_like(combined) else 75,
                    "source": "重定向", "probe": probe["url"],
                }

    for known in list(dict.fromkeys(url for url in (known_urls or []) if url)):
        origin = _origin_url(known)
        if not origin or origin in candidates:
            continue
        try:
            status, raw = auth.http_get(origin, timeout=5, physical=True)
            text = auth.decode_gbk(raw[:131072])
            if status == 200 and (_portal_like(origin + " " + text) or origin == common.DEFAULT_AUTH_URL):
                candidates[origin] = {"url": origin, "confidence": 90,
                                      "source": "已知地址验证", "probe": origin}
        except Exception:
            continue

    ordered = sorted(candidates.values(), key=lambda item: (-item["confidence"], item["url"]))
    return {"candidates": ordered, "online": online, "probes": results}


def detect_auth_server(known_urls=None):
    """兼容旧接口：返回多来源发现结果中可信度最高的认证服务器。"""
    result = discover_auth_servers(known_urls)
    return result["candidates"][0]["url"] if result["candidates"] else None
