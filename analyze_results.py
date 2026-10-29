#!/usr/bin/env python3
"""
analyze_results.py — statistics and plots for the Shruti Lab Simulation Study CSV.

Usage:
    python analyze_results.py shruti_simulation_study_XXXX.csv [--out results_dir]

Needs: pandas, numpy, scipy, matplotlib   (pip install pandas numpy scipy matplotlib)

What it does
  * summary tables (mean, SD, median per method and per condition)
  * the planned paired comparisons H1, H2, H3 (see the Research page):
        Wilcoxon signed-rank test, rank-biserial effect size, bootstrap 95% CI of the
        mean difference, Holm correction across the planned tests
  * two PNG figures

Important notes for the paper
  * Unit of analysis: one simulated recording = one (seed, condition) pair. Conditions form a
    designed grid, not a random sample of "all rooms", so p-values describe consistency across
    THIS grid and these seeds only. Use more seeds, report the grid, and keep effect sizes.
  * Settings (alpha, beta, thresholds) were tuned on seeds 1 and 2. Evaluate on other seeds.
  * Simulation results are not evidence about real singers, drones or rooms.
"""
import argparse, os, sys
import numpy as np, pandas as pd
from scipy import stats
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

METHODS = ["baseline", "improved", "drone", "drone_room"]
NAMES = {"baseline": "Baseline (ACF)", "improved": "Improved v1 (YIN+smoothing)",
         "drone": "Drone-aware", "drone_room": "Drone-aware + room-adaptive"}
COLORS = {"baseline": "#a8472f", "improved": "#b8923a", "drone": "#2f7f7a", "drone_room": "#5c7a2f"}
METRICS = ["rpa50", "rpa20", "recallPct", "falseAlarmPct", "octaveErrPct", "medAbsErrCents"]
PAIRS = [  # (id, A, B, subset name, filter)  -- difference is A - B
    ("H1", "improved", "baseline", "all conditions", lambda d: np.ones(len(d), bool)),
    ("H2", "drone", "improved", "drone present", lambda d: d.vdrDb.astype(str) != "none"),
    ("H3", "drone_room", "drone", "RT60 > 0", lambda d: d.rt60.astype(float) > 0),
    ("H3b", "drone_room", "drone", "RT60 > 0 and drone present", lambda d: (d.rt60.astype(float) > 0) & (d.vdrDb.astype(str) != "none")),
]

def rank_biserial(diff):
    d = diff[diff != 0]
    if len(d) == 0:
        return 0.0
    ranks = stats.rankdata(np.abs(d))
    wp, wm = ranks[d > 0].sum(), ranks[d < 0].sum()
    return float((wp - wm) / (wp + wm))

def boot_ci(diff, n=10000, seed=1):
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), (n, len(diff)))
    m = diff[idx].mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))

