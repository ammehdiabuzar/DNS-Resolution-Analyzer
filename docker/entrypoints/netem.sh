#!/bin/bash
# Apply or clear tc netem on this router's transit interface (subnet B,
# 10.10.2.0/24). Run on BOTH routers so each direction gets half the RTT:
#   netem.sh set <one_way_delay_ms> <loss_pct>
#   netem.sh clear
#   netem.sh show
set -e
IF=$(ip -o -4 addr show | awk '$4 ~ /^10\.10\.2\./ {print $2}' | cut -d@ -f1 | head -n1)
if [ -z "$IF" ]; then echo "no interface in 10.10.2.0/24" >&2; exit 1; fi

case "$1" in
  set)
    DELAY="${2:-0}"; LOSS="${3:-0}"
    tc qdisc replace dev "$IF" root netem delay "${DELAY}ms" loss "${LOSS}%" limit 10000
    ;;
  clear)
    tc qdisc del dev "$IF" root 2>/dev/null || true
    ;;
  show) ;;
  *) echo "usage: netem.sh set <delay_ms> <loss_pct> | clear | show" >&2; exit 1 ;;
esac
echo "$(hostname) $IF: $(tc qdisc show dev "$IF" | head -n1)"
