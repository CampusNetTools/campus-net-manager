#!/bin/sh
# 校园网路由器工作台 - NAS(alist/rclone/tailscale) 控制 API (CGI, v5.5.0)
#
# 用途: 电脑端管家在不使用 SSH 的前提下查询 NAS 服务状态、启动/停止 NAS。
#       与 proxy-api.sh 共用同一个工作台令牌; alist/rclone 的凭据永远不出路由器。
#
# 请求: POST 正文为一行纯 ASCII JSON:
#   {"token":"<工作台令牌>","op":"status|start|stop|restart"}
# 响应: {"ok":true,...} 或 {"ok":false,"msg":"..."}
echo "Content-Type: application/json; charset=utf-8"
echo "Cache-Control: no-store"
echo ""

EXPECT=$(cat /data/other_vol/console/token 2>/dev/null)
LEN=${CONTENT_LENGTH:-0}

err() { printf '{"ok":false,"msg":"%s"}\n' "$1"; exit 0; }
field() {
  KEY="$1"
  printf '%s' "$PAYLOAD" | sed -n "s/.*\"$KEY\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -1
}

[ "$REQUEST_METHOD" = "POST" ] || err "仅允许 POST"
case "$LEN" in ''|*[!0-9]*) err "请求长度无效";; esac
[ "$LEN" -le 4096 ] || err "请求过大"
[ "$LEN" -gt 2 ] || err "请求为空"
PAYLOAD=$(dd bs=1 count="$LEN" 2>/dev/null)

[ "$(field token)" = "$EXPECT" ] || err "令牌错误"

OP=$(field op)
case "$OP" in
  status|start|stop|restart) ;;
  *) err "不支持的操作";;
esac

WATCH=/etc/crontabs/patches/nas_watch.sh
TS=/tmp/tsbin/tailscale
TSSOCK=/var/run/tailscale.sock

if [ "$OP" = "stop" ]; then
  kill $(pidof alist) 2>/dev/null
  kill $(pidof rclone) 2>/dev/null
  sleep 1
  printf '{"ok":true,"msg":"已停止 alist 与 rclone","alist":0,"rclone":0,"tailscale":-1,"web":"000","ts_ip":""}\n'
  exit 0
fi

if [ "$OP" = "start" ] || [ "$OP" = "restart" ]; then
  [ -f "$WATCH" ] || err "路由器上没有 NAS 看门狗脚本(/etc/crontabs/patches/nas_watch.sh)"
  if [ "$OP" = "restart" ]; then
    kill $(pidof alist) 2>/dev/null
    kill $(pidof rclone) 2>/dev/null
    sleep 1
  fi
  # 看门狗是幂等的: 只补缺的进程/文件, 已在跑的服务不受影响。
  sh "$WATCH" >/dev/null 2>&1 &
  printf '{"ok":true,"msg":"已触发启动(约 15-30 秒后请刷新状态)"}\n'
  exit 0
fi

# ---- op=status ----
A=0; pidof alist >/dev/null 2>&1 && A=1
R=0; pidof rclone >/dev/null 2>&1 && R=1
T=0; pidof tailscaled >/dev/null 2>&1 && T=1
WEB=$(curl -s -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:5244/api/public/settings 2>/dev/null)
TIP=""
if [ "$T" = "1" ] && [ -x "$TS" ]; then
  TIP=$("$TS" --socket="$TSSOCK" ip -4 2>/dev/null | head -1)
fi
printf '{"ok":true,"alist":%d,"rclone":%d,"tailscale":%d,"web":"%s","ts_ip":"%s"}\n' \
  "$A" "$R" "$T" "$WEB" "$TIP"
