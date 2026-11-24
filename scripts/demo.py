"""Live POC demo, one step at a time (press Enter between steps).

    python scripts/demo.py            # interactive
    python scripts/demo.py --no-pause # run straight through
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from lab import check_running, clear_netem, dexec, set_netem  # noqa: E402

PAUSE = True


def title(text):
    print("\n" + "=" * 78 + f"\n  {text}\n" + "=" * 78, flush=True)
    if PAUSE:
        input("  [Enter] to run ")


def main():
    global PAUSE
    p = argparse.ArgumentParser()
    p.add_argument("--no-pause", action="store_true")
    PAUSE = not p.parse_args().no_pause
    check_running()
    clear_netem()

    title("1. Topology: routing tables on R1 and R2, traceroute client -> root")
    dexec("r1", "ip", "route")
    dexec("r2", "ip", "route")
    dexec("client", "traceroute", "-n", "-q", "1", "10.10.1.10", check=False)

    title("2. Iterative resolution of www.example.lab with our raw-packet resolver")
    dexec("client", "python3", "-m", "dnsresolver", "www.example.lab", check=False)

    title("3. Correctness: dig +trace, then our resolver vs dig for every test name")
    dexec("client", "dig", "@10.10.1.10", "www.example.lab", "+trace", "+nodnssec", check=False)
    dexec("client", "python3", "experiments/verify.py", check=False)

    title("4. Missing glue: www.noglue.lab needs a sub-lookup of ns.example.lab")
    dexec("client", "python3", "-m", "dnsresolver", "www.noglue.lab", check=False)

    title("5. Truncation: big.example.lab TXT is > 512 bytes -> TC=1 -> retry over TCP 53")
    dexec("client", "python3", "-m", "dnsresolver", "big.example.lab", "--type", "TXT", check=False)

    title("6. Do53 vs DoT vs DoH through Unbound (no impairment)")
    dexec("client", "python3", "experiments/compare.py", check=False)

    title("7. Impairment: 200 ms RTT on the R1-R2 link, same tests again")
    set_netem(200, 0)
    try:
        dexec("client", "python3", "-m", "dnsresolver", "www.noglue.lab", check=False)
        dexec("client", "python3", "experiments/compare.py", check=False)
    finally:
        clear_netem()

    print("\nDemo finished. For Wireshark: open captures/evidence/*_with_keys.pcapng "
          "(TLS keys embedded) to see the DNS inside DoT and DoH.")


if __name__ == "__main__":
    main()
