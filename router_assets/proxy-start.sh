#!/bin/sh
# Fail-open mihomo startup for Xiaomi/OpenWrt. Transparent mode is opt-in.
DIR=/data/other_vol/proxy
LOG=$DIR/mihomo.log
ENABLE=$DIR/transparent.enabled

cleanup_rules() {
  while iptables -t mangle -D PREROUTING -i br-lan -j CN_PROXY 2>/dev/null; do :; done
  iptables -t mangle -F CN_PROXY 2>/dev/null
  iptables -t mangle -X CN_PROXY 2>/dev/null
  while iptables -t nat -D PREROUTING -i br-lan -j CN_DNS 2>/dev/null; do :; done
  iptables -t nat -F CN_DNS 2>/dev/null
  iptables -t nat -X CN_DNS 2>/dev/null
  while iptables -t nat -D PREROUTING -i br-lan -j CN_TCP 2>/dev/null; do :; done
  iptables -t nat -F CN_TCP 2>/dev/null
  iptables -t nat -X CN_TCP 2>/dev/null
  while iptables -D FORWARD -i br-lan -j CN_QUIC 2>/dev/null; do :; done
  iptables -F CN_QUIC 2>/dev/null
  iptables -X CN_QUIC 2>/dev/null
  iptables -t nat -D PREROUTING -i br-lan -p udp --dport 53 -j REDIRECT --to-ports 1053 2>/dev/null
  iptables -t nat -D PREROUTING -i br-lan -p tcp --dport 53 -j REDIRECT --to-ports 1053 2>/dev/null
  ip rule del fwmark 1 table 100 2>/dev/null
  ip route flush table 100 2>/dev/null
}

alive() {
  pidof mihomo >/dev/null 2>&1 &&
    netstat -tln 2>/dev/null | grep -q ':7890 '
}

proxy_ok() {
  CODE=$(curl -x http://127.0.0.1:7890 -L -sS -m 12 -o /dev/null \
    -w '%{http_code}' https://cp.cloudflare.com/generate_204) || return 1
  [ "$CODE" = "204" ]
}

if ! "$DIR/mihomo" -t -d "$DIR" -f "$DIR/config.yaml" >/dev/null 2>&1; then
  sh "$DIR/direct.sh"
  logger -t proxy "配置校验失败，已保持直连"
  exit 1
fi

if ! alive; then
  "$DIR/mihomo" -d "$DIR" >"$LOG" 2>&1 &
  n=0
  while [ "$n" -lt 12 ] && ! alive; do n=$((n + 1)); sleep 1; done
fi
if ! alive; then
  sh "$DIR/direct.sh"
  logger -t proxy "mihomo 启动失败，已撤销透明规则"
  exit 1
fi

if [ ! -f "$ENABLE" ]; then
  cleanup_rules
  logger -t proxy "显式代理在线，透明接管保持关闭"
  echo "OK: explicit proxy only"
  exit 0
fi

# Before intercepting clients, require a working outbound proxy.
if ! proxy_ok || ! proxy_ok || ! proxy_ok; then
  sh "$DIR/direct.sh"
  logger -t proxy "节点连通测试失败，已自动关闭透明接管"
  exit 1
fi

# A stale enable flag must never re-enable an expired trial after a restart.
DEADLINE=$(cat "$DIR/trial.deadline" 2>/dev/null)
SOURCE=$(cat "$DIR/trial.source" 2>/dev/null)
if [ ! -f "$DIR/transparent.approved" ]; then
  case "$DEADLINE" in ''|*[!0-9]*) sh "$DIR/direct.sh"; exit 1;; esac
  [ "$(date +%s)" -lt "$DEADLINE" ] || { sh "$DIR/direct.sh"; exit 1; }
fi
case "$SOURCE" in 192.168.31.*) ;; *) sh "$DIR/direct.sh"; exit 1;; esac

cleanup_rules
fail() { sh "$DIR/direct.sh"; exit 1; }
netstat -tln 2>/dev/null | grep -q ':7892 ' || fail
iptables -t nat -N CN_TCP || fail
iptables -t nat -A CN_TCP ! -s "$SOURCE" -j RETURN || fail
iptables -t nat -A CN_TCP -p tcp --dport 53 -j RETURN || fail
for n in 0.0.0.0/8 10.0.0.0/8 100.64.0.0/10 127.0.0.0/8 169.254.0.0/16 172.16.0.0/12 192.168.0.0/16 224.0.0.0/4 240.0.0.0/4; do
  iptables -t nat -A CN_TCP -d "$n" -j RETURN || fail
done
iptables -t nat -A CN_TCP -p tcp -j REDIRECT --to-ports 7892 || fail
iptables -t nat -N CN_DNS || fail
iptables -t nat -A CN_DNS -s "$SOURCE" -p udp --dport 53 -j REDIRECT --to-ports 1053 || fail
iptables -t nat -A CN_DNS -s "$SOURCE" -p tcp --dport 53 -j REDIRECT --to-ports 1053 || fail
iptables -t nat -A PREROUTING -i br-lan -j CN_DNS || fail
iptables -t nat -A PREROUTING -i br-lan -j CN_TCP || fail
# Browsers fall back from QUIC to HTTPS/TCP. Other UDP stays on direct routing.
iptables -N CN_QUIC || fail
iptables -A CN_QUIC -s "$SOURCE" -p udp --dport 443 -j REJECT --reject-with icmp-port-unreachable || fail
iptables -I FORWARD 1 -i br-lan -j CN_QUIC || fail
logger -t proxy "透明代理已启用（fail-open）"
sh "$DIR/watch.sh" >/dev/null 2>&1 </dev/null &
echo "OK: transparent proxy enabled"
