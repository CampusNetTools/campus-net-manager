#!/bin/sh
DIR=/data/other_vol/proxy
if [ -f "$DIR/transparent.enabled" ] && [ ! -f "$DIR/transparent.approved" ]; then
  DEADLINE=$(cat "$DIR/trial.deadline" 2>/dev/null)
  case "$DEADLINE" in ''|*[!0-9]*) sh "$DIR/direct.sh"; exit 0;; esac
  [ "$(date +%s)" -lt "$DEADLINE" ] || { sh "$DIR/direct.sh"; exit 0; }
fi
if [ -f "$DIR/transparent.enabled" ]; then
  sh "$DIR/watch.sh" >/dev/null 2>&1 </dev/null &
fi
proxy_ok() {
  CODE=$(curl -x http://127.0.0.1:7890 -L -sS -m 10 -o /dev/null \
    -w '%{http_code}' https://cp.cloudflare.com/generate_204) || return 1
  [ "$CODE" = "204" ]
}
if ! pidof mihomo >/dev/null 2>&1 || ! netstat -tln 2>/dev/null | grep -q ':7890 '; then
  logger -t proxy "守护：mihomo 不在线，按 fail-open 模式重启"
  sh "$DIR/start.sh"
elif [ -f "$DIR/transparent.enabled" ] && ! iptables -t nat -S PREROUTING 2>/dev/null | grep -q CN_TCP; then
  logger -t proxy "守护：透明规则缺失，重新校验后加载"
  sh "$DIR/start.sh"
elif [ -f "$DIR/transparent.enabled" ]; then
  # 两次真实传输都失败时立即 fail-open，避免坏节点让整个 LAN 长时间断网。
  if ! proxy_ok && ! proxy_ok; then
    logger -t proxy "守护：节点连续失败，自动关闭透明接管并恢复直连"
    sh "$DIR/direct.sh"
  fi
fi
