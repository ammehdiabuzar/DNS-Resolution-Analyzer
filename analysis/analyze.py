"""Statistics, experiment table and graphs from results/raw/*.csv.

    python3 analysis/analyze.py          (runs in the client container)

For every (condition, metric, label) the samples of one run are first averaged
to a run mean; the 3 run means are then reported as mean, sample standard
deviation and min-max range. Outputs:
  results/summary.csv            every metric, every condition
  results/experiment_table.md    the experiment table for the report
  results/plots/*.png            graphs
"""

from __future__ import annotations

import glob
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

LAB = os.environ.get("LAB_DIR", "/lab")
RAW = os.path.join(LAB, "results", "raw")
OUT = os.path.join(LAB, "results")
PLOTS = os.path.join(OUT, "plots")

COND_ORDER = ["rtt20_loss0", "rtt100_loss0", "rtt200_loss0", "rtt20_loss2", "rtt20_loss5"]
COND_TITLE = {"rtt20_loss0": "20 ms / 0 %", "rtt100_loss0": "100 ms / 0 %",
              "rtt200_loss0": "200 ms / 0 %", "rtt20_loss2": "20 ms / 2 %",
              "rtt20_loss5": "20 ms / 5 %"}
DELAY_SWEEP = ["rtt20_loss0", "rtt100_loss0", "rtt200_loss0"]
LOSS_SWEEP = ["rtt20_loss0", "rtt20_loss2", "rtt20_loss5"]

# Fixed categorical order (validated default palette, slots 1-3), never cycled.
COLORS = {"do53": "#2a78d6", "dot": "#eb6834", "doh": "#1baf7a",
          "www.example.lab": "#2a78d6", "mail.example.lab": "#eb6834", "www.noglue.lab": "#1baf7a"}
INK, INK2, GRID, SURFACE = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

TABLE_METRICS = [
    ("iter_total_ms", "Iterative resolution time (ms)", ".1f"),
    ("iter_queries", "Queries per lookup", ".2f"),
    ("iter_packets_sent", "Packets sent per lookup (incl. retries)", ".2f"),
    ("first_query_ms", "First-query latency, new connection (ms)", ".1f"),
    ("repeat_query_ms", "Repeat-query latency, reused connection (ms)", ".1f"),
    ("do53_cold_ms", "Do53 via Unbound, cold cache (ms)", ".1f"),
    ("handshake_rtts", "Round trips before the DNS query is sent", ".2f"),
    ("packets_before_first_response", "Packets up to the first DNS response", ".1f"),
    ("bytes_first_query_session", "Bytes on the wire, 1-query session (B)", ".0f"),
    ("bytes_per_repeat_query", "Bytes per repeat query on open connection (B)", ".0f"),
    ("iter_bytes_per_lookup", "Bytes on the wire per iterative lookup (B)", ".0f"),
    ("iter_wire_total_ms", "Iterative time from packet timestamps (ms)", ".1f"),
    ("iter_app_minus_wire_ms", "Resolver timer minus capture timer (ms)", ".2f"),
    ("query_failures", "Failed transport queries per run", ".2f"),
    ("iter_failures", "Failed iterative lookups per run", ".2f"),
]
LABEL_ORDER = ["www.example.lab", "mail.example.lab", "www.noglue.lab", "do53", "dot", "doh"]


def load() -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(RAW, "*.csv")))
    if not files:
        raise SystemExit(f"no CSV files in {RAW}; run scripts/run_experiments.py first")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    keys = ["condition", "rtt_ms", "loss_pct", "metric", "label"]
    runs = df.groupby(keys + ["run"], as_index=False)["value"].mean()
    s = runs.groupby(keys)["value"].agg(mean="mean", std="std", min="min", max="max",
                                         runs="count").reset_index()
    s["std"] = s["std"].fillna(0.0)
    s["condition"] = pd.Categorical(s["condition"], COND_ORDER, ordered=True)
    return s.sort_values(["metric", "label", "condition"])


