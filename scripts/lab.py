"""Host-side helpers (standard library only): talk to the lab via `docker exec`."""

from __future__ import annotations

import subprocess
import sys

ROUTERS = ("r1", "r2")


def run(cmd, check=True, quiet=False, capture=False):
    if not quiet:
        print("$ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, text=True, capture_output=capture)
    if check and r.returncode != 0:
        if capture:
            sys.stderr.write(r.stdout + r.stderr)
        raise SystemExit(f"command failed ({r.returncode}): {' '.join(cmd)}")
    return r


def dexec(container, *args, check=True, quiet=False, capture=False):
    return run(["docker", "exec", container, *args], check=check, quiet=quiet, capture=capture)


def set_netem(rtt_ms: float, loss_pct: float):
    """Half the RTT on each router's transit interface; loss on both directions."""
    for r in ROUTERS:
        if rtt_ms == 0 and loss_pct == 0:
            dexec(r, "/opt/lab/netem.sh", "clear")
        else:
            dexec(r, "/opt/lab/netem.sh", "set", f"{rtt_ms / 2:g}", f"{loss_pct:g}")


def clear_netem():
    for r in ROUTERS:
        dexec(r, "/opt/lab/netem.sh", "clear", check=False)


def flush_unbound():
    for args in (("flush_zone", "."), ("flush_infra", "all"), ("flush_requestlist",)):
        dexec("unbound", "unbound-control", "-c", "/etc/unbound-lab/unbound.conf", *args,
              quiet=True, capture=True)


def check_running():
    r = run(["docker", "ps", "--format", "{{.Names}}"], quiet=True, capture=True)
    names = set(r.stdout.split())
    missing = {"r1", "r2", "root", "tld", "auth", "unbound", "client"} - names
    if missing:
        raise SystemExit(f"lab is not running (missing: {', '.join(sorted(missing))}). "
                         "Start it with: docker compose up -d --build")
