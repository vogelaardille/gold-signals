"""Ronde 2, VERKENNEND (PLAN2 §10): elke variant van F1/F2/F4 over 2010-2018 zonder selectie,
tegen random entries met exact dezelfde exits. Verandert geen status.
Draaien: .venv/bin/python -m goldsignals.round2.explore
"""
import json

import numpy as np
import pandas as pd

from goldsignals.config import load_config, project_path
from goldsignals.round2 import families as fam
from goldsignals.round2 import run
from goldsignals.round2.indicators import bars


def main():
    cfg = load_config()
    r2 = cfg["round2"]
    rng = np.random.default_rng(r2["seed"] + 1)
    end = pd.Timestamp(r2["periods"]["holdout_start"], tz="UTC")
    B = {tf: bars(tf, end, cfg) for tf in ("1d", "4h")}
    run._init(B)
    w = r2["walkforward"]
    years = range(w["first_test_year"], w["last_test_year"] + 1)
    rows = []
    for f in ("F1", "F2", "F4"):
        for v in fam.variants(cfg, f):
            vid, t = run.run_variant((v, cfg))
            t = t[t["year"].isin(years)]
            # 'chosen' = deze variant in elk test-jaar -> zelfde random-procedure als in run.py
            chosen = [{"test_year": y, "variant": vid} for y in years]
            rnd = run.random_same_exit(t, chosen, {vid: v}, B, cfg, r2["random_replicates"], rng)
            r = t["r1x"].to_numpy()
            rows.append({"family": f, "variant": vid.replace("family=", ""), "n": len(r),
                         "avg_r_1x": r.mean() if len(r) else np.nan,
                         "avg_r_long": t.loc[t["direction"] == 1, "r1x"].mean(),
                         "avg_r_short": t.loc[t["direction"] == -1, "r1x"].mean(),
                         "random_mean": np.nanmean(rnd), "random_p95": np.nanpercentile(rnd, 95),
                         "pct_vs_random": (rnd < r.mean()).mean() * 100 if len(r) else np.nan})
            print(rows[-1]["variant"], rows[-1]["n"], f"{rows[-1]['avg_r_1x']:+.3f}", f"random {rows[-1]['random_mean']:+.3f}",
                  f"pct {rows[-1]['pct_vs_random']:.0f}", flush=True)
    df = pd.DataFrame(rows)
    out = project_path("research/round2/results/explore_variants.csv")
    df.to_csv(out, index=False, float_format="%.4f")
    print("->", out)



def f2_deep_dive():
    """Verdieping op de 4h-varianten van F2 ('te mooi'-protocol, PLAN2 §9). Beschrijvend."""
    cfg = load_config()
    r2 = cfg["round2"]
    rng = np.random.default_rng(r2["seed"] + 2)
    end = pd.Timestamp(r2["periods"]["holdout_start"], tz="UTC")
    B = {"4h": bars("4h", end, cfg), "1d": bars("1d", end, cfg)}
    run._init(B)
    w = r2["walkforward"]
    oos_start = pd.Timestamp(f"{w['first_test_year']}-01-01", tz="UTC")
    oos_end = pd.Timestamp(f"{w['last_test_year'] + 1}-01-01", tz="UTC")
    r1 = pd.read_csv(project_path("research/results/trials.csv"))
    tr2 = pd.read_csv(project_path("research/round2/results/trials.csv"))
    n_trials = r2["round1_trials"] + r2["burned_holdout_openings"] + len(tr2)
    valid = np.r_[r1.loc[r1["n"] >= 15, "sharpe"].dropna(), tr2.loc[tr2["valid"], "sharpe"].dropna()]
    noise = float(np.mean(np.r_[1 / r1.loc[r1["n"] >= 15, "n"], 1 / tr2.loc[tr2["valid"], "n"]]))
    out = {}
    for v in [x for x in fam.variants(cfg, "F2") if x["timeframe"] == "4h"]:
        vid, t = run.run_variant((v, cfg))
        t = t[(t["year"] >= w["first_test_year"]) & (t["year"] <= w["last_test_year"])]
        s = run.summarize(t, cfg, rng)
        s["equity"] = run.equity_stats(t, oos_start, oos_end)
        s["dsr"], s["dsr_sr0"] = run.dsr(t["r1x"].to_numpy(), n_trials, valid)
        s["dsr_mild"], _ = run.dsr(t["r1x"].to_numpy(), n_trials, valid, mild_noise=noise)
        s["without_top5"] = float(t["r1x"].sort_values().iloc[:-5].mean())
        s["pre2013"] = float(t.loc[t["year"] <= 2012, "r1x"].mean())
        s["post2013"] = float(t.loc[t["year"] >= 2013, "r1x"].mean())
        s["overlaps"] = int((t["entry_i"].to_numpy()[1:] <= t["exit_i"].to_numpy()[:-1]).sum())
        out[vid.replace("family=", "")] = s
    out["_buy_and_hold"] = run.buy_hold_stats(B["1d"], oos_start, oos_end)
    p = project_path("research/round2/results/explore_f2.json")
    p.write_text(json.dumps(run.clean(out), indent=1))
    for k, s in out.items():
        if k.startswith("_"):
            continue
        print(k, f"R {s['avg_r_1x']:+.3f} [{s['ci']['lo']:+.3f}; {s['ci']['hi']:+.3f}] DSR {s['dsr']:.3f} mild {s['dsr_mild']:.3f}",
              {kk: round(vv, 2) for kk, vv in s["equity"].items()}, f"winrate {s['winrate']:.0f}% / break-even {s['breakeven_winrate']:.0f}%")
    print("B&H", {k: round(v, 2) for k, v in out["_buy_and_hold"].items()})


if __name__ == "__main__":
    main()
    f2_deep_dive()
