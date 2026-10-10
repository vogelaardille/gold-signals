"""Ronde 2: walk-forward voor families F1-F4 binnen research R2 (zie PLAN2.md).

Draaien: .venv/bin/python -m goldsignals.round2.run
Output: research/round2/results/ (trials.csv, oos_<familie>.csv, results.json)

Data na het begin van hold-out H2 wordt hier NIET geladen. H2 openen kan alleen via
goldsignals.round2.holdout (eenmalig per strategie, alleen voor candidates).
"""
import json
import math
import time
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

from goldsignals.config import load_config, project_path
from goldsignals.research.stats import bootstrap_mean
from goldsignals.round2 import families as fam
from goldsignals.round2.engine import simulate, with_costs
from goldsignals.round2.indicators import bars

OUT = project_path("research/round2/results")
FAMILIES = ["F1", "F2", "F3", "F4"]
SLOW_TF = {"1d"}


def costs(cfg, mult):
    c = cfg["round2"]["costs"]
    return mult * (c["spread_usd"] + 2 * c["slippage_usd"])


def month_id(times) -> np.ndarray:
    t = pd.DatetimeIndex(times)
    return np.asarray(t.year * 12 + t.month)


# ---------------------------------------------------------------------------
# 1. Elke variant één keer simuleren over de hele research-periode
# ---------------------------------------------------------------------------

_B = {}


def _init(bars_by_tf):
    _B.update(bars_by_tf)


def run_variant(args):
    v, cfg = args
    b = _B[fam.timeframe_of(v)]
    s = fam.signals(b, v, cfg)
    start = pd.Timestamp(cfg["round2"]["periods"]["research_start"], tz="UTC")
    s.entry = np.where(b["close_time"].to_numpy() > start, s.entry, 0).astype(np.int8)   # warm-up: geen trades
    t = simulate(b, s)
    t["entry_time"] = b.index[t["entry_i"].to_numpy()]
    t["exit_time"] = b["close_time"].to_numpy()[t["exit_i"].to_numpy()]
    t["year"] = t["entry_time"].dt.year
    for m in cfg["round2"]["costs"]["multipliers"]:
        t[f"r{m}x"] = with_costs(t, costs(cfg, m))
    t["r_gross"] = t["pnl_oz"] / t["risk_oz"]
    t["rr"] = np.nan
    return fam.variant_id(v), t


# ---------------------------------------------------------------------------
# 2. Walk-forward selectie
# ---------------------------------------------------------------------------

def is_slow(v) -> bool:
    return fam.timeframe_of(v) in SLOW_TF


def per_trade_sharpe(r):
    r = np.asarray(r, float)
    return float(r.mean() / r.std(ddof=1)) if len(r) > 2 and r.std(ddof=1) > 0 else np.nan


def walk_forward(family, vs, trades, cfg, trial_log):
    w = cfg["round2"]["walkforward"]
    mins = cfg["round2"]["min_train_trades"]
    oos, chosen = [], []
    for y in range(w["first_test_year"], w["last_test_year"] + 1):
        best, best_val = None, -np.inf
        for v in vs:
            vid = fam.variant_id(v)
            t = trades[vid]
            tr = t[(t["year"] >= y - w["train_years"]) & (t["year"] < y)]
            need = mins["slow"] if is_slow(v) else mins["fast"]
            r = tr["r1x"].to_numpy()
            val = float(r.mean()) if len(r) >= need else -np.inf
            trial_log.append({"family": family, "test_year": y, "variant": vid, "n": len(r),
                              "avg_r": float(r.mean()) if len(r) else np.nan, "sharpe": per_trade_sharpe(r),
                              "valid": len(r) >= need, "min_trades": need})
            if val > best_val:
                best, best_val = v, val
        if best is None or not np.isfinite(best_val):
            chosen.append({"test_year": y, "variant": None})
            continue
        t = trades[fam.variant_id(best)]
        oos.append(t[t["year"] == y].assign(variant=fam.variant_id(best)))
        chosen.append({"test_year": y, "variant": fam.variant_id(best), "train_avg_r": best_val})
    oos = pd.concat(oos, ignore_index=True) if oos else pd.DataFrame()
    return oos, chosen


