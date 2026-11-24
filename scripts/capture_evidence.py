"""Record the evidence captures for every key protocol exchange.

    python scripts/capture_evidence.py

Writes to captures/evidence/:
  01_icmp_ping_traceroute.pcapng            ICMP echo + traceroute through R2 and R1
  02_iterative_do53_udp.pcapng              our resolver: root -> .lab -> example.lab (UDP 53)
  03_missing_glue_sublookup.pcapng          referral without glue -> extra NS sub-lookup
  04_truncation_tcp53_fallback.pcapng       TC=1 over UDP, retry over TCP 53
  05_recursive_do53_client_unbound.pcapng   client <-> Unbound, plaintext Do53
  05b_unbound_upstream_recursion.pcapng     captured on Unbound: its own iterative queries
  06_dot_tls13_port853.pcapng (+ _with_keys) DoT; the _with_keys copy embeds TLS secrets
  07_doh_tls13_http2_port443.pcapng (+ _with_keys)
  08_loss_udp_retry_vs_tcp_retransmit.pcapng  20 % loss: UDP retries vs TCP retransmissions
"""

from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from lab import check_running, clear_netem, dexec, flush_unbound, run, set_netem  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def scenario(name):
    dexec("client", "python3", "experiments/evidence.py", name)


def main():
    check_running()
    clear_netem()
    try:
        for name in ("icmp", "iterative", "noglue", "tcp_fallback"):
            scenario(name)

        # Recursive Do53, also captured on the Unbound side with a cold cache.
        flush_unbound()
        dexec("unbound", "sh", "-c", "rm -f /tmp/upstream.pcapng; "
              "dumpcap -q -i eth0 -w /tmp/upstream.pcapng >/dev/null 2>&1 &")
        time.sleep(2)
        scenario("recursive_do53")
        time.sleep(1)
        dexec("unbound", "pkill", "-INT", "dumpcap", check=False)
        time.sleep(1)
        os.makedirs(os.path.join(ROOT, "captures", "evidence"), exist_ok=True)
        run(["docker", "cp", "unbound:/tmp/upstream.pcapng",
             os.path.join(ROOT, "captures", "evidence", "05b_unbound_upstream_recursion.pcapng")])

        scenario("dot")
        scenario("doh")

        # Heavy loss only for this illustration, so retries certainly appear.
        set_netem(20, 20)
        scenario("loss")
    finally:
        clear_netem()


if __name__ == "__main__":
    main()
