#!/bin/sh
# Run independently of the desktop/SSH; restore direct LAN when core/path fails.
DIR=/data/other_vol/proxy
LOCK=/tmp/cnm-proxy-watch
mkdir "$LOCK" 2>/dev/null || exit 0
trap 'rmdir "$LOCK" 2>/dev/null' EXIT
proxy_ok() {
  CODE=$(curl -x http://127.0.0.1:7890 -sS -m 5 -o /dev/null -w '%{http_code}' https://cp.cloudflare.com/generate_204 2>/dev/null) || return 1
  [ "$CODE" = 204 ]
}
while [ -f "$DIR/transparent.enabled" ]; do
  if ! pidof mihomo >/dev/null 2>&1; then sh "$DIR/direct.sh"; break; fi
  if [ ! -f "$DIR/transparent.approved" ]; then
    DEADLINE=$(cat "$DIR/trial.deadline" 2>/dev/null)
    case "$DEADLINE" in ''|*[!0-9]*) sh "$DIR/direct.sh"; break;; esac
    if [ "$(date +%s)" -ge "$DEADLINE" ]; then sh "$DIR/direct.sh"; break; fi
  fi
  if ! proxy_ok && ! proxy_ok; then sh "$DIR/direct.sh"; break; fi
  sleep 5
done