def final_variant(vs, trades, cfg):
    """Zelfde selectie op de laatste 4 jaar van R2 (2015-2018): parameters voor H2."""
    w = cfg["round2"]["walkforward"]
    y = w["last_test_year"] + 1
    mins = cfg["round2"]["min_train_trades"]
    best, best_val = None, -np.inf
    for v in vs:
        t = trades[fam.variant_id(v)]
        r = t[(t["year"] >= y - w["train_years"]) & (t["year"] < y)]["r1x"].to_numpy()
        need = mins["slow"] if is_slow(v) else mins["fast"]
        if len(r) >= need and r.mean() > best_val:
            best, best_val = v, float(r.mean())
    return best, best_val


# ---------------------------------------------------------------------------
# 3. Random entries met exact dezelfde exits
# ---------------------------------------------------------------------------

def random_same_exit(oos, chosen, vs_by_id, bars_by_tf, cfg, n_rep, rng):
    """Per test-jaar: zelfde aantal entries en long/short-verhouding als de strategie, op
    willekeurige candles in dat jaar, met de exit-regels van de in dat jaar gekozen variant."""
    if oos.empty:
        return np.array([])
    prepared = []
    for ch in chosen:
        if ch["variant"] is None:
            continue
        y, v = ch["test_year"], vs_by_id[ch["variant"]]
        b = bars_by_tf[fam.timeframe_of(v)]
        s = fam.signals(b, v, cfg)
        ct = b["close_time"]
        in_year = np.flatnonzero((b.index.year == y) & np.isfinite(s.stop_dist) & (s.stop_dist > 0))
        in_year = in_year[in_year < len(b) - 1]
        ty = oos[oos["year"] == y]
        if s.dir_from_target:
            side = np.sign(s.target_level[in_year] - b["close"].to_numpy()[in_year])
            ok = side != 0
            in_year, side = in_year[ok], side[ok]
        else:
            side = None
        prepared.append((y, b, s, in_year, side, len(ty), (ty["direction"] == 1).mean() if len(ty) else 0.5))
    means = []
    for _ in range(n_rep):
        rs = []
        for y, b, s, cand, side, k, long_share in prepared:
            if k == 0 or len(cand) == 0:
                continue
            pick = rng.choice(len(cand), size=min(k, len(cand)), replace=False)
            idx = cand[pick]
            if side is not None:
                d = side[pick]
            else:
                n_long = int(round(k * long_share))
                d = np.r_[np.ones(n_long), -np.ones(len(idx) - n_long)]
                rng.shuffle(d)
            e = np.zeros(len(b), np.int8)
            e[idx] = d
            t = simulate(b, s, entries=e)
            t = t[b.index[t["entry_i"].to_numpy()].year == y]
            rs.append(with_costs(t, costs(cfg, 1)))
        allr = np.concatenate(rs) if rs else np.array([])
        means.append(allr.mean() if len(allr) else np.nan)
    return np.array(means)


# ---------------------------------------------------------------------------
# 4. Kengetallen
# ---------------------------------------------------------------------------

def equity_stats(t: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, risk_pct=1.0) -> dict:
    """Maandrendementen uit gesloten trades (1% risico, samengesteld): Sharpe, CAGR, max DD, Calmar."""
    months = pd.period_range(start.tz_localize(None), (end - pd.Timedelta(days=1)).tz_localize(None), freq="M")
    ret = pd.Series(0.0, index=months)
    if len(t):
        g = (1 + t["r1x"] * risk_pct / 100).groupby(pd.DatetimeIndex(t["exit_time"]).tz_localize(None).to_period("M")).prod() - 1
        ret.loc[g.index.intersection(ret.index)] = g[g.index.intersection(ret.index)]
    eq = (1 + ret).cumprod()
    return _stats_from_monthly(ret, eq)


