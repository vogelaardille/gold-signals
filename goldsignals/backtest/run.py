"""Deel B: alle strategieën door dezelfde walk-forward, status bepalen, leaderboard schrijven.

Draaien:  .venv/bin/python -m goldsignals.backtest.run [--holdout]

Stappen per strategie (config.yaml -> strategies):
1. Walk-forward met Optuna binnen de research-periode (elke trial gelogd).
2. Out-of-sample (OOS) trades uit alle test-vensters samen, ook bij 0x/2x/3x kosten.
3. Candidate-eisen (validation.py). Daarnaast: deflated Sharpe (over ALLE trials van
   ALLE strategieën) en excess t.o.v. willekeurige entries in dezelfde richting.
4. Alleen met --holdout en alleen voor candidates: de hold-out één keer openen
   (holdout.py logt en weigert een tweede keer).
Output: research/results/leaderboard.csv, strategies.json (voor paper trading),
trials.csv, backtest.json en research/backtest.md.
"""
import argparse
import copy
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from goldsignals.backtest import holdout
from goldsignals.backtest.engine import run_backtest
from goldsignals.backtest.metrics import r_by_year, summarize
from goldsignals.backtest.validation import decide_status, deflated_sharpe, excess_vs_random
from goldsignals.backtest.walkforward import final_params, index_range, walk_forward, windows
from goldsignals.config import load_config, project_path
from goldsignals.market import load_market, period_bounds
from goldsignals.paper.runner import load_class
from goldsignals.strategies.baselines import buy_and_hold

RESULTS = project_path("research/results")


def maker(spec: dict):
    cls = load_class(spec["class"])
    return lambda params: cls({**spec["params"], **params})


def methods_needed(specs: dict) -> tuple:
    return tuple(sorted({s["params"].get("method", "A") for s in specs.values()} | {"A"}))


# ---------------------------------------------------------------------------
# Per strategie (draait in een eigen proces)
# ---------------------------------------------------------------------------

def _evaluate(args):
    sid, spec, cfg = args
    _, research_end = period_bounds(cfg, "research")
    market = load_market(cfg, methods=methods_needed({sid: spec}), build=False, until=research_end)
    trials = []
    mults = cfg["costs"]["sensitivity_multipliers"]
    wf = walk_forward(maker(spec), spec.get("space") or {}, spec["params"], market, cfg, sid, trials, mults)
    final = final_params(maker(spec), spec.get("space") or {}, spec["params"], market, cfg, sid, trials) \
        if spec.get("space") else dict(spec["params"])
    return sid, {"oos": wf["oos"], "chosen": wf["chosen"], "final": final, "trials": trials}


def random_baseline(cfg, spec) -> pd.DataFrame:
    """Veel willekeurige entries in de walk-forward test-periode, voor 'excess t.o.v. random'."""
    _, research_end = period_bounds(cfg, "research")
    market = load_market(cfg, methods=("A",), build=False, until=research_end)
    w = windows(cfg)
    i0, _ = index_range(market, w[0][2], w[0][3])
    _, i1 = index_range(market, w[-1][2], w[-1][3])
    params = {**spec["params"], "prob": cfg["validation"]["random_baseline_prob"]}
    return run_backtest(load_class(spec["class"])(params), market, i0, i1, cfg).trades


