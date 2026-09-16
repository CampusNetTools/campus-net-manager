# RD08 direct routing and TCP transparent proxy repair

## Verified state

The user confirmed ordinary Xiaomi Internet access was restored. Campus WLAN on
the Windows PC stayed connected throughout this repair; management and explicitly
bound probes used Ethernet. No firmware flash, reboot, or default-route change
was performed.

The old TPROXY implementation reproduced SYN retries/timeouts even for domestic
destinations: its rule counters increased but the corresponding connections did
not reach mihomo. The precise firmware/kernel mechanism remains undetermined.
The previous claim that upstream HTTP 503 alone explained the incident was too
strong.

The replacement uses NAT REDIRECT to mihomo TCP port 7892. Live `/connections`
records showed Baidu inbound `Redir`, rule `GeoIP`, chain `DIRECT`; Cloudflare
inbound `Redir`, rule `Match`, proxy chain. Four repeated rounds returned Baidu
200 and Cloudflare 204. Additional Google connectivity, GitHub, and Microsoft
checks returned 204/200/200. Tencent's homepage returned 501 with and without
interception and is not counted as a passing website check.

DNS now uses `redir-host` real addresses, with TLS/HTTP sniffing. This avoids new
Fake-IP cache entries that become unreachable when interception is removed.
Windows' separate VPN blocks this PC's ordinary DNS port; router DNS was verified
using a temporary source-restricted alternate port forwarding to the same DNS
service. That temporary rule was automatically removed.

## Recovery

The router-local scripts are in `/data/other_vol/proxy`:

- `direct.sh`: immediately removes TCP/DNS/QUIC interception and approval state,
  without requiring a valid mihomo configuration or a working proxy process.
- `trial.sh <LAN IPv4>`: source-restricted 120-second trial; a detached router timer
  restores direct routing independently of SSH or the desktop.
- `watch.sh`: checks the process and real HTTP 204 transfers; consecutive failures
  restore direct routing. A deliberate process stall was detected and reverted in
  approximately 11 seconds.
- `guard.sh`: cron backup to restart the watcher/core or repair missing rules.

At handoff, validated interception covers `192.168.31.0/24`, with the approval
flag and watchdog present. A failure clears approval and leaves direct routing;
it does not automatically keep retrying global interception. The workbench's
enable action starts only a 120-second trial for the requesting device.

## Limits

This is IPv4 TCP web proxying, not all-protocol tunneling. UDP 443 is rejected to
encourage browser QUIC fallback to TCP; other UDP is direct. Domestic classification
uses `.cn` plus the installed China GeoIP database, which is not perfect. The
tests establish current operation and recovery behavior, not indefinite node
availability. No power-cycle test was performed, as requested.

Original router config/start/guard backups use `*.pre-repair.*`. Windows source
and the local executable were updated to v5.4.1 so future subscription imports
generate real-address DNS and the correct TCP listener. No remote release was
published. Secrets are omitted from this document.
