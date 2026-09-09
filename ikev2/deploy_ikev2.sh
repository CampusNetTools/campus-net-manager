#!/bin/bash
# ============================================================
# 校园网连接管家 · IKEv2 网关一键部署 (v1.0)
# 用法: sudo bash /Users/nanyu/Desktop/校园连接助手/ikev2/deploy_ikev2.sh [可选:目标IP]
# 作用: 启动 strongSwan 网关 + 开启 IP 转发/NAT + 加载 iPhone 凭据
#       IP 变化时重跑本脚本即可(自动重签服务器证书并更新手机描述文件)
# ============================================================
set -e
SW=/opt/homebrew/Cellar/strongswan/6.1.0
ETC=/opt/homebrew/etc/strongswan
PROJ="$(cd "$(dirname "$0")/.." && pwd)"
OLD_IP=192.168.31.30

# ---------- 0. 环境检测 ----------
IFACE=$(route -n get default 2>/dev/null | awk '/interface/{print $2}')
IP=${1:-$(ipconfig getifaddr "$IFACE" 2>/dev/null)}
if [ -z "$IP" ]; then echo "❌ 未检测到网络, 请连网后重试"; exit 1; fi
echo "▶ 网卡: $IFACE · 本机 IP: $IP"

# ---------- 1. IP 变化时: 重签服务器证书 + 更新配置与描述文件 ----------
if [ "$IP" != "$OLD_IP" ] && [ ! -f "$PROJ/ikev2/.signed-for-$IP" ]; then
  echo "== IP 已变化($OLD_IP → $IP): 重签服务器证书 =="
  openssl req -new -key "$PROJ/ikev2/server-key.pem" \
    -subj "/C=CN/O=CampusNetTools/CN=campusnet-gateway" -out "$PROJ/ikev2/server.csr"
  printf "subjectAltName=IP:%s,DNS:campusnet-gateway\nextendedKeyUsage=serverAuth\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyAgreement\n" "$IP" \
    > "$PROJ/ikev2/server-ext.cnf"
  openssl x509 -req -days 825 -in "$PROJ/ikev2/server.csr" \
    -CA "$PROJ/ikev2/ca-cert.pem" -CAkey "$PROJ/ikev2/ca-key.pem" -CAcreateserial \
    -out "$PROJ/ikev2/server-cert.pem" -extfile "$PROJ/ikev2/server-ext.cnf" 2>/dev/null
  cp "$PROJ/ikev2/server-cert.pem" "$ETC/swanctl/x509/campusnet-server.pem"
  sed -i '' "s/local_addrs = .*/local_addrs = $IP/; s/id = $OLD_IP/id = $IP/" "$ETC/swanctl.conf"
  MC="$PROJ/ikev2/pending/iPhone-校园网VPN.mobileconfig"
  [ -f "$MC" ] && sed -i '' "s/$OLD_IP/$IP/g" "$MC"
  touch "$PROJ/ikev2/.signed-for-$IP"
  echo "   证书/配置/描述文件已更新到 $IP"
fi

# ---------- 2. 启动 charon 服务端 ----------
if pgrep -x charon >/dev/null 2>&1; then
  echo "== 2/6 charon 已在运行 =="
else
  echo "== 2/6 启动 charon 服务端 =="
  mkdir -p /var/run
  "$SW/libexec/ipsec/charon" > /tmp/charon.stdout 2>&1 &
  for i in $(seq 1 20); do
    [ -S /var/run/charon.vici ] && break
    sleep 0.5
  done
  [ -S /var/run/charon.vici ] || { echo "❌ charon 启动失败, 查看 /tmp/charon.log"; exit 1; }
  echo "   charon 已启动 (vici 就绪)"
fi

# ---------- 3. 加载连接/证书/凭据 ----------
echo "== 3/6 加载 swanctl 配置 =="
"$SW/bin/swanctl" --load-all --file "$ETC/swanctl.conf" 2>&1 | grep -v "^$" | sed 's/^/   /'
"$SW/bin/swanctl" --list-conns 2>&1 | head -4 | sed 's/^/   /'

# ---------- 4. IP 转发 ----------
echo "== 4/6 开启 IP 转发 =="
sysctl -w net.inet.ip.forwarding=1 | sed 's/^/   /'

# ---------- 5. pf NAT ----------
echo "== 5/6 配置 NAT (iPhone 段 10.99.0.0/24 → $IFACE) =="
cp /etc/pf.conf /tmp/pf.conf.bak.ikev2 2>/dev/null || true
cat > /tmp/pf-ikev2.conf <<PF
set skip on lo0
nat on $IFACE from 10.99.0.0/24 to any -> ($IFACE)
PF
pfctl -f /tmp/pf-ikev2.conf 2>&1 | sed 's/^/   /'
pfctl -e 2>&1 | sed 's/^/   /' || true

# ---------- 6. 交付手机描述文件 ----------
echo "== 6/6 交付 iPhone 描述文件 =="
MC="$PROJ/ikev2/pending/iPhone-校园网VPN.mobileconfig"
if [ -f "$MC" ]; then
  DEST="$HOME/Desktop/iPhone-校园网VPN.mobileconfig"
  cp "$MC" "$DEST"
  echo "   ✅ 已放到桌面: iPhone-校园网VPN.mobileconfig"
else
  echo "   ⚠️ 未找到 pending 描述文件"
fi

echo ""
echo "=============================================="
echo "🎉 IKEv2 网关部署完成"
echo "   手机端: 见对话中的《iPhone 安装步骤》"
echo "   停止网关: sudo pkill -x charon && sudo pfctl -d"
echo "=============================================="
