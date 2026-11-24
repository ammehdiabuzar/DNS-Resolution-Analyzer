"""Command-line interface.

    python3 -m dnsresolver www.example.lab
    python3 -m dnsresolver mail.example.lab --type MX
    python3 -m dnsresolver www.noglue.lab --json
"""

import argparse
import json
import sys

from .resolver import IterativeResolver, format_step


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="dnsresolver", description="Iterative DNS resolver (raw packets)")
    p.add_argument("name")
    p.add_argument("--type", "-t", default="A", help="record type (A, NS, MX, TXT, CNAME, SOA, AAAA)")
    p.add_argument("--root", default="10.10.1.10", help="root server IP (default 10.10.1.10)")
    p.add_argument("--root-name", default="a.root-servers.lab.")
    p.add_argument("--timeout", type=float, default=1.0, help="UDP timeout per attempt, seconds")
    p.add_argument("--retries", type=int, default=3, help="UDP attempts per server")
    p.add_argument("--json", action="store_true", help="print the full result as JSON")
    p.add_argument("--quiet", "-q", action="store_true", help="print only the answer")
    a = p.parse_args(argv)

    live = not (a.json or a.quiet)
    r = IterativeResolver(
        roots=[(a.root_name, a.root)], timeout=a.timeout, retries=a.retries,
        on_step=(lambda s: print(format_step(s), flush=True)) if live else None,
        on_event=(lambda d, t: print("    " * d + "     -> " + t, flush=True)) if live else None,
    )
    if live:
        print(f"Resolving {a.name} {a.type.upper()} iteratively, starting at root {a.root}\n")
    res = r.resolve(a.name, a.type)

    if a.json:
        print(json.dumps(res.to_dict(), indent=2))
    elif a.quiet:
        for rr in res.answers:
            print(rr.value_text())
    else:
        print(f"\nStatus: {res.rcode}")
        for rr in res.answers:
            print("  " + str(rr))
        print(f"Queries: {res.queries} (packets sent incl. retries: {res.packets_sent}, "
              f"missing-glue sub-lookups: {res.sub_lookups})")
        print(f"Total time: {res.total_ms:.1f} ms")
    return 0 if res.rcode == "NOERROR" else 1


if __name__ == "__main__":
    sys.exit(main())
