#!/bin/sh
# 停止本项目的 IKEv2 网关并撤销仅由本项目加入的 PF 锚点。
# 不删除证书、设备描述文件或 /etc/pf.conf.campusnet-ikev2.backup，便于恢复。
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "请使用管理员权限运行此脚本。" >&2
    exit 1
fi

ss_bin=/opt/homebrew/opt/strongswan/bin
pf_conf=/etc/pf.conf

"$ss_bin/ipsec" stop || true
/sbin/pfctl -a campusnet-ikev2 -F all || true
if grep -Fqx 'anchor "campusnet-ikev2"' "$pf_conf"; then
    /usr/bin/sed -i '' '/^anchor "campusnet-ikev2"$/d' "$pf_conf"
    /usr/bin/sed -i '' '/^load anchor "campusnet-ikev2" from "\/etc\/pf\.anchors\/campusnet-ikev2"$/d' "$pf_conf"
    /sbin/pfctl -f "$pf_conf"
fi
echo "已停止 CampusNet IKEv2；证书和原始 PF 备份仍被保留。"
