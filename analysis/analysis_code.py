#!/usr/bin/env python3
"""
Recomputes the numbers in the results tables from the raw logs in data/.

    python analysis/compute_metrics.py
    python analysis/compute_metrics.py --data some/other/dir

Needs pandas, numpy.
"""

import argparse
import glob
import os
import sys

import numpy as np
import pandas as pd

# Fixed seed so the bootstrap intervals come out the same every run --
# otherwise the last decimal moves around and it looks like the numbers
# in the paper are wrong.
RNG = np.random.default_rng(42)
N_BOOT = 10_000
Z = 1.96


def load_csv(path):
    df = pd.read_csv(path)

    # The logger appends "Per-node summary" and "Overall summary" blocks at the
    # bottom of every file. Those rows aren't measurements, so drop anything
    # whose node_id isn't 1 or 2.
    df = df[df["node_id"].astype(str).str.strip().isin(["1", "2"])].copy()

    df["node_id"] = df["node_id"].astype(int)
    df["rtt_ms"] = pd.to_numeric(df["rtt_ms"], errors="coerce")
    df["attempts"] = pd.to_numeric(df["attempts"], errors="coerce")
    df["success"] = df["success"].astype(str).str.strip().str.lower().eq("true")

    # Only the CPU sweep file has this column.
    if "cpu_load_percent" in df.columns:
        df["cpu_load_percent"] = pd.to_numeric(df["cpu_load_percent"],
                                               errors="coerce")

    return df


def load_many(paths):
    if not paths:
        return pd.DataFrame()
    return pd.concat([load_csv(p) for p in paths], ignore_index=True)


def wilson_ci(successes, n, z=Z):
    """95% CI for a proportion, Wilson score.

    Not the textbook p +- z*sqrt(p(1-p)/n) one: half our conditions have zero
    hard failures and that formula gives [100, 100] there, which is obviously
    nonsense for ~230 samples.
    """
    if n == 0:
        return float("nan"), float("nan")
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return 100 * (centre - margin) / denom, 100 * (centre + margin) / denom


