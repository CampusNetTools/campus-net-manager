# -*- coding: utf-8 -*-
"""测速与网络质量评分 (自 keepalive_core.py 拆分, 跨模块调用一律 模块.名字 风格)"""
from core.common import *  # noqa: F401,F403
from core import common  # noqa: F401
from core import netinfo  # noqa: F401

__all__ = ['_curl_speed_request', '_latency_from_timing', 'score_speed_quality', 'run_speed_test']

def _curl_speed_request(url, method="GET", upload_bytes=0, physical=False, timeout=20,
                        allow_timed_sample=False):
    """执行一次有限流量的 curl 测量，返回 curl 的结构化计时字段。"""
    curl = "/usr/bin/curl" if common.IS_MACOS else "curl.exe"
    command = [curl, "--silent", "--show-error", "--location", "--max-time", str(timeout),
               "--output", os.devnull,
               "--write-out", "%{http_code}\t%{time_namelookup}\t%{time_connect}\t%{time_appconnect}\t%{time_pretransfer}\t%{time_starttransfer}\t%{time_total}\t%{size_download}\t%{size_upload}\t%{remote_ip}"]
    if physical and common.IS_MACOS:
        interface = netinfo.get_physical_interface()
        if not interface:
            raise RuntimeError("未找到可用的物理网卡")
        command.extend(["--noproxy", "*", "--interface", interface])
    payload = None
    if method == "POST":
        command.extend(["--request", "POST", "--header", "Content-Type: application/octet-stream",
                        "--data-binary", "@-"])
        payload = b"\0" * upload_bytes
    command.append(url)
    kwargs = {"input": payload, "capture_output": True, "timeout": timeout + 3}
    if common.IS_WINDOWS:
        kwargs["creationflags"] = _NO_WINDOW
    result = subprocess.run(command, **kwargs)
    parts = result.stdout.decode("ascii", errors="replace").strip().split("\t")
    timed_sample = False
    if result.returncode != 0:
        # curl 在 --max-time 到期时仍会输出完整计时数据。测速流量较慢但已经
        # 持续传输时，这本身就是有效的限时测速样本，不应误报为断网。
        try:
            transferred = float(parts[7]) + float(parts[8])
            elapsed = float(parts[6])
            timed_sample = (allow_timed_sample and result.returncode == 28
                            and len(parts) == 10 and parts[0].startswith("2")
                            and transferred >= 65536 and elapsed >= 5.0)
        except (ValueError, IndexError):
            timed_sample = False
        if not timed_sample:
            detail = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "测速请求失败")
    if len(parts) != 10 or not parts[0].startswith("2"):
        raise RuntimeError("测速服务器返回异常（HTTP %s）" % (parts[0] if parts else "?"))
    return {
        "status": int(parts[0]), "lookup": float(parts[1]), "connect": float(parts[2]),
        "appconnect": float(parts[3]), "pretransfer": float(parts[4]), "ttfb": float(parts[5]),
        "total": float(parts[6]), "downloaded": float(parts[7]), "uploaded": float(parts[8]),
        "remote_ip": parts[9], "timed_sample": timed_sample,
    }


def _latency_from_timing(sample):
    """优先使用 TCP 建连往返，避免把服务端首字节等待误当网络延迟。"""
    connect = sample.get("connect", 0.0)
    lookup = sample.get("lookup", 0.0)
    appconnect = sample.get("appconnect", 0.0)
    tcp_latency = max(0.0, connect - lookup)
    tls_time = max(0.0, appconnect - connect)
    # TUN/本地代理可能在本机立即接收 TCP，使 connect 接近 0；此时用 TLS 握手
    # 的半程时间估算 RTT，比直接使用服务端 TTFB 更接近真实链路延迟。
    if tcp_latency < 0.005 and tls_time > 0.020:
        return tls_time * 500.0
    if tcp_latency > 0:
        return tcp_latency * 1000.0
    if appconnect > connect:
        return (appconnect - connect) * 500.0
    return sample.get("ttfb", 0.0) * 1000.0


