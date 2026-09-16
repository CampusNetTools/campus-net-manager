#!/bin/sh
# 代理节点轮换看门狗 (v5.4.2)
#
# 由 crontab 每 2 分钟调用一次: 显式代理连续失败时, 并行测出**全部**候选节点的
# 真实延迟, 挑延迟最低的那个切过去, 再做一次真实连通复验。
# 半失效的隧道 (能握手但过不了流量) 在这里被兜住 —— 这正是「节点用久即被阻断」
# 的网络环境下最有效的自愈手段。
#
# 两个刻意的设计取舍:
#  1) 测延迟只打 mihomo 的 /proxies/<name>/delay, **先不切当前选择**。旧实现是
#     逐个 select 再 probe, 一次轮换会在十几秒里把用户的连接改道最多 6 次;
#     现在全测完只切一次, 对正在下载/开会的连接干扰最小。
#  2) 只按「能通」落位是不够的: 订阅里常有一批能握手但吞吐极差的节点
#     (实测同一时刻 1279ms 与 212ms 并存), 随手挑一个会把用户钉在慢速线路上,
#     所以必须比过延迟再落位。老实现只看配置顺序上的 6 个, 覆盖面也太窄。
#
# 只操作 mihomo 控制 API 的「节点选择」, 不碰 iptables / 透明代理 / 中继 / 中继认证。
# 用法: sh rotate.sh [--force]   (--force: 跳过健康检查, 立刻择优切换)
DIR=/data/other_vol/proxy
LOG=$DIR/rotate.log
STATE=$DIR/rotate.state
LOCK=$DIR/rotate.lock
WORK=$DIR/rotate.work
API=http://127.0.0.1:9091
SEL_ENC='%E8%8A%82%E7%82%B9%E9%80%89%E6%8B%A9'
TESTQ='timeout=5000&url=https%3A%2F%2Fwww.gstatic.com%2Fgenerate_204'
BATCH=8          # 并行测延迟的并发数
VERIFY_TRY=3     # 延迟达标后, 最多实测复验几个节点
LOCK_TTL=300
FORCE=0
[ "$1" = "--force" ] && FORCE=1

log() {
  echo "$(date '+%F %T') $*" >> "$LOG"
  if [ "$(wc -l < "$LOG" 2>/dev/null)" -gt 300 ]; then
    tail -200 "$LOG" > "$LOG.tmp" 2>/dev/null && mv "$LOG.tmp" "$LOG"
  fi
}

# 单实例锁: 一次全量测速可能跑十几到几十秒, 与 2 分钟的 cron 周期可能重叠。
# 用「目录 + 时间戳文件」而不是 find -mmin —— 这台路由器的 busybox find 没有
# -mmin/-mtime, 依赖它会导致陈旧锁永远清不掉, 一次崩溃就把看门狗永久锁死。
acquire_lock() {
  mkdir "$LOCK" 2>/dev/null || return 1
  date +%s > "$LOCK/ts" 2>/dev/null
  return 0
}
if ! acquire_lock; then
  HELD=$(cat "$LOCK/ts" 2>/dev/null)
  case "$HELD" in ''|*[!0-9]*) HELD=0;; esac
  NOW_SEEN=$(date +%s)
  if [ "$HELD" = "0" ] || [ $((NOW_SEEN - HELD)) -gt "$LOCK_TTL" ]; then
    rm -rf "$LOCK" 2>/dev/null
    acquire_lock || exit 0
  else
    exit 0
  fi
fi
trap '[ -n "$LOCK" ] && rm -rf "$LOCK" "$WORK" 2>/dev/null' EXIT INT TERM HUP

pidof mihomo >/dev/null 2>&1 || exit 0
SECRET=$(sed -n 's/^secret: *//p' "$DIR/config.yaml" 2>/dev/null | head -1 | tr -d '"')
[ -n "$SECRET" ] || exit 0

probe() {
  C=$(curl -x http://127.0.0.1:7890 -L -sS -m 6 -o /dev/null \
      -w '%{http_code}' https://www.gstatic.com/generate_204 2>/dev/null)
  [ "$C" = "204" ]
}

api_get() { curl -sS -m 12 -H "Authorization: Bearer $SECRET" "$API$1" 2>/dev/null; }

select_node() {
  curl -sS -m 12 -X PUT -H "Authorization: Bearer $SECRET" \
    -H "Content-Type: application/json" \
    -d "{\"name\":\"$1\"}" "$API/proxies/$SEL_ENC" >/dev/null 2>&1
}

# 节点名 -> 百分号编码。busybox 没有 od, 用 hexdump 逐字节输出十六进制。
pct() { printf '%s' "$1" | hexdump -v -e '/1 "%02x"' | sed 's/../%&/g'; }

# 让 mihomo 直接测这个节点自己的延迟(毫秒); 失败/超时返回空。
node_delay() {
  R=$(curl -sS -m 8 -H "Authorization: Bearer $SECRET" \
      "$API/proxies/$(pct "$1")/delay?$TESTQ" 2>/dev/null)
  D=$(printf '%s' "$R" | sed -n 's/.*"delay":[[:space:]]*\([0-9]*\).*/\1/p' | head -1)
  case "$D" in ''|*[!0-9]*) return 1;; esac
  [ "$D" -gt 0 ] 2>/dev/null || return 1
  printf '%s' "$D"
}

