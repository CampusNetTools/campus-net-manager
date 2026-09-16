# -*- coding: utf-8 -*-
"""安全解析代理订阅并生成 mihomo 配置。

只处理本项目当前需要的 VLESS 与 Hysteria2 URI；不记录原始 URI、UUID、
密码、服务器或订阅地址。输出 YAML 使用 JSON 字符串语法，避免额外依赖 PyYAML。
"""
from __future__ import annotations

import base64
import json
import re
import secrets
from collections import Counter
from urllib import request as urlrequest
from urllib.parse import parse_qs, unquote, urlsplit


MAX_SUBSCRIPTION_BYTES = 2 * 1024 * 1024
SUPPORTED_SCHEMES = {"vless", "hysteria2", "hy2"}


class SubscriptionError(ValueError):
    pass


def _first(query, *keys, default=""):
    for key in keys:
        values = query.get(key)
        if values:
            return values[0]
    return default


def _truthy(value):
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def decode_subscription(raw):
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not raw or len(raw) > MAX_SUBSCRIPTION_BYTES:
        raise SubscriptionError("订阅为空或超过 2 MB 安全上限")
    text = raw.decode("utf-8-sig", errors="strict").strip()
    if "://" in text:
        return [line.strip() for line in text.splitlines() if line.strip()]
    compact = "".join(text.split())
    try:
        decoded = base64.b64decode(compact + "=" * (-len(compact) % 4), validate=True)
        text = decoded.decode("utf-8-sig", errors="strict")
    except Exception as exc:
        raise SubscriptionError("订阅既不是 URI 列表，也不是有效 Base64") from exc
    return [line.strip() for line in text.splitlines() if line.strip()]


def _safe_name(fragment, fallback):
    value = unquote(fragment or "").strip() or fallback
    value = re.sub(r"[\x00-\x1f\x7f]", "", value)[:80]
    return value or fallback


def _parse_vless(uri, index):
    parsed = urlsplit(uri)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if not parsed.hostname or not parsed.port or not parsed.username:
        raise SubscriptionError("VLESS 节点缺少服务器、端口或 UUID")
    node = {
        "name": _safe_name(parsed.fragment, "VLESS-%d" % index),
        "type": "vless",
        "server": parsed.hostname,
        "port": parsed.port,
        "uuid": unquote(parsed.username),
        "udp": True,
        "network": _first(query, "type", default="tcp") or "tcp",
    }
    security = _first(query, "security").lower()
    if security in {"tls", "reality"}:
        node["tls"] = True
    sni = _first(query, "sni", "servername")
    if sni:
        node["servername"] = sni
    if _truthy(_first(query, "allowInsecure", "insecure")):
        node["skip-cert-verify"] = True
    flow = _first(query, "flow")
    if flow:
        node["flow"] = flow
    fingerprint = _first(query, "fp")
    if fingerprint:
        node["client-fingerprint"] = fingerprint
    if security == "reality":
        public_key = _first(query, "pbk", "public-key")
        short_id = _first(query, "sid", "short-id")
        if not public_key:
            raise SubscriptionError("REALITY 节点缺少公钥")
        node["reality-opts"] = {"public-key": public_key, "short-id": short_id}
    if node["network"] == "ws":
        ws_opts = {"path": _first(query, "path", default="/") or "/"}
        host = _first(query, "host")
        if host:
            ws_opts["headers"] = {"Host": host}
        node["ws-opts"] = ws_opts
    elif node["network"] == "grpc":
        service = _first(query, "serviceName", "service-name")
        if service:
            node["grpc-opts"] = {"grpc-service-name": service}
    return node


def _parse_hysteria2(uri, index):
    parsed = urlsplit(uri)
    query = parse_qs(parsed.query, keep_blank_values=True)
    auth = unquote(parsed.username or "")
    if parsed.password:
        auth += ":" + unquote(parsed.password)
    if not parsed.hostname or not parsed.port or not auth:
        raise SubscriptionError("Hysteria2 节点缺少服务器、端口或认证信息")
    node = {
        "name": _safe_name(parsed.fragment, "Hysteria2-%d" % index),
        "type": "hysteria2",
        "server": parsed.hostname,
        "port": parsed.port,
        "password": auth,
    }
    sni = _first(query, "sni", "peer")
    if sni:
        node["sni"] = sni
    if _truthy(_first(query, "insecure", "allowInsecure")):
        node["skip-cert-verify"] = True
    obfs = _first(query, "obfs")
    obfs_password = _first(query, "obfs-password", "obfsPassword")
    if obfs:
        node["obfs"] = obfs
    if obfs_password:
        node["obfs-password"] = obfs_password
    return node


def parse_subscription(raw):
    nodes = []
    rejected = 0
    for index, uri in enumerate(decode_subscription(raw), 1):
        scheme = urlsplit(uri).scheme.lower()
        try:
            if scheme == "vless":
                nodes.append(_parse_vless(uri, index))
            elif scheme in {"hysteria2", "hy2"}:
                nodes.append(_parse_hysteria2(uri, index))
            else:
                rejected += 1
        except (SubscriptionError, ValueError):
            rejected += 1
    if not nodes:
        raise SubscriptionError("订阅中没有可用的 VLESS/Hysteria2 节点")
    seen = Counter()
    for node in nodes:
        base = node["name"]
        seen[base] += 1
        if seen[base] > 1:
            node["name"] = "%s (%d)" % (base, seen[base])
    return nodes, rejected