def _label_key(label: str):
    for i, k in enumerate(LABEL_ORDER):
        if label.startswith(k):
            return (i, label)
    return (len(LABEL_ORDER), label)


def experiment_table(s: pd.DataFrame) -> str:
    conds = [c for c in COND_ORDER if c in set(s["condition"].astype(str))]
    head = "| Metric | Label | " + " | ".join(COND_TITLE[c] for c in conds) + " |"
    lines = ["Cells: mean ± standard deviation [min – max] over the run means "
             "(3 runs per condition). Condition = added RTT / packet loss per direction "
             "on the R1–R2 link.", "", head, "|" + "---|" * (len(conds) + 2)]
    for metric, title, fmt in TABLE_METRICS:
        sub = s[s["metric"] == metric]
        for label in sorted(sub["label"].unique(), key=_label_key):
            cells = []
            for c in conds:
                r = sub[(sub["label"] == label) & (sub["condition"].astype(str) == c)]
                if r.empty:
                    cells.append("–")
                    continue
                r = r.iloc[0]
                cells.append(f"{r['mean']:{fmt}} ± {r['std']:{fmt}} [{r['min']:{fmt}} – {r['max']:{fmt}}]")
            lines.append(f"| {title} | {label} | " + " | ".join(cells) + " |")

    # Per-step table (delay sweep only, to keep it readable)
    steps = s[(s["metric"] == "iter_step_ms") & s["condition"].astype(str).isin(DELAY_SWEEP)]
    if not steps.empty:
        lines += ["", "### Per-step resolution time (ms), delay sweep", "",
                  "| Lookup step | " + " | ".join(COND_TITLE[c] for c in DELAY_SWEEP) + " |",
                  "|" + "---|" * (len(DELAY_SWEEP) + 1)]
        for label in sorted(steps["label"].unique(), key=_label_key):
            cells = []
            for c in DELAY_SWEEP:
                r = steps[(steps["label"] == label) & (steps["condition"].astype(str) == c)]
                cells.append("–" if r.empty else f"{r.iloc[0]['mean']:.1f} ± {r.iloc[0]['std']:.1f}")
            lines.append(f"| {label.replace(' | ', ' — ')} | " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ plots
def _style(ax, title, xlabel, ylabel):
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=11, color=INK, pad=10)
    ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    ax.set_ylabel(ylabel, color=INK2, fontsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8)


def _lines(s, metric, labels, conds, xvals, xlabel, title, ylabel, fname):
    fig, ax = plt.subplots(figsize=(6.4, 3.8), facecolor=SURFACE)
    ends = []
    for label in labels:
        sub = s[(s["metric"] == metric) & (s["label"] == label)]
        sub = sub.set_index(sub["condition"].astype(str)).reindex(conds)
        if sub["mean"].isna().all():
            continue
        ax.errorbar(xvals, sub["mean"], yerr=sub["std"], color=COLORS.get(label, INK),
                    linewidth=2, marker="o", markersize=6, capsize=3, label=label,
                    markeredgecolor=SURFACE, markeredgewidth=1.5)
        ends.append([float(sub["mean"].iloc[-1]), label])
    ax.set_xticks(xvals)
    ax.set_ylim(bottom=0)
    # Direct labels at the line ends, nudged apart so they never overlap.
    gap = 0.06 * ax.get_ylim()[1]
    ends.sort()
    for i in range(1, len(ends)):
        ends[i][0] = max(ends[i][0], ends[i - 1][0] + gap)
    for y, label in ends:
        ax.annotate(label, (xvals[-1], y), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=8, color=INK2, annotation_clip=False)
    _style(ax, title, xlabel, ylabel)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS, fname), dpi=160)
    plt.close(fig)


