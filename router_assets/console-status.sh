#!/bin/sh
# 校园网路由器工作台 - 状态接口 (CGI)
# 输出: JSON
echo "Content-Type: application/json; charset=utf-8"
echo "Cache-Control: no-store"
echo ""

BASE=/data/other_vol
CONSOLE=$BASE/console

# ---------- 中继 ----------
RSSID=$(iwinfo wl12 info 2>/dev/null | awk -F'"' '/ESSID/{print $2; exit}')
RSIG=$(iwinfo wl12 info 2>/dev/null | awk '/Signal/{print $2; exit}')
RBSSID=$(iwinfo wl12 info 2>/dev/null | awk '/Access Point/{print $3; exit}')
RIP=$(ifconfig wl12 2>/dev/null | awk '/inet addr/{print $2}' | cut -d: -f2 | head -1)
[ -z "$RIP" ] && RIP="(无IP)"

# ---------- AP ----------
ASSID=$(iwinfo wl1 info 2>/dev/null | awk -F'"' '/ESSID/{print $2; exit}')
ACH=$(iwinfo wl1 info 2>/dev/null | awk '/Channel/{print $4; exit}')
A24=$(iwinfo wl1 info 2>/dev/null | grep -c "Mode: Master")

# ---------- 校园网认证 ----------
AUTH="未知"
if wget -q -T 5 -O /tmp/cg_auth http://192.168.16.3/ 2>/dev/null; then
    if grep -qi "logout" /tmp/cg_auth 2>/dev/null; then AUTH="已登录在线"; else AUTH="未登录"; fi
else
    AUTH="认证服务器不可达"
fi
rm -f /tmp/cg_auth

# ---------- 外网 ----------
NET=$(curl -s -o /dev/null -w "%{http_code}" -m 6 http://www.baidu.com/ 2>/dev/null)
[ "$NET" = "200" ] && NETOK="正常" || NETOK="异常($NET)"

# ---------- 服务 ----------
PC=$(pgrep -f "other_vol/proxy/mihomo" 2>/dev/null | wc -l)
PORT1=$(netstat -tln 2>/dev/null | grep -c ":7890 ")
PORT2=$(netstat -tln 2>/dev/null | grep -c ":7891 ")
PORT3=$(netstat -tln 2>/dev/null | grep -c ":9091 ")
PORT4=$(netstat -tln 2>/dev/null | grep -c ":7892 ")
TRANSPARENT=0; [ -f "$BASE/proxy/transparent.enabled" ] && TRANSPARENT=1
VC=$(pgrep -x xl2tpd 2>/dev/null | wc -l)
IC=0; [ -n "$(pgrep -f 'pluto' 2>/dev/null)" ] && IC=1
V500=0; [ -n "$(netstat -uln 2>/dev/null | grep ':500 ')" ] && V500=1
SSHD=$(ps w 2>/dev/null | grep -c "[d]ropbear")
HTTPD=0; [ -n "$(pgrep -f 'uhttpd -p 8088' 2>/dev/null)" ] && HTTPD=1

# ---------- 代理节点信息 ----------
if grep -qE "^proxies: *\[\]" $BASE/proxy/config.yaml 2>/dev/null; then
    NODES_DESC="未配置节点(仅直连)"
else
    NODE_COUNT=$(awk '/^proxies:/{inside=1; next} /^proxy-groups:/{inside=0} inside && /^  - name:/{count++} END{print count+0}' "$BASE/proxy/config.yaml" 2>/dev/null)
    NODES_DESC="已配置 $NODE_COUNT 个节点"
fi

# ---------- 系统 ----------
UP=$(uptime | awk -F'up' '{print $2}' | cut -d, -f1 | sed 's/^ *//')
LOAD=$(uptime | awk -F'load average:' '{print $2}' | sed 's/^ *//')
MU=$(free | awk '/Mem/{print $3}')
MT=$(free | awk '/Mem/{print $2}')
MODEL=$(cat /proc/xiaoqiang/model 2>/dev/null || echo "RD08")
ROM=$(grep -o "1\.[0-9.]*" /usr/share/xiaoqiang/xiaoqiang_version 2>/dev/null | head -1)

# ---------- 防护开关 ----------
OTA=$(uci get misc.ota_pred.download 2>/dev/null); [ -z "$OTA" ] && OTA="?"
MLO=$(uci get misc.features.mlo_support 2>/dev/null); [ -z "$MLO" ] && MLO="?"
MLO2=$(uci get wireless.hostap_mld0.mlo_enable 2>/dev/null); [ -z "$MLO2" ] && MLO2="-"

# ---------- 最近日志 ----------
LOGTXT=$(tail -30 "$CONSOLE/keeper.log" 2>/dev/null | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/ /g' | tr '\n' '~')

RLOG=$(tail -3 "$BASE/proxy/rotate.log" 2>/dev/null | sed 's/\\/\\\\/g; s/"/\\"/g; s/\t/ /g' | tr '\n' '~')

cat <<EOF
{
  "relay": {"ssid":"$RSSID","signal":"$RSIG","bssid":"$RBSSID","ip":"$RIP"},
  "ap": {"ssid":"$ASSID","channel":"$ACH","up":"$A24"},
  "auth": "$AUTH",
  "net": "$NETOK",
  "proxy": {"rotate":"$RLOG","proc":"$PC","p7890":"$PORT1","p7891":"$PORT2","p7892":"$PORT4","panel":"$PORT3","transparent":"$TRANSPARENT","nodes":"$NODES_DESC"},
  "vpn": {"xl2tpd":"$VC","ipsec":"$IC","udp500":"$V500"},
  "ssh": {"dropbear":"$SSHD"},
  "console": {"httpd":"$HTTPD"},
  "sys": {"model":"$MODEL","rom":"$ROM","uptime":"$UP","load":"$LOAD","mem_used":"$MU","mem_total":"$MT"},
  "guard": {"ota_auto":"$OTA","mlo_support":"$MLO","mlo_enable":"$MLO2"},
  "log": "$LOGTXT"
}
EOF