def run_holdout(spec, params, cfg) -> dict:
    """De hold-out-backtest. Wordt alleen aangeroepen via holdout.open_once."""
    start, end = period_bounds(cfg, "holdout")
    market = load_market(cfg, methods=methods_needed({"x": spec}), build=True, until=end)
    i0, i1 = index_range(market, start, end)
    t = run_backtest(load_class(spec["class"])(params), market, i0, i1, cfg).trades
    s = summarize(t, cfg["account"]["start_equity_eur"], cfg["account"]["risk_pct"])
    return {"n": s["n"], "avg_r": s["avg_r"], "total_r": s["total_r"], "winrate": s["winrate"],
            "max_dd_pct": s["max_dd_pct"], "n_long": s["n_long"], "avg_r_long": s["avg_r_long"],
            "n_short": s["n_short"], "avg_r_short": s["avg_r_short"]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--holdout", action="store_true", help="hold-out openen voor candidates (eenmalig!)")
    ap.add_argument("--only", nargs="*", help="alleen deze strategieën")
    args = ap.parse_args()
    cfg = load_config()
    acc = cfg["account"]
    RESULTS.mkdir(parents=True, exist_ok=True)
    specs = {k: v for k, v in cfg["strategies"].items() if v.get("enabled", True)}
    if args.only:
        specs = {k: v for k, v in specs.items() if k in args.only}

    # 1. Walk-forward parallel per strategie
    workers = min(len(specs), cfg["snapshots"]["workers"] or os.cpu_count())
    with ProcessPoolExecutor(workers) as ex:
        results = dict(ex.map(_evaluate, [(sid, spec, cfg) for sid, spec in specs.items()]))

    all_trials = pd.DataFrame([t for r in results.values() for t in r["trials"]])
    prev = RESULTS / "trials.csv"
    if args.only and prev.exists():   # trials van eerdere runs van andere strategieën blijven meetellen
        old = pd.read_csv(prev)
        all_trials = pd.concat([old[~old["strategy"].isin(specs)], all_trials], ignore_index=True)
    all_trials.to_csv(prev, index=False)
    n_trials = int(len(all_trials)) + sum(1 for s in cfg["strategies"].values() if not s.get("space"))
    trial_sr = all_trials["sharpe"].to_numpy(float) if len(all_trials) else np.array([])

    # 2. Willekeurige-entry-baseline voor de 'long-bias'-toets
    rnd_spec = cfg["strategies"]["random_entry"]
    rnd = random_baseline(cfg, rnd_spec)

    # 3. Buy-and-hold over dezelfde OOS-periode
    _, research_end = period_bounds(cfg, "research")
    market = load_market(cfg, methods=("A",), build=False, until=research_end)
    w = windows(cfg)
    i0, _ = index_range(market, w[0][2], w[0][3])
    _, i1 = index_range(market, w[-1][2], w[-1][3])
    bh = buy_and_hold(market.candles.iloc[i0:i1 + 1], acc["start_equity_eur"])

    # 4. Status per strategie
    prev_json = RESULTS / "strategies.json"
    strategies_json = json.loads(prev_json.read_text()) if (args.only and prev_json.exists()) else {}
    rows, details = [], {}
    for sid, spec in specs.items():
        r = results[sid]
        oos = r["oos"][1.0]
        s = summarize(oos, acc["start_equity_eur"], acc["risk_pct"])
        dsr = deflated_sharpe(oos["r"].to_numpy(), n_trials, trial_sr) if len(oos) > 2 else {"dsr": np.nan}
        exc = excess_vs_random(oos, rnd)
        inst = load_class(spec["class"])(r["final"])
        if spec.get("baseline"):
            st = {"status": "baseline", "reasons": ["baseline, handelt nooit"]}
            ho = None
        else:
            ho = holdout.status(sid, inst)
            st0 = decide_status(oos, cfg["validation"])
            if args.holdout and st0["status"] == "candidate" and ho is None:
                print(f"  HOLD-OUT openen voor {sid} (eenmalig) ...")
                ho = holdout.open_once(sid, inst, lambda: run_holdout(spec, r["final"], cfg))
            st = decide_status(oos, cfg["validation"], ho, dsr["dsr"], exc)
        row = {"strategy": sid, "title": spec.get("title", sid), "status": st["status"], **s,
               "avg_r_0x": r["oos"][0.0]["r"].mean() if len(r["oos"][0.0]) else np.nan,
               "avg_r_2x": r["oos"][2.0]["r"].mean() if len(r["oos"][2.0]) else np.nan,
               "avg_r_3x": r["oos"][3.0]["r"].mean() if len(r["oos"][3.0]) else np.nan,
               "dsr": dsr["dsr"], "excess_vs_random": exc,
               "n_trials": int((all_trials["strategy"] == sid).sum()) if len(all_trials) else 0,
               "holdout_n": ho["n"] if ho else np.nan, "holdout_avg_r": ho["avg_r"] if ho else np.nan,
               "holdout_burned": bool(ho.get("burned")) if ho else False,
               "reasons": "; ".join(st["reasons"])}
        rows.append(row)
        details[sid] = {"summary": s, "by_year": r_by_year(oos), "chosen": r["chosen"], "final": r["final"],
                        "dsr": dsr, "holdout": ho, "status": st}
        strategies_json[sid] = {"class": spec["class"], "title": spec.get("title", sid), "status": st["status"],
                                "params": r["final"], "reasons": st["reasons"],
                                "backtest": {"n": s["n"], "winrate": s["winrate"], "avg_r": s["avg_r"],
                                             "max_dd_pct": s["max_dd_pct"],
                                             "std_r": float(oos["r"].std()) if len(oos) > 1 else None}}
        oos.to_csv(RESULTS / f"oos_{sid}.csv", index=False)

    lb = pd.DataFrame(rows)
    lb = pd.concat([lb, pd.DataFrame([{"strategy": "buy_and_hold", "title": "Buy-and-hold (kopen en vasthouden)",
                                       "status": "baseline", "return_pct": bh["return_pct"],
                                       "max_dd_pct": bh["max_dd_pct"],
                                       "reasons": "baseline: rendement zonder hefboom over dezelfde OOS-periode"}])],
                   ignore_index=True)
    if args.only and (RESULTS / "leaderboard.csv").exists():
        old = pd.read_csv(RESULTS / "leaderboard.csv")
        lb = pd.concat([old[~old["strategy"].isin(lb["strategy"])], lb], ignore_index=True)
    order = {"validated": 0, "candidate": 1, "rejected": 2, "baseline": 3}
    lb = lb.sort_values(["status", "avg_r"], key=lambda c: c.map(order) if c.name == "status" else -c.fillna(-9))
    lb.to_csv(RESULTS / "leaderboard.csv", index=False, float_format="%.4f")
    prev_json.write_text(json.dumps(strategies_json, indent=1, default=str))
    (RESULTS / "backtest.json").write_text(json.dumps(
        {"n_trials_total": n_trials, "random_baseline": {str(k): float(v) for k, v in rnd.groupby("direction")["r"].mean().items()},
         "random_baseline_n": len(rnd), "buy_and_hold": {k: v for k, v in bh.items() if k != "equity"},
         "oos_period": [str(w[0][2].date()), str(w[-1][3].date())], "details": details}, indent=1, default=str))
    print(lb[["strategy", "status", "n", "winrate", "avg_r", "avg_r_2x", "max_dd_pct", "dsr", "excess_vs_random",
              "holdout_avg_r", "reasons"]].to_string(index=False))


if __name__ == "__main__":
    main()
