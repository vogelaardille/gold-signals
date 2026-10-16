"""Ronde 4: research-run (alleen R4, 2005–2019). H4 wordt hier NOOIT geladen.

Draaien: .venv/bin/python -m fx.run
Uitvoer: research/round4/results/ (trials.csv, results.json, trades_*.csv) en
research/round4/research_results.md.
"""
import json
import time

import numpy as np
import pandas as pd

from fx import data, engine, families, stats

ROOT = data.ROOT
OUT = ROOT / "research/round4"


def _research_only(tr: pd.DataFrame, start: pd.Timestamp) -> pd.DataFrame:
    if tr is None or len(tr) == 0:
        return pd.DataFrame(columns=["entry_time", "exit_time", "direction", "net_bp", "gross_bp", "cost_bp", "r"])
    return tr[tr["entry_time"] >= start].reset_index(drop=True)


def _pool(parts: dict) -> pd.DataFrame:
    frames = [t.assign(pair=p) for p, t in parts.items() if len(t)]
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _mean(tr) -> float:
    return float(tr["net_bp"].mean()) if len(tr) else float("nan")


class Run:
    def __init__(self):
        self.cfg = cfg = data.load_config()
        p = cfg["periods"]
        self.start = pd.Timestamp(p["research_start"], tz="UTC")
        self.days = stats.research_days(p["research_start"], p["research_end"])
        s = cfg["stats"]
        self.idx = stats.bootstrap_index(len(self.days), s["bootstrap_n"], s["block_days"], s["seed"])
        self.px = {pair: engine.prices(data.research_data(cfg, pair)) for pair in cfg["pairs"]}
        self.slip = cfg["execution"]["slippage_pips"]
        self.trials = {}       # naam -> gepoolde trades (research)
        self.per_pair = {}     # naam -> {paar: trades}
        self.family = {}

    # ---------- runners per familie (geven {paar: trades}) ----------

    def f1(self, pair, legs, slip, shift=0):
        out = []
        for leg in legs:
            tr = families.f1_leg(self.px[pair], pair, self.cfg["f1"]["legs"][leg], self.cfg["pairs"][pair], slip, shift)
            out.append(_research_only(tr, self.start).assign(leg=leg))
        return pd.concat(out, ignore_index=True)

    def f2(self, level, variant, target, slip, offset=0.0):
        return {pair: _research_only(families.f2_run(self.px[pair], pair, self.cfg, level, variant, target, slip, offset),
                                     self.start) for pair in self.cfg["pairs"]}

    def f3(self, stop, target, slip):
        return {pair: _research_only(families.f3_run(self.px[pair], pair, self.cfg, stop, target, slip), self.start)
                for pair in self.cfg["pairs"]}

    # ---------- de 32 trials ----------

    def build_trials(self):
        f1 = self.cfg["f1"]
        for pair in self.cfg["pairs"]:
            for leg in f1["legs"]:
                self._add(f"F1|{pair}|{leg}", "F1", {pair: self.f1(pair, [leg], self.slip)})
            for combo, legs in f1["combos"].items():
                self._add(f"F1|{pair}|{combo}", "F1", {pair: self.f1(pair, legs, self.slip)})
        f2 = self.cfg["f2"]
        for level in f2["levels"]:
            for variant in f2["variants"]:
                for t in f2["targets_r"]:
                    self._add(f"F2|{level}|{variant}|{t}R", "F2", self.f2(level, variant, t, self.slip))
        f3 = self.cfg["f3"]
        for stop in f3["stops"]:
            for t in f3["targets_r"]:
                self._add(f"F3|{stop}|{'tijd' if t is None else f'{t}R'}", "F3", self.f3(stop, t, self.slip))

    def _add(self, name, fam, parts):
        self.per_pair[name] = parts
        self.trials[name] = _pool(parts)
        self.family[name] = fam

    # ---------- nulmodellen ----------

    def f2_null(self, level, variant, target):
        rng = np.random.default_rng(self.cfg["stats"]["seed"] + (0 if level == "00" else 1))
        offsets = families.f2_null_offsets(self.cfg, level, rng)
        return np.array([_mean(_pool(self.f2(level, variant, target, self.slip, off))) for off in offsets])

    def f3_null(self, stop, target):
        rng = np.random.default_rng(self.cfg["stats"]["seed"] + 10)
        preps = {pair: families.f3_null_prep(self.px[pair], self.cfg, stop) for pair in self.cfg["pairs"]}
        out = []
        for _ in range(self.cfg["f3"]["null_replicates"]):
            parts = {pair: _research_only(families.f3_null(self.px[pair], pair, self.cfg, target, self.slip, rng,
                                                           preps[pair]), self.start) for pair in self.cfg["pairs"]}
            out.append(_mean(_pool(parts)))
        return np.array(out)

    # ---------- placebo F1 (beschrijvend) ----------

    def f1_placebo(self, pair, legs):
        rows = {}
        for shift in range(-12, 12):
            tr = self.f1(pair, legs, self.slip, shift)
            rows[shift] = float(tr["gross_bp"].mean()) if len(tr) else None
        return rows


