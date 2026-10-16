"""Ronde 5: research-run (R5: EUR/USD, GBP/USD, USD/JPY, 2005–2019). PLAN5.

Laadt NOOIT de bevestigingsparen (C5) en nooit data van 2020 of later.
Draaien: .venv/bin/python -m fx.run5
Uitvoer: research/round5/results/ en research/round5/research_results.md
"""
import json
import time

import numpy as np
import pandas as pd

from fx import data, engine, momentum, stats
from fx.run import _f, _mean, _pool, subperiod_means

OUT = data.ROOT / "research/round5"


class Ctx:
    """Data en instellingen voor één set paren in één periode."""

    def __init__(self, cfg, pairs: dict, start: str, end: str, since: str):
        self.cfg, self.pairs = cfg, pairs
        self.start = pd.Timestamp(start, tz="UTC")
        self.days = stats.research_days(start, end)
        s = cfg["stats"]
        self.idx = stats.bootstrap_index(len(self.days), s["bootstrap_n"], s["block_days"], s["seed"])
        until = pd.Timestamp(end, tz="UTC")
        self.px = {p: engine.prices(data.load_pair(cfg, p, until=until, since=pd.Timestamp(since, tz="UTC")))
                   for p in pairs}
        self.slip = cfg["execution"]["slippage_pips"]
        self._g2 = {}

    def only(self, tr):
        return tr[tr["entry_time"] >= self.start].reset_index(drop=True) if len(tr) else tr

    def g1(self, window, slip=None, rng=None):
        out = {}
        for p, pip in self.pairs.items():
            st = momentum.g1_setups(self.px[p]["time"], self.px[p]["close"], self.px[p]["open"],
                                    self.cfg["round5"]["g1"]["day_open_ny_hour"], *window)
            d = st["dir"].to_numpy() if rng is None else rng.permutation(st["dir"].to_numpy())
            tr = engine.simulate(self.px[p], st["entry"].to_numpy(), d, pip, self.slip if slip is None else slip,
                                 momentum.base_is_usd(p), exit_idx=st["exit"].to_numpy())
            out[p] = self.only(tr)
        return out

    def g2_setups(self, anchor, m):
        key = (anchor, m)
        if key not in self._g2:
            g2, ex = self.cfg["round5"]["g2"], self.cfg["execution"]
            tz, hour = g2["anchors"][anchor]
            self._g2[key] = {}
            for p in self.pairs:
                b = momentum.g2_bands(self.px[p], tz, hour, g2["lookback_days"], g2["min_days"],
                                      ex["force_exit_ny_hour"])
                self._g2[key][p] = momentum.g2_trades(self.px[p], b, m, ex["no_entry_ny_hours"])
        return self._g2[key]

    def g2(self, anchor, m, slip=None, rng=None):
        out = {}
        for p, pip in self.pairs.items():
            st = self.g2_setups(anchor, m)[p]
            d = None if rng is None else rng.choice([-1, 1], size=len(st))
            out[p] = self.only(momentum.g2_run(self.px[p], p, pip, self.slip if slip is None else slip, st, d))
        return out


def trial_defs(cfg) -> dict:
    r5 = cfg["round5"]
    defs = {}
    for w in r5["g1"]["windows"]:
        defs[f"G1|{w[0]}-{w[1]}NY"] = ("G1", {"window": tuple(w)})
    for a in r5["g2"]["anchors"]:
        for m in r5["g2"]["multipliers"]:
            defs[f"G2|{a}|m{m}"] = ("G2", {"anchor": a, "m": m})
    return defs


def primary_ids(cfg) -> dict:
    r5 = cfg["round5"]
    p1, p2 = r5["g1"]["primary"], r5["g2"]["primary"]
    return {"G1": f"G1|{p1[0]}-{p1[1]}NY", "G2": f"G2|{p2['anchor']}|m{p2['m']}"}


def run_trial(C: Ctx, fam, kw, slip=None, rng=None):
    return C.g1(kw["window"], slip, rng) if fam == "G1" else C.g2(kw["anchor"], kw["m"], slip, rng)


