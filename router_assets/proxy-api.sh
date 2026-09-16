#!/bin/sh
# 校园网路由器工作台 - mihomo 控制 API 转发 (CGI, v5.4.2)
#
# 用途: 让电脑端管家在不保存 mihomo 面板密钥、不使用 SSH 的前提下读取节点列表、
#       测延迟与切换节点。面板密钥由本脚本在路由器本地从 config.yaml 读取,
#       只在 127.0.0.1 内部使用, 绝不出现在响应或日志里。
#
# 请求: POST 正文为一行纯 ASCII JSON (busybox 无法安全做百分号解码, 所以节点名走 base64):
#   {"token":"<工作台令牌>","path":"<已百分号编码的 API 路径>",
#    "method":"GET|PUT","name_b64":"<节点名的 base64, 仅 PUT 需要>"}
#   path 必须是「无查询串」的路径; 以 /delay 结尾时由本脚本补上固定测速目标,
#   不接受外部 url, 避免这个端点被当成通用探测跳板。
# 响应: mihomo 原始 JSON; 出错时为 {"ok":false,"msg":"..."}
echo "Content-Type: application/json; charset=utf-8"
echo "Cache-Control: no-store"
echo ""

CONSOLE=/data/other_vol/console
DIR=/data/other_vol/proxy
EXPECT=$(cat "$CONSOLE/token" 2>/dev/null)
LEN=${CONTENT_LENGTH:-0}

err() { printf '{"ok":false,"msg":"%s"}\n' "$1"; exit 0; }
field() {
  KEY="$1"
  printf '%s' "$PAYLOAD" | sed -n "s/.*\"$KEY\"[[:space:]]*:[[:space:]]*\"\\([^\"]*\\)\".*/\\1/p" | head -1
}

[ "$REQUEST_METHOD" = "POST" ] || err "仅允许 POST"
case "$LEN" in ''|*[!0-9]*) err "请求长度无效";; esac
[ "$LEN" -le 32768 ] || err "请求过大"
[ "$LEN" -gt 2 ] || err "请求为空"
PAYLOAD=$(dd bs=1 count="$LEN" 2>/dev/null)

[ "$(field token)" = "$EXPECT" ] || err "令牌错误"

# ---- 接口白名单: 只放行管家需要的只读/选路接口, 不做任意路径转发 ----
APIPATH=$(field path)
METHOD=$(field method)
[ -n "$METHOD" ] || METHOD=GET
case "$APIPATH" in ''|*..*|*//*|*\?*|*\&*|*\ *) err "非法接口路径";; esac
case "$APIPATH" in
  version|configs|proxies|proxies/*|connections) ;;
  *) err "不允许的接口";;
esac
case "$METHOD" in GET|PUT) ;; *) err "不允许的方法";; esac

if [ "$METHOD" = "PUT" ]; then
  # 只允许切换「节点选择」这一个组。期望串与实参做同一种大小写归一后比对,
  # 只归一 a-f (hex 位), 所以 'proxies' 的 e 会被一起转成 E —— 两边一致即可。
  SEL_ENC=$(printf '%s' 'proxies/%E8%8A%82%E7%82%B9%E9%80%89%E6%8B%A9' | tr 'a-f' 'A-F')
  [ "$(printf '%s' "$APIPATH" | tr 'a-f' 'A-F')" = "$SEL_ENC" ] \
    || err "只允许切换节点选择组"
  NAME_B64=$(field name_b64)
  [ -n "$NAME_B64" ] || err "缺少节点名"
  NAME=$(printf '%s' "$NAME_B64" | base64 -d 2>/dev/null)
  [ -n "$NAME" ] || err "节点名解码失败"
  case "$NAME" in *'"'*|*\\*) err "节点名包含非法字符";; esac
fi

SECRET=$(sed -n 's/^secret: *//p' "$DIR/config.yaml" 2>/dev/null | head -1 | tr -d '"')
[ -n "$SECRET" ] || err "未找到面板密钥"

# 测速目标固定为 gstatic generate_204, 与「自动选择」组保持一致
Q=""
case "$APIPATH" in
  */delay) Q="?timeout=5000&url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204";;
esac
URL="http://127.0.0.1:9091/$APIPATH$Q"

if [ "$METHOD" = "PUT" ]; then
  curl -sS -m 25 -X PUT \
    -H "Authorization: Bearer $SECRET" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$NAME\"}" "$URL" 2>/dev/null
else
  curl -sS -m 25 -H "Authorization: Bearer $SECRET" "$URL" 2>/dev/null
fi
echo ""