def subperiod_means(tr: pd.DataFrame, subperiods) -> list:
    t = pd.DatetimeIndex(tr["entry_time"])
    return [_mean(tr[(t >= pd.Timestamp(a, tz="UTC")) & (t < pd.Timestamp(b, tz="UTC"))]) for a, b in subperiods]


def main():
    t0 = time.time()
    R = Run()
    cfg = R.cfg
    print("trials bouwen ...", flush=True)
    R.build_trials()
    summaries = {k: stats.summarize(v, R.days, R.idx) for k, v in R.trials.items()}
    series = {k: stats.daily_series(v, R.days) for k, v in R.trials.items()}

    primaries = {
        "F1-EU": ("F1|EUR/USD|Europe", "F1"), "F1-TK": ("F1|USD/JPY|Tokyo", "F1"),
        "F2-B": ("F2|00|bounce|1R", "F2"), "F2-D": ("F2|00|breakout|2R", "F2"),
        "F3": ("F3|opposite|1R", "F3"),
    }
    s, ex = cfg["stats"], cfg["execution"]
    results = {"trials": summaries, "primaries": {}}
    for pname, (trial, fam) in primaries.items():
        print(f"{pname}: kosten, nulmodel, robuustheid ...", flush=True)
        tr = R.trials[trial]
        sm = summaries[trial]
        res = {"trial": trial, **{k: sm[k] for k in ("n_trades", "net_bp", "gross_bp", "cost_bp", "sharpe",
                                                     "boot_pos", "ci95_net_bp", "net_bp_without_best_year",
                                                     "best_year", "r", "hit_rate", "long_net_bp", "short_net_bp")}}
        res["subperiods_net_bp"] = subperiod_means(tr, cfg["periods"]["subperiods"])
        # kosten: slippage 0x / 3x en het retail-scenario (beschrijvend)
        if fam == "F1":
            pair, combo = trial.split("|")[1:]
            legs = cfg["f1"]["combos"][combo]
            costs = {m: _mean(R.f1(pair, legs, ex["slippage_pips"] * m)) for m in ex["slippage_multipliers"]}
            costs["retail"] = _mean(R.f1(pair, legs, ex["slippage_pips"] + ex["retail_extra_pips"]))
            res["gross_by_pair"] = {p: float(R.trials[f"F1|{p}|{combo}"]["gross_bp"].mean()) for p in cfg["pairs"]}
            res["net_by_pair"] = {p: float(R.trials[f"F1|{p}|{combo}"]["net_bp"].mean()) for p in cfg["pairs"]}
            res["by_leg_net_bp"] = {leg: float(tr.loc[tr.leg == leg, "net_bp"].mean()) for leg in legs}
            res["by_leg_gross_bp"] = {leg: float(tr.loc[tr.leg == leg, "gross_bp"].mean()) for leg in legs}
            res["placebo_gross_bp_by_shift_hours"] = R.f1_placebo(pair, legs)
        else:
            _, *conf = trial.split("|")
            if fam == "F2":
                level, variant, t = conf
                run = lambda slip: R.f2(level, variant, int(t[:-1]), slip)
            else:
                stop, t = conf
                run = lambda slip: R.f3(stop, None if t == "tijd" else int(t[:-1]), slip)
            costs = {m: _mean(_pool(run(ex["slippage_pips"] * m))) for m in ex["slippage_multipliers"]}
            costs["retail"] = _mean(_pool(run(ex["slippage_pips"] + ex["retail_extra_pips"])))
            res["net_by_pair"] = {p: _mean(v) for p, v in R.per_pair[trial].items()}
            target = None if t == "tijd" else int(t[:-1])
            null = R.f2_null(level, variant, target) if fam == "F2" else R.f3_null(stop, target)
            res["null_p95"] = float(np.nanpercentile(null, s["null_percentile"]))
            res["null_mean"] = float(np.nanmean(null))
            res["null_percentile_of_real"] = float((null < sm["net_bp"]).mean() * 100)
            grid = [k for k in R.trials if R.family[k] == fam]
            res["grid_share_positive"] = float(np.mean([summaries[k].get("net_bp", -1) > 0 for k in grid]))
        res["net_bp_by_slippage_multiplier"] = costs
        res["reality_check_p"] = stats.reality_check(series, trial, R.idx)

        checks = {
            "1_net_and_sharpe_positive": sm["net_bp"] > 0 and sm["sharpe"] > 0,
            "2_boot_pos_ge_80pct": sm["boot_pos"] >= s["pct_positive"],
            "3_min_trades": sm["n_trades"] >= s["min_trades"],
            "4a_subperiods_2_of_3": sum(x > 0 for x in res["subperiods_net_bp"]) >= 2,
            "4b_without_best_year": sm["net_bp_without_best_year"] > 0,
            "5_slippage_3x": costs[3] > 0,
        }
        if fam == "F1":
            checks["4c_gross_same_sign_2_of_3_pairs"] = sum(v > 0 for v in res["gross_by_pair"].values()) >= 2
        else:
            checks["4c_net_positive_2_of_3_pairs"] = sum(v > 0 for v in res["net_by_pair"].values()) >= 2
            checks["6_above_null_p95"] = sm["net_bp"] > res["null_p95"]
            checks["7_plateau_half_grid"] = res["grid_share_positive"] >= 0.5
        res["checks"] = checks
        res["status"] = "candidate" if all(checks.values()) else "rejected"
        too_good = (sm["sharpe"] > 1.5 or (fam == "F1" and sm["net_bp"] > 3)
                    or (fam != "F1" and (sm["r"] or 0) > 0.3))
        res["too_good_flag"] = bool(too_good)
        gross_series = stats.daily_series(tr.assign(net_bp=tr["gross_bp"]), R.days)
        res["gross_boot_pos"] = float((stats.bootstrap_mean(gross_series, R.idx) > 0).mean())
        if res["status"] == "candidate":
            res["verdict"] = "c"  # voordeel na kosten
        elif sm["gross_bp"] > 0 and res["gross_boot_pos"] >= 0.95:
            res["verdict"] = "b"  # bruto wel, netto niet
        else:
            res["verdict"] = "a"  # geen voordeel
        results["primaries"][pname] = res
        tr.to_csv(OUT / "results" / f"trades_{pname}.csv", index=False)

    rows = []
    for i, (k, v) in enumerate(summaries.items(), 1):
        rows.append({"trial": i, "id": k, "family": R.family[k], "n_trades": v.get("n_trades"),
                     "net_bp": v.get("net_bp"), "gross_bp": v.get("gross_bp"), "cost_bp": v.get("cost_bp"),
                     "sharpe": v.get("sharpe"), "boot_pos": v.get("boot_pos"), "r": v.get("r")})
    pd.DataFrame(rows).to_csv(OUT / "results/trials.csv", index=False)
    results["n_trials"] = len(rows)
    results["runtime_s"] = round(time.time() - t0)
    (OUT / "results/results.json").write_text(json.dumps(results, indent=1, default=float))
    write_markdown(results, rows)
    print(f"klaar in {results['runtime_s']} s")


