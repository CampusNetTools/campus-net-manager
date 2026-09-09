# -*- coding: utf-8 -*-
"""为 iPhone 系统内建 IKEv2 VPN 生成一次性安装描述文件。

不启动 IKE 守护进程、不安装证书、不改路由或防火墙。只有 Mac 网关经过用户
确认并就绪后，才输出包含独立 EAP 凭据的 .mobileconfig 与服务端片段。
"""
from __future__ import annotations

import ipaddress
import plistlib
import secrets
import shutil
import uuid
from dataclasses import dataclass, field


class IKEv2GatewayNotReady(RuntimeError):
    pass


def _valid_host(value):
    if not value or len(value) > 253:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        labels = value.split(".")
        return all(label and len(label) <= 63 and label.replace("-", "").isalnum()
                   and not label.startswith("-") and not label.endswith("-") for label in labels)


@dataclass(frozen=True)
class IKEv2DeviceProfile:
    device_name: str
    username: str
    password: str = field(repr=False)
    mobileconfig: bytes = field(repr=False)
    swanctl_secret: str = field(repr=False)


class IKEv2ProfileController:
    def __init__(self, server_host, server_identifier, ca_certificate_der,
                 gateway_ready=False, swanctl_available=None, dns_servers=("1.1.1.1",)):
        self.server_host = server_host
        self.server_identifier = server_identifier
        self.ca_certificate_der = ca_certificate_der
        self.gateway_ready = bool(gateway_ready)
        self.swanctl_available = shutil.which("swanctl") is not None if swanctl_available is None else bool(swanctl_available)
        self.dns_servers = tuple(dns_servers)

    def readiness(self):
        if not self.gateway_ready:
            return False, "Mac IKEv2 网关尚未由用户安装和授权，不能生成可连接的描述文件。"
        if not self.swanctl_available:
            return False, "未检测到 IKEv2 网关工具 swanctl，不能生成或应用设备凭据。"
        if not _valid_host(self.server_host) or not _valid_host(self.server_identifier):
            return False, "IKEv2 服务器地址或证书标识无效。"
        if not isinstance(self.ca_certificate_der, bytes) or not self.ca_certificate_der:
            return False, "缺少 Mac 网关 CA 证书，拒绝生成无法验证服务器身份的描述文件。"
        if not self.dns_servers or any(not _valid_host(server) for server in self.dns_servers):
            return False, "DNS 配置无效。"
        return True, "Mac IKEv2 网关已就绪，可生成一台 iPhone 的安装描述文件。"

    def create_device_profile(self, device_name):
        ok, message = self.readiness()
        if not ok:
            raise IKEv2GatewayNotReady(message)
        if not device_name or len(device_name) > 32 or not device_name.replace("-", "").replace("_", "").isalnum():
            raise ValueError("设备名仅可含字母、数字、下划线和连字符，长度不超过32位。")
        username = "iphone-" + secrets.token_hex(8)
        password = secrets.token_urlsafe(32)
        profile = self._profile(device_name, username, password)
        secret = "\n".join((
            "# CampusNet iPhone: " + device_name,
            "secrets {",
            "  " + username + " {",
            "    id = " + username,
            "    secret = " + password,
            "  }",
            "}",
            "",
        ))
        return IKEv2DeviceProfile(device_name, username, password,
                                  plistlib.dumps(profile, fmt=plistlib.FMT_XML, sort_keys=True), secret)

    def _profile(self, device_name, username, password):
        root_uuid = str(uuid.uuid4()).upper()
        vpn_uuid = str(uuid.uuid4()).upper()
        profile_uuid = str(uuid.uuid4()).upper()
        certificate = {
            "PayloadType": "com.apple.security.root",
            "PayloadVersion": 1,
            "PayloadIdentifier": "com.campusnettools.ikev2.ca." + root_uuid.lower(),
            "PayloadUUID": root_uuid,
            "PayloadDisplayName": "校园网连接管家 IKEv2 网关证书",
            "PayloadCertificateFileName": "campusnet-ikev2-ca.cer",
            "PayloadContent": self.ca_certificate_der,
        }
        ikev2 = {
            "RemoteAddress": self.server_host,
            "RemoteIdentifier": self.server_identifier,
            "LocalIdentifier": username,
            # Apple 的 IKEv2 描述文件在服务端使用 X.509 证书、客户端使用
            # EAP-MSCHAPv2 时，必须以 Certificate 认证 IKE 服务器；不能用
            # None 绕过服务器身份校验。未设置客户端 PayloadCertificateUUID 时，
            # ExtendedAuthEnabled 会使用下方的独立 EAP 凭据。
            "AuthenticationMethod": "Certificate",
            "ExtendedAuthEnabled": 1,
            "AuthName": username,
            "AuthPassword": password,
            "DeadPeerDetectionRate": "Medium",
            "DisableMOBIKE": 0,
            "EnablePFS": 1,
            "IncludeAllNetworks": 1,
        }
        vpn = {
            "PayloadType": "com.apple.vpn.managed",
            "PayloadVersion": 1,
            "PayloadIdentifier": "com.campusnettools.ikev2.vpn." + vpn_uuid.lower(),
            "PayloadUUID": vpn_uuid,
            "PayloadDisplayName": "校园网连接管家 · " + device_name,
            "UserDefinedName": "校园网连接管家 · " + device_name,
            "VPNType": "IKEv2",
            "IKEv2": ikev2,
            "DNS": {"ServerAddresses": list(self.dns_servers)},
        }
        return {
            "PayloadType": "Configuration",
            "PayloadVersion": 1,
            "PayloadIdentifier": "com.campusnettools.ikev2.profile." + profile_uuid.lower(),
            "PayloadUUID": profile_uuid,
            "PayloadDisplayName": "校园网连接管家 IKEv2 · " + device_name,
            "PayloadDescription": "仅用于连接此 Mac 的本地 IKEv2 网关。移除描述文件即可撤销手机端配置。",
            "PayloadContent": [certificate, vpn],
        }
