# -*- coding: utf-8 -*-
"""iPhone Packet Tunnel 配对状态机。

不创建 TUN、不改 pf、不记录包内容。那些需要特权的网关操作必须由独立、
经过用户确认的 macOS helper 实现；本模块只负责最小化的短期配对令牌。
"""
import base64
import datetime as dt
import json
import secrets
import threading
import urllib.parse


PAIRING_TTL_SECONDS = 60


class GatewayNotReady(RuntimeError):
    pass


class PairingController:
    def __init__(self, host, port=9443, certificate_pin="", gateway_ready=False):
        self.host = host
        self.port = int(port)
        self.certificate_pin = certificate_pin
        self.gateway_ready = bool(gateway_ready)
        self._tokens = {}
        self._lock = threading.Lock()

    def readiness(self):
        if not self.gateway_ready:
            return False, "电脑 Packet Tunnel 网关尚未安装，不能生成可连接的二维码。"
        if not self.host or not 1 <= self.port <= 65535:
            return False, "电脑网关地址或端口无效。"
        if len(self.certificate_pin) != 64 or any(c not in "0123456789abcdefABCDEF" for c in self.certificate_pin):
            return False, "电脑网关缺少 TLS 证书指纹，拒绝生成不安全的配对码。"
        return True, "电脑网关已就绪，可生成一次性配对码。"

    def create_qr_url(self, now=None):
        ok, message = self.readiness()
        if not ok:
            raise GatewayNotReady(message)
        now = now or dt.datetime.now(dt.timezone.utc)
        token = secrets.token_urlsafe(32)
        payload = {
            "version": 1,
            "gatewayHost": self.host,
            "gatewayPort": self.port,
            "enrollmentToken": token,
            "certificatePinSHA256": self.certificate_pin.lower(),
            "expiresAt": (now + dt.timedelta(seconds=PAIRING_TTL_SECONDS)).isoformat().replace("+00:00", "Z"),
        }
        encoded = base64.b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")).decode("ascii")
        with self._lock:
            self._purge(now)
            self._tokens[token] = now + dt.timedelta(seconds=PAIRING_TTL_SECONDS)
        return "campusnet://pair?" + urllib.parse.urlencode({"payload": encoded})

    def redeem(self, token, now=None):
        """网关 TLS 握手时兑换一次；成功后令牌立刻失效。"""
        now = now or dt.datetime.now(dt.timezone.utc)
        with self._lock:
            expires = self._tokens.pop(token, None)
        return bool(expires and expires > now)

    def _purge(self, now):
        self._tokens = {token: expires for token, expires in self._tokens.items()
                        if expires > now}
