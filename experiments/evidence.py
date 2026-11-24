"""Record one evidence capture (.pcapng) per key protocol exchange.

Runs in the client container; scripts/capture_evidence.py calls it once per
scenario (and handles netem and the capture on the Unbound side).

    python3 experiments/evidence.py <scenario>
Scenarios: icmp, iterative, noglue, tcp_fallback, recursive_do53, dot, doh, loss
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from common import LAB, ROOT_IP, TRANSPORT_NAME, Capture, inject_secrets
from dnsresolver import IterativeResolver, format_step
from transports import DoH, DoT, Do53, QueryFailed

OUT = os.path.join(LAB, "captures", "evidence")
KEYS = os.path.join(OUT, "keys")


def sh(cmd):
    print("$ " + " ".join(cmd), flush=True)
    subprocess.run(cmd)


def resolve(name, qtype="A"):
    r = IterativeResolver(roots=[("a.root-servers.lab.", ROOT_IP)],
                          on_step=lambda s: print(format_step(s), flush=True),
                          on_event=lambda d, t: print("    " * d + "     -> " + t, flush=True))
    res = r.resolve(name, qtype)
    print(f"{res.rcode} {res.addresses()} queries={res.queries} total={res.total_ms:.1f} ms", flush=True)


def transport_session(cls, keylog, repeats=3):
    t = cls(keylog=keylog)
    print(f"{t.name}: first query {t.first_query(TRANSPORT_NAME):.1f} ms (new connection)", flush=True)
    time.sleep(0.3)
    t.open()
    try:
        for i in range(repeats + 1):
            ms = t.query_open(TRANSPORT_NAME)
            print(f"{t.name}: query {i} on open connection {ms:.1f} ms", flush=True)
    finally:
        t.close()


SCENARIOS = {
    "icmp": ("01_icmp_ping_traceroute", lambda k: (
        sh(["ping", "-c", "3", "10.10.1.10"]),
        sh(["traceroute", "-n", "-q", "1", "-w", "2", "10.10.1.10"]))),
    "iterative": ("02_iterative_do53_udp", lambda k: resolve("www.example.lab")),
    "noglue": ("03_missing_glue_sublookup", lambda k: resolve("www.noglue.lab")),
    "tcp_fallback": ("04_truncation_tcp53_fallback", lambda k: resolve("big.example.lab", "TXT")),
    "recursive_do53": ("05_recursive_do53_client_unbound", lambda k: transport_session(Do53, k)),
    "dot": ("06_dot_tls13_port853", lambda k: transport_session(DoT, k)),
    "doh": ("07_doh_tls13_http2_port443", lambda k: transport_session(DoH, k)),
    "loss": ("08_loss_udp_retry_vs_tcp_retransmit", lambda k: (
        [resolve("www.example.lab") for _ in range(3)],
        [transport_session(Do53, k, 5), transport_session(DoT, k, 5)])),
}


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in SCENARIOS:
        print(__doc__)
        sys.exit(2)
    base, action = SCENARIOS[sys.argv[1]]
    os.makedirs(KEYS, exist_ok=True)
    pcap = os.path.join(OUT, base + ".pcapng")
    keylog = os.path.join(KEYS, base + ".keys")
    if os.path.exists(keylog):
        os.remove(keylog)
    print(f"=== {base} ===", flush=True)
    with Capture(pcap):
        try:
            action(keylog)
        except (OSError, QueryFailed) as exc:
            print(f"error during scenario: {exc}", flush=True)
    if os.path.exists(keylog) and os.path.getsize(keylog) > 0:
        dec = os.path.join(OUT, base + "_with_keys.pcapng")
        if inject_secrets(pcap, keylog, dec):
            print(f"decryptable copy (TLS keys embedded): {dec}", flush=True)
    print(f"saved {pcap}", flush=True)


if __name__ == "__main__":
    main()