def _f(x, nd=2):
    return "–" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def write_markdown(results, rows):
    out = ["# Ronde 4 – research-uitkomsten (R4, 2005–2019)", "",
           "Automatisch gemaakt door `python -m fx.run`. Kosten: echte bid/ask-spread + 0,1 pip slippage "
           "per kant. H4 (2020–2026) is **niet** geopend.", "",
           "## Primaire configuraties", "",
           "| | trial | trades | netto bp/trade | bruto bp | kosten bp | Sharpe | bootstrap > 0 | 3× slip | retail | RC p | status | oordeel |",
           "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    for k, r in results["primaries"].items():
        c = r["net_bp_by_slippage_multiplier"]
        out.append(f"| {k} | `{r['trial']}` | {r['n_trades']} | {_f(r['net_bp'])} | {_f(r['gross_bp'])} | "
                   f"{_f(r['cost_bp'])} | {_f(r['sharpe'])} | {r['boot_pos']:.0%} | {_f(c['3'] if '3' in c else c[3])} | "
                   f"{_f(c['retail'])} | {_f(r['reality_check_p'])} | **{r['status']}** | ({r['verdict']}) |")
    out += ["", "## Controles per primaire configuratie (PLAN4 §9)", ""]
    for k, r in results["primaries"].items():
        failed = [c for c, ok in r["checks"].items() if not ok]
        out.append(f"- **{k}**: subperiodes {[_f(x) for x in r['subperiods_net_bp']]} bp; zonder beste jaar "
                   f"({r['best_year']}) {_f(r['net_bp_without_best_year'])} bp; per paar "
                   f"{ {p: _f(v) for p, v in r['net_by_pair'].items()} }"
                   + (f"; nulmodel p95 {_f(r['null_p95'])} bp (echt op percentiel {_f(r['null_percentile_of_real'], 0)})"
                      if "null_p95" in r else f"; bruto per paar { {p: _f(v) for p, v in r['gross_by_pair'].items()} }")
                   + f". Niet gehaald: {', '.join(failed) if failed else 'geen'}.")
    out += ["", "## Alle 32 trials", "", "| # | trial | trades | netto bp | bruto bp | Sharpe | bootstrap > 0 | R |",
            "|---:|---|---:|---:|---:|---:|---:|---:|"]
    for r in rows:
        out.append(f"| {r['trial']} | `{r['id']}` | {r['n_trades']} | {_f(r['net_bp'])} | {_f(r['gross_bp'])} | "
                   f"{_f(r['sharpe'])} | {_f(r['boot_pos'] * 100 if r['boot_pos'] is not None else None, 0)}% | {_f(r['r'])} |")
    (OUT / "research_results.md").write_text("\n".join(out) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
