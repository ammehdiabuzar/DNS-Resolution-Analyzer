"""One experiment run under the current network condition (runs in the client).

Started by scripts/run_experiments.py, which applies tc netem on the routers
and flushes Unbound's cache before every run. This script:
  1. starts a .pcapng capture of the whole run
  2. cold Do53 query through Unbound (cache was just flushed)
  3. iterative resolution of every test name with our resolver
     (total time, per-step time, queries per lookup)
  4. Do53 / DoT / DoH first-query latency (new connection every time)
     and repeat-query latency (queries reusing one open connection)
  5. a "wire" phase: marked time windows that are later analysed from the
     capture for bytes per query, handshake round trips, packets before the
     first response, and an iterative-timing cross-check
and writes long-format rows to results/raw/<condition>_run<N>.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import time

from common import (LAB, ROOT_IP, TEST_NAMES, TRANSPORT_NAME, UNBOUND_IP, Capture,
                    tshark_fields)
from dnsresolver import IterativeResolver
from transports import TRANSPORTS, Do53, QueryFailed


class Recorder:
    def __init__(self, cond, rtt, loss, run):
        self.base = {"condition": cond, "rtt_ms": rtt, "loss_pct": loss, "run": run}
        self.rows = []

    def add(self, metric, label, value, sample=0):
        self.rows.append({**self.base, "metric": metric, "label": label,
                          "sample": sample, "value": value})


def phase_iterative(rec: Recorder, samples: int):
    resolver = IterativeResolver(roots=[("a.root-servers.lab.", ROOT_IP)])
    for name in TEST_NAMES:
        fails = 0
        for i in range(samples):
            res = resolver.resolve(name)
            if res.rcode != "NOERROR" or not res.answers:
                fails += 1
                continue
            rec.add("iter_total_ms", name, res.total_ms, i)
            rec.add("iter_queries", name, res.queries, i)
            rec.add("iter_packets_sent", name, res.packets_sent, i)
            for s in res.steps:
                label = f"{name} | step {s.index}: {s.qname} @ zone {s.zone}"
                rec.add("iter_step_ms", label, s.rtt_ms, i)
            time.sleep(0.05)
        rec.add("iter_failures", name, fails)
        print(f"  iterative {name}: done ({fails} failures)", flush=True)


def phase_transports(rec: Recorder, samples: int, repeat: int, keylog: str):
    Do53().first_query(TRANSPORT_NAME)          # make sure Unbound's cache is warm
    for cls in TRANSPORTS:
        t = cls(keylog=keylog)
        fails = 0
        try:
            # Uncounted warm-up: the first connection in a process pays one-time
            # Python costs (lazy imports, SSL/HTTP2 setup), which are not network cost.
            t.first_query(TRANSPORT_NAME)
        except (OSError, QueryFailed):
            pass
        for i in range(samples):
            try:
                rec.add("first_query_ms", t.name, t.first_query(TRANSPORT_NAME), i)
            except (OSError, QueryFailed) as exc:
                fails += 1
                print(f"  {t.name} first query failed: {exc}", flush=True)
            time.sleep(0.2)
        try:
            t.open()
            t.query_open(TRANSPORT_NAME)        # warm-up: connection setup, not counted
            for i in range(repeat):
                rec.add("repeat_query_ms", t.name, t.query_open(TRANSPORT_NAME), i)
        except (OSError, QueryFailed) as exc:
            fails += 1
            print(f"  {t.name} repeat session failed: {exc}", flush=True)
        finally:
            t.close()
        rec.add("query_failures", t.name, fails)
        print(f"  transport {t.name}: done ({fails} failures)", flush=True)


def phase_wire(rtt_ms: float, keylog: str):
    """Run marked sessions; returns time windows for the capture analysis."""
    gap = max(1.0, 3 * rtt_ms / 1000) + 0.5
    windows = []
    for cls in TRANSPORTS:
        t = cls(keylog=keylog)
        w0 = time.time()
        try:
            t.first_query(TRANSPORT_NAME)
        except (OSError, QueryFailed):
            pass
        time.sleep(gap)
        windows.append({"kind": "single", "transport": t.name, "t0": w0, "t1": time.time() - 0.2})
        w0 = time.time()
        try:
            t.open()
            for _ in range(11):
                t.query_open(TRANSPORT_NAME)
        except (OSError, QueryFailed):
            pass
        finally:
            t.close()
        time.sleep(gap)
        windows.append({"kind": "multi", "transport": t.name, "t0": w0, "t1": time.time() - 0.2})
    resolver = IterativeResolver(roots=[("a.root-servers.lab.", ROOT_IP)])
    for name in TEST_NAMES:
        w0 = time.time()
        res = resolver.resolve(name)
        time.sleep(gap)
        windows.append({"kind": "iter", "name": name, "t0": w0, "t1": time.time() - 0.2,
                        "app_total_ms": res.total_ms, "queries": res.queries,
                        "ok": res.rcode == "NOERROR"})
    return windows


FIELDS = ["frame.time_epoch", "ip.src", "ip.dst", "frame.len", "tcp.flags.syn",
          "tcp.flags.ack", "dns.flags.response", "dns.id", "udp.port", "tcp.port"]
# Server port of each transport: a window only counts that transport's packets,
# so the teardown of a previous connection cannot leak into the next window.
SERVER_PORT = {"do53": "53", "dot": "853", "doh": "443"}
WIRE_METRICS = {"bytes_first_query_session", "packets_before_first_response", "handshake_rtts",
                "bytes_per_repeat_query", "iter_wire_total_ms", "iter_app_total_ms",
                "iter_app_minus_wire_ms", "iter_wire_query_packets", "iter_bytes_per_lookup"}


def analyse_wire(rec: Recorder, pcap: str, keylog: str, windows):
    frames = tshark_fields(pcap, FIELDS, display_filter="ip", keylog=keylog)
    for f in frames:
        f["t"] = float(f["frame.time_epoch"] or 0)
        f["len"] = int(f["frame.len"] or 0)
        f["resp"] = f["dns.flags.response"].split(",") if f["dns.flags.response"] else []

    def in_window(w, pred):
        return [f for f in frames if w["t0"] <= f["t"] <= w["t1"] and pred(f)]

    def to_unbound(name):
        port = SERVER_PORT[name]
        return lambda f: (UNBOUND_IP in (f["ip.src"], f["ip.dst"]) and
                          port in (f["udp.port"] + "," + f["tcp.port"]).split(","))

    single_bytes = {}
    for w in windows:
        if w["kind"] == "single":
            name = w["transport"]
            fs = in_window(w, to_unbound(name))
            single_bytes[name] = sum(f["len"] for f in fs)
            rec.add("bytes_first_query_session", name, single_bytes[name])
            q = next((f for f in fs if f["ip.src"] != UNBOUND_IP and "0" in f["resp"]), None)
            r = next((f for f in fs if f["ip.src"] == UNBOUND_IP and "1" in f["resp"]), None)
            if r is not None:
                rec.add("packets_before_first_response", name, sum(1 for f in fs if f["t"] <= r["t"]))
            syn = next((f for f in fs if f["tcp.flags.syn"] in ("1", "True") and
                        f["tcp.flags.ack"] in ("0", "False")), None)
            synack = next((f for f in fs if f["tcp.flags.syn"] in ("1", "True") and
                           f["tcp.flags.ack"] in ("1", "True")), None)
            if name == "do53":
                rec.add("handshake_rtts", name, 0)
            elif syn and synack and q and synack["t"] > syn["t"]:
                rec.add("handshake_rtts", name, (q["t"] - syn["t"]) / (synack["t"] - syn["t"]))
        elif w["kind"] == "multi":
            name = w["transport"]
            total = sum(f["len"] for f in in_window(w, to_unbound(name)))
            if name in single_bytes:
                rec.add("bytes_per_repeat_query", name, (total - single_bytes[name]) / 10)
        elif w["kind"] == "iter" and w["ok"]:
            fs = in_window(w, lambda f: f["ip.src"].startswith("10.10.1.") or
                           f["ip.dst"].startswith("10.10.1."))
            queries = [f for f in fs if f["ip.dst"].startswith("10.10.1.") and "0" in f["resp"]]
            replies = [f for f in fs if f["ip.src"].startswith("10.10.1.") and "1" in f["resp"]]
            if queries and replies:
                wire_ms = (replies[-1]["t"] - queries[0]["t"]) * 1000
                rec.add("iter_wire_total_ms", w["name"], wire_ms)
                rec.add("iter_app_total_ms", w["name"], w["app_total_ms"])
                rec.add("iter_app_minus_wire_ms", w["name"], w["app_total_ms"] - wire_ms)
                rec.add("iter_wire_query_packets", w["name"], len(queries))
                rec.add("iter_bytes_per_lookup", w["name"], sum(f["len"] for f in fs))


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--condition", required=True)
    p.add_argument("--rtt", type=float, required=True, help="RTT added on the transit link (ms)")
    p.add_argument("--loss", type=float, required=True, help="loss per direction (%%)")
    p.add_argument("--run", type=int, required=True)
    p.add_argument("--samples", type=int, default=5, help="samples per run for lookups / first queries")
    p.add_argument("--repeat", type=int, default=10, help="queries on one reused connection")
    p.add_argument("--out-dir", default=os.path.join(LAB, "results", "raw"))
    p.add_argument("--capture-dir", default=os.path.join(LAB, "captures", "experiments"))
    a = p.parse_args()

    tag = f"{a.condition}_run{a.run}"
    os.makedirs(a.out_dir, exist_ok=True)
    os.makedirs(os.path.join(a.capture_dir, "keys"), exist_ok=True)
    pcap = os.path.join(a.capture_dir, f"{tag}.pcapng")
    keylog = os.path.join(a.capture_dir, "keys", f"{tag}.keys")
    if os.path.exists(keylog):
        os.remove(keylog)

    rec = Recorder(a.condition, a.rtt, a.loss, a.run)
    print(f"[{tag}] capture -> {pcap}", flush=True)
    with Capture(pcap):
        try:
            rec.add("do53_cold_ms", "unbound (cache flushed)", Do53().first_query(TRANSPORT_NAME))
        except (OSError, QueryFailed) as exc:
            print(f"  cold Do53 failed: {exc}", flush=True)
        phase_iterative(rec, a.samples)
        phase_transports(rec, a.samples, a.repeat, keylog)
        windows = phase_wire(a.rtt, keylog)
    analyse_wire(rec, pcap, keylog, windows)

    out = os.path.join(a.out_dir, f"{tag}.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rec.rows[0].keys()))
        w.writeheader()
        w.writerows(rec.rows)
    with open(os.path.join(a.out_dir, f"{tag}.windows.json"), "w") as fh:
        json.dump(windows, fh, indent=1)

    def quick(metric, label):
        v = [r["value"] for r in rec.rows if r["metric"] == metric and r["label"] == label]
        v = [x for x in v if isinstance(x, (int, float)) and not math.isnan(x)]
        return f"{statistics.mean(v):.1f}" if v else "n/a"
    print(f"[{tag}] wrote {len(rec.rows)} rows to {out}")
    print(f"[{tag}] first query ms  do53={quick('first_query_ms','do53')} "
          f"dot={quick('first_query_ms','dot')} doh={quick('first_query_ms','doh')}")
    print(f"[{tag}] repeat query ms do53={quick('repeat_query_ms','do53')} "
          f"dot={quick('repeat_query_ms','dot')} doh={quick('repeat_query_ms','doh')}")
    print(f"[{tag}] iterative ms    " + " ".join(f"{n}={quick('iter_total_ms', n)}" for n in TEST_NAMES))


if __name__ == "__main__":
    main()
