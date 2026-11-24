"""Correctness check: our iterative resolver vs dig +trace.

For every test name the answer set from our resolver must equal the answer
set that `dig @10.10.1.10 <name> +trace` gets from the authoritative server.

    python3 experiments/verify.py
"""

from __future__ import annotations

import subprocess
import sys

from common import ROOT_IP
from dnsresolver import IterativeResolver

CASES = [("www.example.lab", "A"), ("mail.example.lab", "A"), ("example.lab", "MX"),
         ("www.noglue.lab", "A"), ("web.example.lab", "A"), ("big.example.lab", "TXT"),
         ("example.lab", "NS")]


def dig_trace(name: str, qtype: str) -> set:
    out = subprocess.run(["dig", f"@{ROOT_IP}", name, qtype, "+trace", "+nodnssec"],
                         capture_output=True, text=True).stdout
    records = set()
    for line in out.splitlines():
        parts = line.split(None, 4)
        if not line.startswith(";") and len(parts) == 5 and parts[2] == "IN":
            records.add((parts[0].lower(), parts[3], parts[4].strip().lower()))
    # Follow the CNAME chain from the asked name, then keep records of qtype.
    owners, cur = {name.lower() + "."}, name.lower() + "."
    for _ in range(8):
        nxt = next((v for o, t, v in records if o == cur and t == "CNAME"), None)
        if not nxt:
            break
        owners.add(nxt)
        cur = nxt
    return {(o, v) for o, t, v in records if t == qtype and o in owners}


def ours(name: str, qtype: str) -> set:
    res = IterativeResolver(roots=[("a.root-servers.lab.", ROOT_IP)]).resolve(name, qtype)
    return {(rr.name, rr.value_text().lower()) for rr in res.answers if rr.type_text == qtype}


def main() -> int:
    bad = 0
    for name, qtype in CASES:
        a, b = ours(name, qtype), dig_trace(name, qtype)
        ok = bool(a) and a == b
        bad += not ok
        print(f"{'MATCH' if ok else 'DIFF '}  {name:18} {qtype:4}  ours={sorted(v for _, v in a)}"
              + ("" if ok else f"  dig={sorted(v for _, v in b)}"))
    print(f"\n{len(CASES) - bad}/{len(CASES)} names match dig +trace")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
