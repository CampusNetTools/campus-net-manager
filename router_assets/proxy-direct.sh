#!/bin/sh
# Remove interception without depending on a working core/configuration.
DIR=/data/other_vol/proxy
rm -f "$DIR/transparent.enabled" "$DIR/transparent.approved" "$DIR/trial.deadline" "$DIR/trial.source"
for chain in CN_PROXY CN_DNS CN_TCP; do
  table=nat; [ "$chain" = CN_PROXY ] && table=mangle
  while iptables -t "$table" -D PREROUTING -i br-lan -j "$chain" 2>/dev/null; do :; done
  iptables -t "$table" -F "$chain" 2>/dev/null
  iptables -t "$table" -X "$chain" 2>/dev/null
done
while iptables -D FORWARD -i br-lan -j CN_QUIC 2>/dev/null; do :; done
iptables -F CN_QUIC 2>/dev/null
iptables -X CN_QUIC 2>/dev/null
for proto in udp tcp; do
  while iptables -t nat -D PREROUTING -i br-lan -p "$proto" --dport 53 -j REDIRECT --to-ports 1053 2>/dev/null; do :; done
done
while ip rule del fwmark 1 table 100 2>/dev/null; do :; done
ip route flush table 100 2>/dev/null
logger -t proxy "Transparent interception removed; LAN direct"
exit 0