# 候选节点: config.yaml 里所有非 hysteria2 节点 (校园网封 UDP, hy2 必然不可用),
# 并剔除订阅里夹带的信息行 (剩余流量 / 套餐到期 之类, 不是真节点)。
#
# 注意 type 的值在生成出来时是带引号的 ('type: "vless"', 生成器统一用 JSON
# 字符串语法), 必须像 name 一样先剥掉引号再比较 —— 否则 "hysteria2" != hysteria2,
# 剔除逻辑静默失效 (实测踩到: 候选数 69 而非 52, 白白多测 17 个 hy2)。
candidates() {
  awk '
    /^proxies:[[:space:]]*$/ { inp = 1; next }
    /^proxy-groups:/ { inp = 0 }
    inp && /^  - name:/ {
      if (name != "" && type != "hysteria2") print name
      name = $0
      sub(/^  - name:[[:space:]]*/, "", name)
      gsub(/^"|"$/, "", name)
      type = ""
      next
    }
    inp && /^    type:/ {
      t = $0
      sub(/^    type:[[:space:]]*/, "", t)
      gsub(/^"|"$/, "", t)
      type = t
    }
    END { if (name != "" && type != "hysteria2") print name }
  ' "$DIR/config.yaml" 2>/dev/null | grep -vE '剩余流量|重置剩余|套餐到期|过期时间|官网|订阅'
}

TOTAL=$(candidates | wc -l)
[ "$TOTAL" -gt 0 ] 2>/dev/null || exit 0

NOW=$(api_get "/proxies/$SEL_ENC" | sed -n 's/.*"now":"\([^"]*\)".*/\1/p')

if [ "$FORCE" = "0" ]; then
  if probe || probe; then
    exit 0
  fi
  log "显式代理连续失败, 开始轮换 (当前: ${NOW:-未知})"
else
  log "手动轮换请求 (当前: ${NOW:-未知})"
fi

rm -rf "$WORK"
mkdir -p "$WORK" 2>/dev/null || exit 0
candidates | awk '{printf "%d\t%s\n", NR, $0}' > "$WORK/list"
ALL=$(wc -l < "$WORK/list" 2>/dev/null)
case "$ALL" in ''|*[!0-9]*) ALL=0;; esac
[ "$ALL" -gt 0 ] || exit 0

# ---- 第一步: 并行测全部候选的延迟, 全程不改当前选择 ----
# 用显式递增的 NEXT 而不是「批次偏移 K」: 之前从 0 起算时依赖 sed -n "0p",
# 而 busybox 的 sed 会把 0p 当成第 1 行(GNU sed 则输出空), 导致首个节点被
# 重复测一次 —— 不但浪费一次往返, 行为还随 sed 实现漂移。
NEXT=1
while [ "$NEXT" -le "$ALL" ]; do
  K=0
  while [ "$K" -lt "$BATCH" ] && [ "$NEXT" -le "$ALL" ]; do
    IDX=$NEXT
    NEXT=$((NEXT + 1))
    K=$((K + 1))
    LINE=$(sed -n "${IDX}p" "$WORK/list" 2>/dev/null)
    [ -n "$LINE" ] || continue
    NAME=$(printf '%s' "$LINE" | cut -f2-)
    case "$NAME" in *'"'*) continue;; esac
    (
      D=$(node_delay "$NAME")
      [ -n "$D" ] && printf '%s\t%s\n' "$D" "$NAME" > "$WORK/r$(printf '%03d' "$IDX")"
    ) &
  done
  wait
done

MEASURED=$(cat "$WORK"/r[0-9]* 2>/dev/null | wc -l)
case "$MEASURED" in ''|*[!0-9]*) MEASURED=0;; esac

# ---- 第二步: 按延迟升序, 实测复验后落位 ----
RANKED=$(cat "$WORK"/r[0-9]* 2>/dev/null | sort -n)

OK_NAME=""
OK_DELAY=""
VERIFIED=0
while [ "$VERIFIED" -lt "$VERIFY_TRY" ]; do
  LINE=$(printf '%s\n' "$RANKED" | sed -n "$((VERIFIED + 1))p")
  [ -n "$LINE" ] || break
  VERIFIED=$((VERIFIED + 1))
  D=$(printf '%s' "$LINE" | cut -f1)
  NAME=$(printf '%s' "$LINE" | cut -f2-)
  [ -n "$NAME" ] || continue
  select_node "$NAME"
  sleep 1
  if probe; then
    OK_NAME="$NAME"
    OK_DELAY="$D"
    break
  fi
  log "延迟测量通过但实测不通, 换下一个: $NAME (${D}ms)"
done

if [ -n "$OK_NAME" ]; then
  echo "$(date +%s) $MEASURED" > "$STATE" 2>/dev/null
  log "轮换成功 -> $OK_NAME (${OK_DELAY}ms; 候选 $ALL 个, 测出延迟 $MEASURED 个, 实测 $VERIFIED 个)"
  exit 0
fi

if [ -n "$NOW" ]; then
  select_node "$NOW"
fi
log "候选节点均不可用 (测出延迟 $MEASURED 个, 实测 $VERIFIED 个均不通), 已还原为 ${NOW:-未知} (建议更新订阅或更换机场)"
exit 1