def score_speed_quality(latency_ms, jitter_ms, download_mbps, upload_mbps, success_rate):
    """给出可解释的 0-100 网络质量分，不替代专业 SLA 测试。"""
    score = 100.0
    score -= max(0.0, latency_ms - 30.0) * 0.22
    score -= max(0.0, jitter_ms - 5.0) * 0.8
    score -= max(0.0, 30.0 - download_mbps) * 0.55
    score -= max(0.0, 8.0 - upload_mbps) * 1.0
    score -= max(0.0, 100.0 - success_rate) * 0.8
    score = max(0, min(100, int(round(score))))
    grade = "优秀" if score >= 90 else "流畅" if score >= 75 else "一般" if score >= 60 else "较差"
    return score, grade


def run_speed_test(path="current", download_bytes=10000000, upload_bytes=2000000, progress=None):
    """限流量测速。path=current 测当前/VPN路径，physical 在 macOS 上绑定物理网卡绕过 VPN。"""
    if path not in ("current", "physical"):
        raise ValueError("未知测速路径")
    physical = path == "physical"
    if physical and not common.IS_MACOS:
        raise RuntimeError("绕过 VPN 的物理路径测速当前仅支持 macOS")
    notify = progress or (lambda _text: None)
    base = "https://speed.cloudflare.com"
    latency = []
    remote_ip = ""
    sample_count = 6
    notify("正在测量延迟、抖动和请求成功率…")
    def latency_probe(index):
        try:
            return _curl_speed_request("%s/__down?bytes=0&r=%d" % (base, index),
                                       physical=physical, timeout=8)
        except Exception:
            return None
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        samples = list(pool.map(latency_probe, range(sample_count)))
    for sample in samples:
        if sample:
            latency.append(_latency_from_timing(sample))
            remote_ip = sample["remote_ip"] or remote_ip
    if len(latency) < 2:
        raise RuntimeError("延迟探测成功次数不足")
    notify("正在测量下载速度（约 %.0f MB）…" % (download_bytes / 1000000.0))
    down = _curl_speed_request("%s/__down?bytes=%d" % (base, download_bytes),
                               physical=physical, timeout=25, allow_timed_sample=True)
    notify("正在测量上传速度（约 %.0f MB）…" % (upload_bytes / 1000000.0))
    up = _curl_speed_request("%s/__up" % base, method="POST", upload_bytes=upload_bytes,
                             physical=physical, timeout=25, allow_timed_sample=True)
    down_mbps = (down["downloaded"] * 8.0 / 1000000.0) / max(down["total"], 0.001)
    up_mbps = (up["uploaded"] * 8.0 / 1000000.0) / max(up["total"], 0.001)
    latency_median = sorted(latency)[len(latency) // 2]
    jitter = sum(abs(latency[i] - latency[i - 1]) for i in range(1, len(latency))) / (len(latency) - 1)
    success_rate = len(latency) * 100.0 / sample_count
    score, grade = score_speed_quality(latency_median, jitter, down_mbps, up_mbps, success_rate)
    return {
        "path": path,
        "path_label": ("未经过 VPN（直连网络）" if physical else
                       "当前系统路径（%s）" % ("经过 VPN" if netinfo.vpn_active() else "未检测到 VPN")),
        "interface": netinfo.get_physical_interface() if physical else "",
        "latency_ms": latency_median,
        "jitter_ms": jitter,
        "success_rate": success_rate,
        "download_mbps": down_mbps,
        "upload_mbps": up_mbps,
        "quality_score": score,
        "quality_grade": grade,
        "remote_ip": down["remote_ip"] or remote_ip,
        "traffic_mb": (down["downloaded"] + up["uploaded"]) / 1000000.0,
    }


# 常见路由器品牌 OUI (MAC 前 3 字节) 库, 用于识别路由器品牌给对应操作指引
