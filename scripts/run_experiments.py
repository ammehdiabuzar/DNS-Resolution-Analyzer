"""Run the full experiment matrix and build the results table.

    python scripts/run_experiments.py                 # 5 conditions x 3 runs
    python scripts/run_experiments.py --runs 1 --conditions rtt20_loss0   # quick check

Conditions (tc netem on the R1-R2 transit link):
  delay sweep, no loss : 20, 100, 200 ms RTT
  loss sweep, 20 ms RTT: 0, 2, 5 % loss (per direction)
rtt20_loss0 belongs to both sweeps, so 5 distinct conditions are measured.

For every run: Unbound's cache is flushed, then experiments/measure.py runs in
the client, capturing the run to captures/experiments/<cond>_run<N>.pcapng
and writing results/raw/<cond>_run<N>.csv. Finally analysis/analyze.py
computes mean, standard deviation and range and draws the graphs.
Only the Python standard library and Docker are needed on the host.
"""

from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from lab import check_running, clear_netem, dexec, flush_unbound, set_netem  # noqa: E402

CONDITIONS = {
    "rtt20_loss0": (20, 0),
    "rtt100_loss0": (100, 0),
    "rtt200_loss0": (200, 0),
    "rtt20_loss2": (20, 2),
    "rtt20_loss5": (20, 5),
}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--runs", type=int, default=3)
    p.add_argument("--samples", type=int, default=5)
    p.add_argument("--repeat", type=int, default=10)
    p.add_argument("--conditions", nargs="*", default=list(CONDITIONS), choices=list(CONDITIONS))
    p.add_argument("--no-analysis", action="store_true")
    a = p.parse_args()

    check_running()
    started = time.time()
    try:
        for cond in a.conditions:
            rtt, loss = CONDITIONS[cond]
            print(f"\n######## condition {cond}: RTT +{rtt} ms, loss {loss}% ########", flush=True)
            set_netem(rtt, loss)
            time.sleep(1)
            dexec("client", "ping", "-c", "5", "-i", "0.3", "10.10.4.10", check=False)
            for run in range(1, a.runs + 1):
                flush_unbound()
                dexec("client", "python3", "experiments/measure.py",
                      "--condition", cond, "--rtt", str(rtt), "--loss", str(loss),
                      "--run", str(run), "--samples", str(a.samples), "--repeat", str(a.repeat))
    finally:
        clear_netem()
    print(f"\nall runs finished in {(time.time() - started) / 60:.1f} min", flush=True)
    if not a.no_analysis:
        dexec("client", "python3", "analysis/analyze.py")


if __name__ == "__main__":
    main()
