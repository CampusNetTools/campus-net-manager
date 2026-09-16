#!/bin/sh
DIR=/data/other_vol/proxy
sh "$DIR/direct.sh"
iptables -t mangle -D PREROUTING -i br-lan -j CN_PROXY 2>/dev/null
iptables -t mangle -F CN_PROXY 2>/dev/null
iptables -t mangle -X CN_PROXY 2>/dev/null
iptables -t nat -D PREROUTING -i br-lan -p udp --dport 53 -j REDIRECT --to-ports 1053 2>/dev/null
iptables -t nat -D PREROUTING -i br-lan -p tcp --dport 53 -j REDIRECT --to-ports 1053 2>/dev/null
ip rule del fwmark 1 table 100 2>/dev/null
ip route flush table 100 2>/dev/null
for pid in $(pidof mihomo 2>/dev/null); do kill "$pid" 2>/dev/null; done
exit 0
