#!/bin/sh
# 在 macOS 上安装本项目专用的 IKEv2 网关。须由管理员运行。
# 所有可移除的系统状态均位于 campusnet-ikev2 命名空间；不改写既有 VPN 配置。
set -eu

if [ "$(id -u)" -ne 0 ]; then
    echo "请使用管理员权限运行此脚本。" >&2
    exit 1
fi

server_address=${1:?需要传入当前 Mac 的局域网 IPv4 地址}
case "$server_address" in
    *[!0-9.]*|*..*|.*|*.) echo "服务器地址不是 IPv4：$server_address" >&2; exit 2 ;;
esac

ss_prefix=/opt/homebrew/opt/strongswan
ss_bin="$ss_prefix/bin"
state_dir=/opt/homebrew/etc/campusnet-ikev2
pf_anchor=/etc/pf.anchors/campusnet-ikev2
pf_conf=/etc/pf.conf
pf_backup=/etc/pf.conf.campusnet-ikev2.backup

test -x "$ss_bin/ipsec"
test -x "$ss_bin/swanctl"
test -x "$ss_bin/pki"

umask 077
mkdir -p "$state_dir"
if [ ! -f "$state_dir/ca-cert.pem" ]; then
    "$ss_bin/pki" --gen --type rsa --size 3072 --outform pem > "$state_dir/ca-key.pem"
    "$ss_bin/pki" --self --ca --lifetime 3650 --in "$state_dir/ca-key.pem" --type rsa \
        --dn 'CN=CampusNet IKEv2 Local CA' --outform pem > "$state_dir/ca-cert.pem"
    "$ss_bin/pki" --gen --type rsa --size 3072 --outform pem > "$state_dir/server-key.pem"
    "$ss_bin/pki" --pub --in "$state_dir/server-key.pem" --type rsa | \
        "$ss_bin/pki" --issue --lifetime 825 --cacert "$state_dir/ca-cert.pem" \
        --cakey "$state_dir/ca-key.pem" --dn 'CN=vpn.campusnet.local' \
        --san "$server_address" --san 'vpn.campusnet.local' --flag serverAuth --outform pem \
        > "$state_dir/server-cert.pem"
    /opt/homebrew/opt/openssl@3/bin/openssl x509 -in "$state_dir/ca-cert.pem" -outform der \
        -out "$state_dir/ca-cert.der"
fi

cat > "$state_dir/swanctl.conf" <<EOF
connections {
  campusnet-ikev2 {
    version = 2
    local_addrs = $server_address
    proposals = aes256gcm16-prfsha256-ecp256,aes256-sha256-modp2048
    local {
      auth = pubkey
      certs = $state_dir/server-cert.pem
      id = vpn.campusnet.local
    }
    remote {
      auth = eap-mschapv2
      eap_id = %any
    }
    children {
      iphone-full-tunnel {
        local_ts = 0.0.0.0/0
        esp_proposals = aes256gcm16-ecp256,aes256-sha256-modp2048
      }
    }
    pools = campusnet-iphone
    send_cert = always
  }
}
pools {
  campusnet-iphone {
    addrs = 10.203.0.0/24
    dns = 1.1.1.1
  }
}
secrets {
  private-server-key {
    file = $state_dir/server-key.pem
  }
}
EOF

cat > "$pf_anchor" <<EOF
# 由校园网连接管家管理；删除本文件并移除 pf.conf 中同名两行即可撤销。
nat on { en0, utun6 } from 10.203.0.0/24 to any -> (egress:0)
pass in quick on en0 proto udp from any to $server_address port { 500, 4500 } keep state
pass in quick from 10.203.0.0/24 to any keep state
pass out quick on { en0, utun6 } from 10.203.0.0/24 to any keep state
EOF

if ! grep -Fqx 'anchor "campusnet-ikev2"' "$pf_conf"; then
    cp -p "$pf_conf" "$pf_backup"
    printf '\nanchor "campusnet-ikev2"\nload anchor "campusnet-ikev2" from "/etc/pf.anchors/campusnet-ikev2"\n' >> "$pf_conf"
fi

/sbin/pfctl -f "$pf_conf"
/sbin/pfctl -E >/dev/null 2>&1 || true
"$ss_bin/ipsec" start
sleep 1
"$ss_bin/swanctl" --load-all --file "$state_dir/swanctl.conf"
"$ss_bin/swanctl" --list-conns
echo "已启动 CampusNet IKEv2；证书和配置位于 $state_dir。"