def null_means(C: Ctx, fam, kw, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = C.cfg["round5"]["g1" if fam == "G1" else "g2"]["null_replicates"]
    return np.array([_mean(_pool(run_trial(C, fam, kw, rng=rng))) for _ in range(n)])


def evaluate_primary(C: Ctx, trials: dict, defs: dict, trial: str, series: dict = None) -> dict:
    """Alle meetwaarden en controles van één primaire configuratie in context C."""
    cfg, ex, s = C.cfg, C.cfg["execution"], C.cfg["stats"]
    fam, kw = defs[trial]
    parts = trials[trial]
    tr = _pool(parts)
    sm = stats.summarize(tr, C.days, C.idx)
    res = {"trial": trial, **{k: sm.get(k) for k in ("n_trades", "net_bp", "gross_bp", "cost_bp", "sharpe", "boot_pos",
                                                     "ci95_net_bp", "best_year", "net_bp_without_best_year",
                                                     "hit_rate", "long_net_bp", "short_net_bp", "net_bp_by_year")}}
    res["subperiods_net_bp"] = subperiod_means(tr, cfg["periods"]["subperiods"])
    res["net_by_pair"] = {p: _mean(v) for p, v in parts.items()}
    costs = {m: _mean(_pool(run_trial(C, fam, kw, ex["slippage_pips"] * m))) for m in (0, 2, 3)}
    costs[1] = sm["net_bp"]
    costs["retail"] = _mean(_pool(run_trial(C, fam, kw, ex["slippage_pips"] + ex["retail_extra_pips"])))
    res["net_bp_by_slippage_multiplier"] = costs
    null = null_means(C, fam, kw, s["seed"] + (1 if fam == "G1" else 2))
    res["null_p95"] = float(np.nanpercentile(null, s["null_percentile"]))
    res["null_mean"] = float(np.nanmean(null))
    res["null_percentile_of_real"] = float((null < sm["net_bp"]).mean() * 100)
    gross = stats.daily_series(tr.assign(net_bp=tr["gross_bp"]), C.days)
    res["gross_boot_pos"] = float((stats.bootstrap_mean(gross, C.idx) > 0).mean())
    if series is not None:
        res["reality_check_p"] = stats.reality_check(series, trial, C.idx)
    return res


def research_checks(res: dict, trials_summary: dict, fam: str, s: dict) -> dict:
    grid = [k for k in trials_summary if k.startswith(fam)]
    return {
        "1_net_and_sharpe_positive": res["net_bp"] > 0 and res["sharpe"] > 0,
        "2_boot_pos_ge_80pct": res["boot_pos"] >= s["pct_positive"],
        "3_min_trades": res["n_trades"] >= s["min_trades"],
        "4a_subperiods_2_of_3": sum(x > 0 for x in res["subperiods_net_bp"]) >= 2,
        "4b_without_best_year": res["net_bp_without_best_year"] > 0,
        "4c_net_positive_2_of_3_pairs": sum(v > 0 for v in res["net_by_pair"].values()) >= 2,
        "5_slippage_3x": res["net_bp_by_slippage_multiplier"][3] > 0,
        "6_above_null_p95": res["net_bp"] > res["null_p95"],
        "7_plateau_half_grid": np.mean([trials_summary[k].get("net_bp", -1) > 0 for k in grid]) >= 0.5,
    }


def main():
    t0 = time.time()
    cfg = data.load_config()
    p, r5, s = cfg["periods"], cfg["round5"], cfg["stats"]
    C = Ctx(cfg, r5["research_pairs"], p["research_start"], p["research_end"], p["warmup_start"])
    defs = trial_defs(cfg)
    print("trials ...", flush=True)
    trials = {k: run_trial(C, fam, kw) for k, (fam, kw) in defs.items()}
    summaries = {k: stats.summarize(_pool(v), C.days, C.idx) for k, v in trials.items()}
    series = {k: stats.daily_series(_pool(v), C.days) for k, v in trials.items()}
    results = {"trials": summaries, "primaries": {}}
    for fam, trial in primary_ids(cfg).items():
        print(f"{fam}: kosten, nulmodel, robuustheid ...", flush=True)
        res = evaluate_primary(C, trials, defs, trial, series)
        res["checks"] = research_checks(res, summaries, fam, s)
        res["status"] = "candidate" if all(res["checks"].values()) else "rejected"
        res["verdict"] = ("c" if res["status"] == "candidate" else
                          "b" if res["gross_bp"] > 0 and res["gross_boot_pos"] >= 0.95 else "a")
        res["too_good_flag"] = bool(res["sharpe"] > 1.5 or res["net_bp"] > 3)
        results["primaries"][fam] = res
        _pool(trials[trial]).to_csv(OUT / f"results/trades_{fam}.csv", index=False)
    rows = [{"trial": i, "id": k, "family": k[:2], "n_trades": v.get("n_trades"), "net_bp": v.get("net_bp"),
             "gross_bp": v.get("gross_bp"), "cost_bp": v.get("cost_bp"), "sharpe": v.get("sharpe"),
             "boot_pos": v.get("boot_pos")} for i, (k, v) in enumerate(summaries.items(), 1)]
    pd.DataFrame(rows).to_csv(OUT / "results/trials.csv", index=False)
    results["runtime_s"] = round(time.time() - t0)
    (OUT / "results/results.json").write_text(json.dumps(results, indent=1, default=float))
    write_markdown(results, rows)
    print(f"klaar in {results['runtime_s']} s")


def write_markdown(results, rows):
    out = ["# Ronde 5 – research-uitkomsten (R5: EUR/USD, GBP/USD, USD/JPY, 2005–2019)", "",
           "Automatisch gemaakt door `python -m fx.run5`. Kosten: echte bid/ask-spread + 0,1 pip slippage per kant. "
           "Bevestigingsparen (C5) en 2020–2026 zijn **niet** geladen.", "",
           "## Primaire configuraties", "",
           "| | trial | trades | netto bp/trade | bruto bp | kosten bp | Sharpe | bootstrap > 0 | 3× slip | retail | "
           "nulmodel p95 | RC p | status | oordeel |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for k, r in results["primaries"].items():
        c = r["net_bp_by_slippage_multiplier"]
        out.append(f"| {k} | `{r['trial']}` | {r['n_trades']} | {_f(r['net_bp'])} | {_f(r['gross_bp'])} | "
                   f"{_f(r['cost_bp'])} | {_f(r['sharpe'])} | {r['boot_pos']:.0%} | {_f(c[3])} | {_f(c['retail'])} | "
                   f"{_f(r['null_p95'])} | {_f(r['reality_check_p'])} | **{r['status']}** | ({r['verdict']}) |")
    out += ["", "## Controles (PLAN5 §8)", ""]
    for k, r in results["primaries"].items():
        failed = [c for c, ok in r["checks"].items() if not ok]
        out.append(f"- **{k}**: subperiodes {[_f(x) for x in r['subperiods_net_bp']]} bp; zonder beste jaar "
                   f"({r['best_year']}) {_f(r['net_bp_without_best_year'])} bp; per paar "
                   f"{ {p: _f(v) for p, v in r['net_by_pair'].items()} }; long/short {_f(r['long_net_bp'])}/"
                   f"{_f(r['short_net_bp'])} bp; echt op percentiel {_f(r['null_percentile_of_real'], 0)} van het "
                   f"nulmodel. Niet gehaald: {', '.join(failed) if failed else 'geen'}.")
    out += ["", "## Alle 6 trials", "", "| # | trial | trades | netto bp | bruto bp | Sharpe | bootstrap > 0 |",
            "|---:|---|---:|---:|---:|---:|---:|"]
    for r in rows:
        out.append(f"| {r['trial']} | `{r['id']}` | {r['n_trades']} | {_f(r['net_bp'])} | {_f(r['gross_bp'])} | "
                   f"{_f(r['sharpe'])} | {_f((r['boot_pos'] or 0) * 100, 0)}% |")
    (OUT / "research_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