def _bars(s, metric, labels, cond, title, ylabel, fname, fmt="{:.0f}"):
    sub = s[(s["metric"] == metric) & (s["condition"].astype(str) == cond)]
    sub = sub.set_index("label").reindex(labels).dropna(subset=["mean"])
    if sub.empty:
        return
    fig, ax = plt.subplots(figsize=(5.2, 3.4), facecolor=SURFACE)
    bars = ax.bar(sub.index, sub["mean"], yerr=sub["std"], capsize=3, width=0.6,
                  color=[COLORS.get(l, INK) for l in sub.index], edgecolor=SURFACE, linewidth=2)
    for b, v in zip(bars, sub["mean"]):
        ax.annotate(fmt.format(v), (b.get_x() + b.get_width() / 2, v), xytext=(0, 4),
                    textcoords="offset points", ha="center", fontsize=8, color=INK)
    _style(ax, title, "", ylabel)
    fig.tight_layout()
    fig.savefig(os.path.join(PLOTS, fname), dpi=160)
    plt.close(fig)


def plots(s: pd.DataFrame):
    os.makedirs(PLOTS, exist_ok=True)
    tr = ["do53", "dot", "doh"]
    names = ["www.example.lab", "mail.example.lab", "www.noglue.lab"]
    rtt_x, loss_x = [20, 100, 200], [0, 2, 5]
    _lines(s, "first_query_ms", tr, DELAY_SWEEP, rtt_x, "Added RTT on R1–R2 link (ms)",
           "First-query latency (new connection) vs RTT", "Latency (ms)", "first_query_vs_rtt.png")
    _lines(s, "repeat_query_ms", tr, DELAY_SWEEP, rtt_x, "Added RTT on R1–R2 link (ms)",
           "Repeat-query latency (reused connection) vs RTT", "Latency (ms)", "repeat_query_vs_rtt.png")
    _lines(s, "first_query_ms", tr, LOSS_SWEEP, loss_x, "Packet loss per direction (%), 20 ms RTT",
           "First-query latency vs packet loss", "Latency (ms)", "first_query_vs_loss.png")
    _lines(s, "repeat_query_ms", tr, LOSS_SWEEP, loss_x, "Packet loss per direction (%), 20 ms RTT",
           "Repeat-query latency vs packet loss", "Latency (ms)", "repeat_query_vs_loss.png")
    _lines(s, "iter_total_ms", names, DELAY_SWEEP, rtt_x, "Added RTT on R1–R2 link (ms)",
           "Iterative resolution time vs RTT", "Total time (ms)", "iterative_vs_rtt.png")
    _lines(s, "iter_total_ms", names, LOSS_SWEEP, loss_x, "Packet loss per direction (%), 20 ms RTT",
           "Iterative resolution time vs packet loss", "Total time (ms)", "iterative_vs_loss.png")
    _bars(s, "iter_queries", names, "rtt20_loss0", "Queries per lookup (glue vs missing glue)",
          "Queries", "queries_per_lookup.png", "{:.1f}")
    _bars(s, "bytes_first_query_session", tr, "rtt20_loss0", "Bytes on the wire, one-query session",
          "Bytes", "bytes_first_session.png")
    _bars(s, "bytes_per_repeat_query", tr, "rtt20_loss0", "Bytes per query on an open connection",
          "Bytes", "bytes_repeat_query.png")
    _bars(s, "handshake_rtts", tr, "rtt200_loss0", "Round trips before the query (200 ms RTT)",
          "Round trips", "handshake_rtts.png", "{:.2f}")


def main():
    df = load()
    s = summarize(df)
    s.to_csv(os.path.join(OUT, "summary.csv"), index=False, float_format="%.3f")
    with open(os.path.join(OUT, "experiment_table.md"), "w", encoding="utf-8") as fh:
        fh.write("# Experiment table\n\n" + experiment_table(s))
    plots(s)
    print(f"runs loaded: {df.groupby(['condition', 'run']).ngroups}  rows: {len(df)}")
    print(f"wrote {OUT}/summary.csv, experiment_table.md and plots/")


if __name__ == "__main__":
    main()