def fetch_subscription(url, timeout=30):
    parsed = urlsplit((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise SubscriptionError("订阅地址必须是有效 HTTPS URL")
    opener = urlrequest.build_opener(urlrequest.ProxyHandler({}))
    req = urlrequest.Request(url, headers={"User-Agent": "CampusNetManager/5"})
    with opener.open(req, timeout=timeout) as response:
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_SUBSCRIPTION_BYTES:
            raise SubscriptionError("订阅响应超过 2 MB 安全上限")
        raw = response.read(MAX_SUBSCRIPTION_BYTES + 1)
    if len(raw) > MAX_SUBSCRIPTION_BYTES:
        raise SubscriptionError("订阅响应超过 2 MB 安全上限")
    return raw


def subscription_summary(nodes, rejected=0):
    protocols = Counter(node.get("type", "unknown") for node in nodes)
    return {"node_count": len(nodes), "protocols": dict(protocols), "rejected": rejected}


# 订阅里可能出现的协议 (用于「切换协议」: 部署时只保留勾选的协议)
PROTOCOL_OPTIONS = (("vless", "VLESS"), ("hysteria2", "Hysteria2"))
DEFAULT_PROTOCOLS = ("vless", "hysteria2")


def filter_by_protocols(nodes, allow_types=None):
    """按协议过滤节点; allow_types 为空表示不过滤。

    校园网对 UDP 的态度不稳定, Hysteria2 这类基于 UDP 的协议可能整体不可用,
    因此部署前允许只保留 VLESS, 避免把一堆必然失败的节点塞进配置里。
    """
    if not allow_types:
        return list(nodes)
    allowed = {str(item).lower() for item in allow_types}
    return [n for n in nodes if str(n.get("type", "")).lower() in allowed]


def protocol_labels(allow_types):
    """协议标识 -> 展示名, 用于 UI 与日志。"""
    wanted = {str(item).lower() for item in (allow_types or ())}
    return [label for key, label in PROTOCOL_OPTIONS if key in wanted]


def _yaml_value(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _emit_mapping(lines, mapping, indent):
    prefix = " " * indent
    for key, value in mapping.items():
        if isinstance(value, dict):
            lines.append("%s%s:" % (prefix, key))
            _emit_mapping(lines, value, indent + 2)
        else:
            lines.append("%s%s: %s" % (prefix, key, _yaml_value(value)))


def build_mihomo_config(nodes, controller_secret=None, allow_types=None):
    nodes = filter_by_protocols(nodes, allow_types)
    if not nodes:
        raise SubscriptionError("按所选协议过滤后没有可用节点")
    secret = controller_secret or secrets.token_urlsafe(24)
    names = [node["name"] for node in nodes]
    lines = [
        "# Generated by CampusNetManager; contains credentials. chmod 600.",
        "mixed-port: 7890",
        "tproxy-port: 7891",
        "redir-port: 7892",
        "allow-lan: true",
        "bind-address: \"*\"",
        "mode: rule",
        "log-level: warning",
        "profile:",
        "  store-selected: true",
        "external-controller: \"0.0.0.0:9091\"",
        "secret: %s" % _yaml_value(secret),
        "ipv6: false",
        "dns:",
        "  enable: true",
        "  listen: \"0.0.0.0:1053\"",
        "  enhanced-mode: redir-host",
        "  ipv6: false",
        "  nameserver:",
        "    - \"223.5.5.5\"",
        "    - \"119.29.29.29\"",
        "sniffer:",
        "  enable: true",
        "  force-dns-mapping: true",
        "  parse-pure-ip: true",
        "  sniff:",
        "    TLS:",
        "      ports: [443, 8443]",
        "    HTTP:",
        "      ports: [80, 8080]",
        "      override-destination: true",
        "proxies:",
    ]
    for node in nodes:
        lines.append("  - name: %s" % _yaml_value(node["name"]))
        _emit_mapping(lines, {k: v for k, v in node.items() if k != "name"}, 4)
    lines.extend([
        "proxy-groups:",
        "  - name: \"节点选择\"",
        "    type: select",
        "    proxies:",
        "      - \"自动选择\"",
        "      - \"故障转移\"",
    ])
    lines.extend("      - %s" % _yaml_value(name) for name in names)
    lines.extend([
        "  - name: \"自动选择\"",
        "    type: url-test",
        "    url: \"https://www.gstatic.com/generate_204\"",
        "    interval: 300",
        "    tolerance: 100",
        "    proxies:",
    ])
    lines.extend("      - %s" % _yaml_value(name) for name in names)
    lines.extend([
        "  - name: \"故障转移\"",
        "    type: fallback",
        "    url: \"https://cp.cloudflare.com/generate_204\"",
        "    interval: 120",
        "    proxies:",
    ])
    lines.extend("      - %s" % _yaml_value(name) for name in names)
    # Split routing: private/LAN traffic is excluded again at the mihomo layer,
    # Chinese domains and Chinese destination IPs stay direct, and only the
    # remainder uses the selected subscription node. GEOIP uses the local
    # geoip.metadb already installed on the router, so runtime does not depend
    # on downloading a ruleset from GitHub.
    lines.extend([
        "rules:",
        "  - \"DOMAIN-SUFFIX,cn,DIRECT\"",
        "  - \"GEOIP,CN,DIRECT\"",
        "  - \"MATCH,节点选择\"",
        "",
    ])
    return "\n".join(lines), secret
