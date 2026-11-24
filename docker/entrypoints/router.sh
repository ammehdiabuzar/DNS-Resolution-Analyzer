#!/bin/bash
# Entry point for the two routers. IP forwarding is enabled by the
# compose file (sysctls). Here we add the static routes.
#   router.sh r1|r2
set -e
ROLE="$1"
case "$ROLE" in
  r1)
    # R1 is attached to A (10.10.1.0/24), B (transit) and D (10.10.4.0/24).
    ip route replace 10.10.3.0/24 via 10.10.2.2
    ;;
  r2)
    # R2 is attached to B (transit) and C (10.10.3.0/24).
    ip route replace 10.10.1.0/24 via 10.10.2.1
    ip route replace 10.10.4.0/24 via 10.10.2.1
    ;;
  *)
    echo "usage: router.sh r1|r2" >&2; exit 1 ;;
esac
# Do not send ICMP redirects (all hosts already use the right gateway).
sysctl -qw net.ipv4.conf.all.send_redirects=0 || true
echo "[$ROLE] forwarding=$(cat /proc/sys/net/ipv4/ip_forward)"
ip -br addr
ip route
exec sleep infinity