def _stats_from_monthly(ret, eq):
    years = len(ret) / 12
    cagr = eq.iloc[-1] ** (1 / years) - 1 if years > 0 else np.nan
    dd = float(((eq - eq.cummax()) / eq.cummax()).min())
    sharpe = float(ret.mean() / ret.std(ddof=1) * math.sqrt(12)) if ret.std(ddof=1) > 0 else np.nan
    return {"cagr_pct": float(cagr * 100), "max_dd_pct": dd * 100, "sharpe": sharpe,
            "calmar": float(cagr / abs(dd)) if dd < 0 else np.nan, "total_return_pct": float(eq.iloc[-1] * 100 - 100)}


def buy_hold_stats(daily: pd.DataFrame, start, end) -> dict:
    d = daily[(daily["close_time"] > start) & (daily["close_time"] <= end)]
    m = d.set_index(pd.DatetimeIndex(d["close_time"]).tz_localize(None))["close"].resample("ME").last()
    ret = m.pct_change().dropna()
    eq = (1 + ret).cumprod()
    return _stats_from_monthly(ret, eq)


def summarize(t: pd.DataFrame, cfg, rng) -> dict:
    if t.empty:
        return {"n": 0}
    out = {"n": len(t), "n_long": int((t["direction"] == 1).sum()), "n_short": int((t["direction"] == -1).sum())}
    for m in cfg["round2"]["costs"]["multipliers"]:
        out[f"avg_r_{m}x"] = float(t[f"r{m}x"].mean())
    out["avg_r_gross"] = float(t["r_gross"].mean())
    out["ci"] = bootstrap_mean(t["r1x"], month_id(t["entry_time"]), cfg["round2"]["bootstrap_n"], rng)
    for d, name in ((1, "long"), (-1, "short")):
        sub = t[t["direction"] == d]
        out[f"avg_r_{name}"] = float(sub["r1x"].mean()) if len(sub) else np.nan
        out[f"ci_{name}"] = bootstrap_mean(sub["r1x"], month_id(sub["entry_time"]), cfg["round2"]["bootstrap_n"], rng) if len(sub) > 5 else None
    out["by_year"] = {int(y): {"n": len(g), "avg_r": float(g["r1x"].mean()), "total_r": float(g["r1x"].sum())}
                      for y, g in t.groupby("year")}
    # win rate alleen ter informatie, naast de break-even win rate bij de werkelijke R:R
    wins = t["r1x"] > 0
    avg_win = t.loc[wins, "r1x"].mean() if wins.any() else np.nan
    avg_loss = -t.loc[~wins, "r1x"].mean() if (~wins).any() else np.nan
    out["winrate"] = float(wins.mean() * 100)
    out["avg_win_r"], out["avg_loss_r"] = float(avg_win), float(avg_loss)
    out["breakeven_winrate"] = float(100 * avg_loss / (avg_win + avg_loss)) if np.isfinite(avg_win) and np.isfinite(avg_loss) else np.nan
    by = out["by_year"]
    best = max(by, key=lambda y: by[y]["total_r"])
    out["total_r"] = float(t["r1x"].sum())
    out["total_r_without_best_year"] = float(sum(v["total_r"] for y, v in by.items() if y != best))
    out["losing_years"] = int(sum(1 for v in by.values() if v["total_r"] < 0))
    return out


