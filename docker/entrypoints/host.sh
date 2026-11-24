#!/bin/bash
# Entry point for end hosts: replace Docker's default route with the
# subnet's router, then run the service command.
#   host.sh <gateway-ip> <command> [args...]
set -e
GW="$1"; shift
ip route replace default via "$GW"
echo "[$(hostname)] default route via $GW"
ip route
exec "$@"