def holm(p):
    p = np.asarray(p, float); order = np.argsort(p); adj = np.empty_like(p); run = 0.0
    for rank, i in enumerate(order):
        run = max(run, (len(p) - rank) * p[i]); adj[i] = min(1.0, run)
    return adj

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--out", default="analysis_out")
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    df = pd.read_csv(a.csv)
    need = {"runId", "method", "rpa50", "falseAlarmPct", "vdrDb", "snrDb", "rt60"}
    if not need <= set(df.columns):
        sys.exit("This does not look like a Shruti Lab simulation CSV. Missing: %s" % sorted(need - set(df.columns)))
    for m in METRICS:
        df[m] = pd.to_numeric(df[m], errors="coerce")
    present = [m for m in METHODS if m in set(df.method)]
    print("File:", a.csv, "| rows:", len(df), "| recordings:", df.runId.nunique(), "| seeds:", sorted(int(x) for x in df.seed.unique()))
    print("Versions:", sorted(set(df.simVersion)), sorted(set(df.algorithmVersion)))

    # ---- summaries
    pool = df.groupby("method")[METRICS].agg(["mean", "std", "median"]).reindex(present)
    pool.to_csv(os.path.join(a.out, "summary_by_method.csv"))
    print("\n=== Mean by method (pooled over the grid) ===")
    print(df.groupby("method")[METRICS].mean().reindex(present).round(1).to_string())
    for f in ["vdrDb", "snrDb", "rt60"]:
        t = df.pivot_table(index=f, columns="method", values="rpa50", aggfunc="mean")[present]
        t.to_csv(os.path.join(a.out, "rpa50_by_%s.csv" % f))
        print("\n=== RPA50 (%%) by %s ===" % f); print(t.round(1).to_string())

    # ---- paired tests
    wide = {m: df[df.method == m].set_index("runId") for m in present}
    cond = df.drop_duplicates("runId").set_index("runId")
    rows = []
    for hid, A, B, sub, flt in PAIRS:
        if A not in wide or B not in wide:
            continue
        keep = np.asarray(flt(cond.reset_index()), dtype=bool)
        ids = [i for i in wide[A].index.intersection(wide[B].index) if i in set(cond.index[keep])]
        if len(ids) < 3:
            continue
        for metric, better in [("rpa50", "higher"), ("falseAlarmPct", "lower")]:
            d = (wide[A].loc[ids, metric] - wide[B].loc[ids, metric]).dropna().to_numpy()
            if len(d) < 3:
                continue
            try:
                p = stats.wilcoxon(d, zero_method="wilcox", alternative="two-sided").pvalue if np.any(d != 0) else 1.0
            except ValueError:
                p = 1.0
            lo, hi = boot_ci(d)
            rows.append(dict(hypothesis=hid, A=A, B=B, subset=sub, metric=metric, better=better, n_pairs=len(d),
                             mean_diff_A_minus_B=d.mean(), median_diff=float(np.median(d)), ci95_low=lo, ci95_high=hi,
                             A_wins=int((d > 1).sum()), B_wins=int((d < -1).sum()), ties=int((np.abs(d) <= 1).sum()),
                             wilcoxon_p=p, rank_biserial_r=rank_biserial(d)))
    res = pd.DataFrame(rows)
    if len(res):
        res["holm_p"] = np.nan
        for metric in res.metric.unique():
            m = res.metric == metric; res.loc[m, "holm_p"] = holm(res.loc[m, "wilcoxon_p"].to_numpy())
        res.to_csv(os.path.join(a.out, "paired_tests.csv"), index=False)
        print("\n=== Planned paired comparisons (difference = A − B; wins use ±1 point) ===")
        show = res[["hypothesis", "A", "B", "subset", "metric", "n_pairs", "mean_diff_A_minus_B", "ci95_low", "ci95_high", "A_wins", "B_wins", "wilcoxon_p", "holm_p", "rank_biserial_r"]]
        print(show.round(3).to_string(index=False))
        print("\nReading guide: for rpa50 a positive difference favours A; for falseAlarmPct a negative difference favours A."
              "\nA hypothesis is only 'supported' if the effect is in the predicted direction, the CI excludes 0 and the result"
              "\nholds across conditions — look at the per-condition tables too. Report rejected hypotheses as results.")
    else:
        print("\nNot enough paired data for the planned comparisons (need the relevant methods and conditions).")

    # ---- figures
    for f, lab, fn in [("vdrDb", "Drone level (voice vs drone)", "rpa50_by_drone.png"), ("rt60", "Room decay time RT60 (s)", "rpa50_by_room.png")]:
        t = df.pivot_table(index=f, columns="method", values="rpa50", aggfunc="mean")[present]
        order = sorted(t.index, key=lambda v: (-1e9 if str(v) == "none" else float(v)) if f == "vdrDb" else float(v))
        t = t.loc[order]; x = np.arange(len(t)); w = 0.8 / len(present)
        fig, ax = plt.subplots(figsize=(8, 4))
        for k, m in enumerate(present):
            ax.bar(x + k * w - 0.4 + w / 2, t[m], w, label=NAMES[m], color=COLORS[m])
        ax.set_xticks(x); ax.set_xticklabels([str(v) for v in t.index]); ax.set_ylim(0, 100)
        ax.set_xlabel(lab); ax.set_ylabel("Raw pitch accuracy ±50 ¢ (%)"); ax.legend(fontsize=8); ax.grid(axis="y", alpha=.3)
        fig.tight_layout(); fig.savefig(os.path.join(a.out, fn), dpi=160); plt.close(fig)
    print("\nSaved tables and figures in:", os.path.abspath(a.out))

if __name__ == "__main__":
    main()