def bootstrap_median_ci(x, n_boot=N_BOOT, alpha=0.05):
    x = np.asarray(x, dtype=float)
    if x.size < 2:
        return float("nan"), float("nan")
    idx = RNG.integers(0, x.size, size=(n_boot, x.size))
    meds = np.median(x[idx], axis=1)
    lo, hi = np.percentile(meds, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def summarise(group):
    n = len(group)
    successes = int(group["success"].sum())
    hard = n - successes

    # Soft failure = got through, but needed a retry to do it.
    soft = int(((group["success"]) & (group["attempts"] > 1)).sum())

    # Timings only make sense for attempts that actually completed -- a
    # transaction that hit the 2 s timeout is a censored observation, not a
    # 2000 ms latency sample.
    ok = group.loc[group["success"], "rtt_ms"].dropna().to_numpy()

    pdr = 100.0 * successes / n if n else float("nan")
    pdr_lo, pdr_hi = wilson_ci(successes, n)

    if ok.size:
        med_lo, med_hi = bootstrap_median_ci(ok)
        q1, q3 = np.percentile(ok, [25, 75])
        stats = dict(
            mean=float(ok.mean()),
            median=float(np.median(ok)),
            med_lo=med_lo,
            med_hi=med_hi,
            iqr=float(q3 - q1),
            p95=float(np.percentile(ok, 95)),
            minimum=float(ok.min()),
            maximum=float(ok.max()),
        )
    else:
        keys = ["mean", "median", "med_lo", "med_hi", "iqr", "p95",
                "minimum", "maximum"]
        stats = dict.fromkeys(keys, float("nan"))

    return dict(n=n, soft=soft, hard=hard, pdr=pdr,
                pdr_lo=pdr_lo, pdr_hi=pdr_hi, **stats)


HEADER = (
    f"{'Condition':<14}{'Node':<7}{'N':>5}{'Soft':>6}{'Hard':>6}"
    f"{'PDR %':>8}{'PDR 95% CI':>18}"
    f"{'Mean':>9}{'Median':>9}{'Med 95% CI':>18}"
    f"{'IQR':>8}{'p95':>9}{'Min':>9}{'Max':>10}"
)


def print_row(condition, node, s):
    print(
        f"{condition:<14}Node {node:<2}{s['n']:>5}{s['soft']:>6}{s['hard']:>6}"
        f"{s['pdr']:>8.2f}"
        f"   [{s['pdr_lo']:6.2f},{s['pdr_hi']:7.2f}]"
        f"{s['mean']:>9.2f}{s['median']:>9.2f}"
        f"   [{s['med_lo']:6.2f},{s['med_hi']:7.2f}]"
        f"{s['iqr']:>8.2f}{s['p95']:>9.2f}"
        f"{s['minimum']:>9.2f}{s['maximum']:>10.2f}"
    )


def section(title):
    print()
    print("=" * len(HEADER))
    print(title)
    print("=" * len(HEADER))
    print(HEADER)
    print("-" * len(HEADER))


def main(data_dir):
    def g(pattern):
        return sorted(glob.glob(os.path.join(data_dir, pattern)))

    # Short tests are 4 runs each, the long one is 3. We pool the repetitions
    # rather than averaging the per-run summaries.
    conditions = {
        "1 m cable": g("1m_*.csv"),
        "2 m cable": g("2m_*.csv"),
        "4 m cable": g("4m_*.csv"),
        "5 h test":  g("5hr_4m_*.csv"),
    }
    cpu_files = g("CPU_LOAD.csv")

    for name, files in conditions.items():
        if not files:
            print(f"warning: nothing found for {name}", file=sys.stderr)
    if not cpu_files:
        print("warning: CPU_LOAD.csv not found", file=sys.stderr)

    section("Tables I & II -- by test condition")
    for cond, files in conditions.items():
        if not files:
            continue
        df = load_many(files)
        for node in (1, 2):
            sub = df[df["node_id"] == node]
            if len(sub):
                print_row(cond, node, summarise(sub))

    if not cpu_files:
        return 0

    cpu = load_many(cpu_files)
    levels = sorted(cpu["cpu_load_percent"].dropna().unique())

    section("Table III -- by CPU load level")
    for lvl in levels:
        for node in (1, 2):
            sub = cpu[(cpu["cpu_load_percent"] == lvl) &
                      (cpu["node_id"] == node)]
            if len(sub):
                print_row(f"{lvl:.0f} % CPU", node, summarise(sub))

    # Per-level PDR is based on only ~59 samples, so the intervals are wide.
    # The pooled figure is the one quoted in the text.
    section("Pooled over all load levels")
    for node in (1, 2):
        sub = cpu[cpu["node_id"] == node]
        if len(sub):
            print_row("75-95 % CPU", node, summarise(sub))

    # This is the "no degradation" claim: if load mattered, these medians
    # would climb.
    print()
    print("Median RTT per load level")
    print("-" * 44)
    for node in (1, 2):
        meds = []
        for lvl in levels:
            ok = cpu[(cpu["cpu_load_percent"] == lvl) &
                     (cpu["node_id"] == node) &
                     (cpu["success"])]["rtt_ms"].dropna()
            if len(ok):
                meds.append(float(np.median(ok)))
        if meds:
            print(f"  Node {node}: {' '.join(f'{m:.1f}' for m in meds)}"
                  f"  (span {max(meds) - min(meds):.2f} ms)")

    print()
    print("PDR intervals are Wilson score, median intervals are percentile "
          "bootstrap")
    print(f"({N_BOOT} resamples, seed 42). Timing stats use successful "
          "transactions only.")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    args = ap.parse_args()
    raise SystemExit(main(args.data))
