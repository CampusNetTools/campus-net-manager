#!/bin/sh
echo "Content-Type: application/json; charset=utf-8"
echo "Cache-Control: no-store"
echo ""
CONSOLE=/data/other_vol/console
PROXY=/data/other_vol/proxy
EXPECT=$(cat "$CONSOLE/token" 2>/dev/null)
LEN=${CONTENT_LENGTH:-0}

ok()  { echo "{\"ok\":true,\"msg\":\"$1\"}"; exit 0; }
err() { echo "{\"ok\":false,\"msg\":\"$1\"}"; exit 0; }
decode() { printf '%b' "$(printf '%s' "$1" | sed 's/+/ /g; s/%/\\x/g')"; }
get() { printf '%s' "$FORM" | tr '&' '\n' | sed -n "s/^$1=//p" | head -1; }

[ "$REQUEST_METHOD" = "POST" ] || err "仅允许 POST"
case "$LEN" in ''|*[!0-9]*) err "请求长度无效";; esac
[ "$LEN" -le 8192 ] || err "请求过大"
FORM=$(dd bs=1 count="$LEN" 2>/dev/null)
OP=$(decode "$(get op)")
TOKEN=$(decode "$(get token)")
[ "$TOKEN" = "$EXPECT" ] || err "令牌错误"
LOG=$CONSOLE/keeper.log
say() { echo "$(date '+%F %T') 工作台: $*" >> "$LOG"; }

case "$OP" in
  restart_proxy) sh "$PROXY/stop.sh" >/dev/null 2>&1; sleep 1; sh "$PROXY/start.sh" >/dev/null 2>&1; say "重启代理"; ok "代理已重启";;
  enable_transparent) sh "$PROXY/trial.sh" "$REMOTE_ADDR" >/dev/null 2>&1 || err "测试启动失败，保持直连"; say "单设备透明代理测试"; ok "仅当前设备测试，120秒后自动恢复直连";;
  disable_transparent) sh "$PROXY/direct.sh" >/dev/null 2>&1; say "关闭透明代理"; ok "透明代理已关闭，恢复直连";;
  restart_vpn) /etc/init.d/xl2tpd restart >/dev/null 2>&1; /etc/init.d/ipsec restart >/dev/null 2>&1; say "重启 VPN"; ok "VPN 服务已重启";;
  relogin) sh /etc/crontabs/patches/campus-wisp.sh >/dev/null 2>&1; say "校园网重登"; ok "已触发校园网重登";;
  reconnect_relay) ifup wwan >/dev/null 2>&1; say "重连中继"; ok "已触发中继重连";;
  switch_relay)
    SSID=$(decode "$(get ssid)"); PASS=$(decode "$(get pass)"); [ -n "$SSID" ] || err "缺少 SSID"
    uci set wireless.wwan.ssid="$SSID" || err "写入 SSID 失败"
    if [ -n "$PASS" ]; then uci set wireless.wwan.key="$PASS"; uci set wireless.wwan.encryption=psk2; else uci delete wireless.wwan.key 2>/dev/null; uci set wireless.wwan.encryption=none; fi
    uci commit wireless; say "切换中继目标"; (sleep 2; wifi reload wifi1) >/dev/null 2>&1 &
    ok "中继目标已切换";;
  restart_ap) say "重启无线"; (sleep 1; wifi down; sleep 4; wifi up) >/dev/null 2>&1 &
    ok "无线正在重启";;
  restart_router) say "重启路由器"; (sleep 2; reboot) >/dev/null 2>&1 &
    ok "路由器正在重启";;
  clearlog) : > "$LOG"; ok "日志已清空";;
  rotate_node) (sleep 1; sh "$PROXY/rotate.sh" --force >/dev/null 2>&1) >/dev/null 2>&1 & say "手动轮换代理节点"; ok "正在切换到下一个可用节点(约 10 秒生效)";;
  *) err "未知操作";;
esac
