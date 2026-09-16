#!/bin/sh
# Every activation is a time-limited, single-client trial until separately verified.
DIR=/data/other_vol/proxy
SOURCE=$1
case "$SOURCE" in
  192.168.31.0/24) ;;
  192.168.31.*)
    LAST=${SOURCE##*.}
    case "$LAST" in ''|*[!0-9]*) exit 1;; esac
    [ "$LAST" -ge 2 ] && [ "$LAST" -le 254 ] || exit 1;;
  *) echo 'LAN source required'; exit 1;;
esac
sh "$DIR/direct.sh"
DEADLINE=$(($(date +%s) + 120))
printf '%s\n' "$SOURCE" > "$DIR/trial.source"
printf '%s\n' "$DEADLINE" > "$DIR/trial.deadline"
touch "$DIR/transparent.enabled"
# Independent from SSH, the GUI, the proxy core, and its network health.
(sleep 120; [ "$(cat "$DIR/trial.deadline" 2>/dev/null)" = "$DEADLINE" ] && sh "$DIR/direct.sh") >/dev/null 2>&1 </dev/null &
sh "$DIR/start.sh" || { sh "$DIR/direct.sh"; exit 1; }
echo "Trial active for $SOURCE; automatic rollback in 120 seconds"