def dsr(r, n_trials, trial_sharpes, mild_noise=None):
    """Deflated Sharpe (ronde 1-formule). mild_noise: gemiddelde 1/n van de trials -> milde variant."""
    r = np.asarray(r, float)
    if len(r) < 3 or r.std(ddof=1) == 0:
        return np.nan, np.nan
    sr = r.mean() / r.std(ddof=1)
    ts = np.asarray(trial_sharpes, float)
    ts = ts[np.isfinite(ts)]
    var = ts.var(ddof=1)
    if mild_noise is not None:
        var = max(var - mild_noise, 0.0) + 1 / len(r)
    g = 0.5772156649
    N = max(int(n_trials), 2)
    sr0 = math.sqrt(var) * ((1 - g) * norm.ppf(1 - 1 / N) + g * norm.ppf(1 - 1 / (N * math.e)))
    denom = math.sqrt(max(1 - skew(r) * sr + (kurtosis(r, fisher=False) - 1) / 4 * sr ** 2, 1e-12))
    return float(norm.cdf((sr - sr0) * math.sqrt(len(r) - 1) / denom)), float(sr0)


def clean(o):
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (float, np.floating)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


def main():
    cfg = load_config()
    r2 = cfg["round2"]
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(r2["seed"])
    t0 = time.time()
    end = pd.Timestamp(r2["periods"]["holdout_start"], tz="UTC")     # hold-out niet laden
    bars_by_tf = {tf: bars(tf, end, cfg) for tf in ("1d", "4h", "1h", "15m")}
    for tf, b in bars_by_tf.items():
        assert b["close_time"].max() <= end, f"hold-out-data in {tf}!"
    print(f"Bars geladen ({time.time() - t0:.0f}s): " + ", ".join(f"{k} {len(v)}" for k, v in bars_by_tf.items()))

    vs_all = {f: fam.variants(cfg, f) for f in FAMILIES}
    jobs = [(v, cfg) for f in FAMILIES for v in vs_all[f]]
    with ProcessPoolExecutor(cfg["snapshots"]["workers"], initializer=_init, initargs=(bars_by_tf,)) as ex:
        trades = dict(ex.map(run_variant, jobs))
    print(f"{len(trades)} varianten gesimuleerd ({time.time() - t0:.0f}s)")

    trial_log, results = [], {}
    oos_by_family, chosen_by_family = {}, {}
    for f in FAMILIES:
        oos, chosen = walk_forward(f, vs_all[f], trades, cfg, trial_log)
        oos_by_family[f], chosen_by_family[f] = oos, chosen
        oos.to_csv(OUT / f"oos_{f}.csv", index=False)
    trials = pd.DataFrame(trial_log)
    trials.to_csv(OUT / "trials.csv", index=False)

    # Correctie: alle trials van ronde 1 en 2, plus de opening van H1
    r1 = pd.read_csv(project_path("research/results/trials.csv"))
    n_trials = r2["round1_trials"] + r2["burned_holdout_openings"] + len(trials)
    valid_sh = np.r_[r1.loc[r1["n"] >= 15, "sharpe"].dropna().to_numpy(),
                     trials.loc[trials["valid"], "sharpe"].dropna().to_numpy()]
    noise = float(np.mean(np.r_[1 / r1.loc[r1["n"] >= 15, "n"].to_numpy(), 1 / trials.loc[trials["valid"], "n"].to_numpy()]))

    w = r2["walkforward"]
    oos_start = pd.Timestamp(f"{w['first_test_year']}-01-01", tz="UTC")
    oos_end = pd.Timestamp(f"{w['last_test_year'] + 1}-01-01", tz="UTC")
    bh = buy_hold_stats(bars_by_tf["1d"], oos_start, oos_end)
    vs_by_id = {fam.variant_id(v): v for f in FAMILIES for v in vs_all[f]}

    for f in FAMILIES:
        oos = oos_by_family[f]
        s = summarize(oos, cfg, rng)
        s["equity"] = equity_stats(oos, oos_start, oos_end) if len(oos) else None
        d, sr0 = dsr(oos["r1x"].to_numpy(), n_trials, valid_sh) if len(oos) else (np.nan, np.nan)
        dm, _ = dsr(oos["r1x"].to_numpy(), n_trials, valid_sh, mild_noise=noise) if len(oos) else (np.nan, np.nan)
        s.update(dsr=d, dsr_sr0=sr0, dsr_mild=dm, sharpe_per_trade=per_trade_sharpe(oos["r1x"]) if len(oos) else np.nan)
        rnd = random_same_exit(oos, chosen_by_family[f], vs_by_id, bars_by_tf, cfg, r2["random_replicates"], rng)
        s["random_mean"] = float(np.nanmean(rnd)) if len(rnd) else np.nan
        s["random_p95"] = float(np.nanpercentile(rnd, 95)) if len(rnd) else np.nan
        s["random_pct"] = float((rnd < s.get("avg_r_1x", np.nan)).mean() * 100) if len(rnd) else np.nan
        slow = all(is_slow(vs_by_id[c["variant"]]) for c in chosen_by_family[f] if c["variant"])
        s["slow"] = slow
        fv, fval = final_variant(vs_all[f], trades, cfg)
        s["final_variant"], s["final_train_avg_r"] = (fam.variant_id(fv) if fv else None), fval
        s["chosen"] = chosen_by_family[f]
        # Beschrijvend: elke variant over alle test-jaren (robuustheid van de familie)
        allv = []
        for v in vs_all[f]:
            t = trades[fam.variant_id(v)]
            t = t[(t["year"] >= w["first_test_year"]) & (t["year"] <= w["last_test_year"])]
            allv.append({"variant": fam.variant_id(v), "n": len(t),
                         "avg_r_1x": float(t["r1x"].mean()) if len(t) else np.nan,
                         "avg_r_long": float(t.loc[t["direction"] == 1, "r1x"].mean()) if (t["direction"] == 1).any() else np.nan,
                         "avg_r_short": float(t.loc[t["direction"] == -1, "r1x"].mean()) if (t["direction"] == -1).any() else np.nan})
        s["all_variants"] = allv
        s["status"], s["reasons"] = status(s, cfg)
        results[f] = s
        print(f"{f}: n={s.get('n')} gem.R={s.get('avg_r_1x', float('nan')):+.3f} "
              f"[{s['ci']['lo'] if s.get('ci') else float('nan'):+.3f}; {s['ci']['hi'] if s.get('ci') else float('nan'):+.3f}] "
              f"random p95={s['random_p95']:+.3f} DSR={s['dsr']:.2f} -> {s['status']} ({time.time() - t0:.0f}s)")

    meta = {"n_trials_round2": len(trials), "n_trials_total": n_trials, "buy_and_hold": bh,
            "oos_period": [str(oos_start.date()), str(oos_end.date())],
            "bars": {k: [str(v.index[0]), str(v.index[-1]), len(v)] for k, v in bars_by_tf.items()}}
    (OUT / "results.json").write_text(json.dumps(clean({"meta": meta, "families": results}), indent=1))
    print(f"Klaar ({time.time() - t0:.0f}s)")


def status(s, cfg) -> tuple:
    """candidate / rejected volgens PLAN2 §8 (validated pas na H2, zie holdout.py)."""
    r2 = cfg["round2"]
    reasons = []
    if s.get("n", 0) == 0:
        return "rejected", ["geen trades"]
    need = r2["min_oos_trades"]["slow"] if s["slow"] else r2["min_oos_trades"]["fast"]
    ok = True
    if s["n"] < need:
        ok = False
        reasons.append(f"te weinig trades ({s['n']} < {need})")
    if not s["avg_r_1x"] > 0:
        ok = False
        reasons.append(f"gem. R na kosten niet positief ({s['avg_r_1x']:+.3f})")
    if not s["total_r_without_best_year"] > 0:
        ok = False
        reasons.append(f"zonder beste jaar niet positief ({s['total_r_without_best_year']:+.1f}R)")
    if not ok:
        return "rejected", reasons
    reasons = ["voldoet aan candidate-eisen"] + (["traag: kan niet validated worden zonder forward paper trading"] if s["slow"] else [])
    return "candidate", reasons


if __name__ == "__main__":
    main()
