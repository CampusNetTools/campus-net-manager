#!/usr/bin/env python3
"""在已安装的本机 IKEv2 网关上创建一台 iPhone 的私有配置文件。

此脚本必须由安装脚本以管理员权限调用。它不会把用户名或密码打印到终端；
产物仅保存在网关私有目录，供 AirDrop/USB 本地交付后删除。
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ikev2_profile import IKEv2ProfileController


def write_private(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as target:
        target.write(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("device_name")
    parser.add_argument("--server-address", required=True)
    parser.add_argument("--state-dir", default="/opt/homebrew/etc/campusnet-ikev2")
    args = parser.parse_args()
    state_dir = Path(args.state_dir)
    ca_der = (state_dir / "ca-cert.der").read_bytes()
    controller = IKEv2ProfileController(
        args.server_address,
        "vpn.campusnet.local",
        ca_der,
        gateway_ready=True,
        swanctl_available=True,
        dns_servers=("1.1.1.1",),
    )
    profile = controller.create_device_profile(args.device_name)
    profiles = state_dir / "profiles"
    devices = state_dir / "devices"
    profiles.mkdir(mode=0o700, exist_ok=True)
    devices.mkdir(mode=0o700, exist_ok=True)
    write_private(profiles / f"{args.device_name}.mobileconfig", profile.mobileconfig)
    write_private(devices / f"{args.device_name}.conf", profile.swanctl_secret.encode("utf-8"))
    print(f"已创建设备配置：{profiles / (args.device_name + '.mobileconfig')}")
    print(f"已创建服务端凭据：{devices / (args.device_name + '.conf')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
