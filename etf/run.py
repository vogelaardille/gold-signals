"""Ronde 3: research-run (2005-01 – 2020-12). PLAN3 §4–§10.

Rekent alle 25 trials, de baselines, bootstrap-intervallen, de Reality Check, willekeurige
timing en de robuustheidschecks door, en bepaalt de status van de 4 primaire configuraties.
Laadt ALLEEN data t/m 2020-12 (data.research_prices / until = research_end).

Draaien: .venv/bin/python -m etf.run      (~ enkele minuten)
Uitvoer: research/round3/results/
"""
import json

import numpy as np
import pandas as pd

from etf import data, portfolio, rules, stats
from etf.data import ROOT

OUT = ROOT / "research/round3/results"


# ---------------------------------------------------------------------------
# Context: alle data voor één periode en één universum
# ---------------------------------------------------------------------------

class Context:
    """Koersen, rendementen, cash en signaaldagen voor een periode [start, end).
    until = laatste toegestane datum (exclusief) voor het laden van data."""

    def __init__(self, cfg, tickers, start, end, until, rename=None, rets=None, cash=None, rf=None):
        self.cfg = cfg
        self.start, self.end = pd.Timestamp(start), pd.Timestamp(end)
        prices = data.price_table(tickers, cfg, until)
        if rename:
            prices = prices.rename(columns=rename)
        self.prices = prices
        self.rets = prices.pct_change() if rets is None else rets
        self.cash = data.cash_daily(cfg, prices.index, until=until) if cash is None else cash
        self.me = portfolio.month_end_prices(prices)
        self.avail = rules.available(self.me, cfg["min_month_ends"])
        first_sig = (self.start.to_period("M") - 1)
        self.sig = self.me.index[(self.me.index.to_period("M") >= first_sig) & (self.me.index < self.end)]
        self.until = until
        self.rf = portfolio.monthly_cash(self.cash, self.start, self.end) if rf is None else rf
        self._cash_l = {}

    def cash_lookback(self, lookback):
        if lookback not in self._cash_l:
            self._cash_l[lookback] = data.cash_known_at(self.cfg, self.sig, lookback, self.until)
        return self._cash_l[lookback]

    def assets(self):
        return list(self.prices.columns)


# ---------------------------------------------------------------------------
# Configuraties (trials)
# ---------------------------------------------------------------------------

def trial_list(cfg) -> list:
    f = cfg["families"]
    out = [{"id": f"F1_N{n}", "family": "F1", "n": n} for n in f["F1_trend"]["sma_months"]]
    out += [{"id": f"F2_k{k}_L{L}", "family": "F2", "k": k, "L": L}
            for k in f["F2_dual_momentum"]["top_k"] for L in f["F2_dual_momentum"]["lookback_months"]]
    out += [{"id": f"F3_{b}_v{round(v * 100)}_w{w}", "family": "F3", "base": b, "target": v, "window": w}
            for b in f["F3_vol_target"]["bases"] for v in f["F3_vol_target"]["target_vol"]
            for w in f["F3_vol_target"]["window_days"]]
    return out


def primary_ids(cfg) -> list:
    f = cfg["families"]
    p3 = f["F3_vol_target"]["primary"]
    return [f"F1_N{f['F1_trend']['primary']['sma_months']}",
            f"F2_k{f['F2_dual_momentum']['primary']['top_k']}_L{f['F2_dual_momentum']['primary']['lookback_months']}"] + \
           [f"F3_{b}_v{round(p3['target_vol'] * 100)}_w{p3['window_days']}" for b in f["F3_vol_target"]["bases"]]


def base_weights(conf, ctx) -> pd.DataFrame:
    if conf["family"] == "F3" and conf["base"] == "sixty_forty":
        return rules.fixed_weights(ctx.avail, ctx.cfg["sixty_forty"]).loc[ctx.sig]
    return rules.equal_weight(ctx.avail).loc[ctx.sig]


def base_name(conf) -> str:
    return "60/40" if conf.get("base") == "sixty_forty" else "EW"


def weights(conf, ctx) -> pd.DataFrame:
    me, av = ctx.me, ctx.avail
    if conf["family"] == "F1":
        return rules.f1_trend(me, av, conf["n"]).loc[ctx.sig]
    if conf["family"] == "F2":
        return rules.f2_dual_momentum(me, av, conf["k"], conf["L"], ctx.cash_lookback(conf["L"])).loc[ctx.sig]
    b = base_weights(conf, ctx)
    return rules.f3_vol_target(b, ctx.rets, conf["target"], conf["window"], ctx.cfg["families"]["F3_vol_target"]["max_exposure"])


# ---------------------------------------------------------------------------
# Simuleren
# ---------------------------------------------------------------------------

def run_weights(w: pd.DataFrame, ctx, cost, lag=1, rets=None, cash=None) -> dict:
    """Simuleer één portefeuille en geef maandrendementen + handelskengetallen."""
    w = w.reindex(columns=ctx.assets()).fillna(0.0)
    sim = portfolio.simulate(w.to_numpy(), w.index, ctx.rets if rets is None else rets,
                             ctx.cash if cash is None else cash, cost, lag=lag, end=ctx.end)
    m = portfolio.monthly_returns(sim["values"], sim["days"], ctx.start, ctx.end)[0]
    inside = (sim["exec"] >= ctx.start) & (sim["exec"] < ctx.end)
    years = len(m) / 12
    expo = float(w.to_numpy().sum(1)[:len(sim["exec"])][np.asarray(inside)].mean())
    return {"r": m, "turnover_py": float(sim["turnover"][0, inside].sum() / years),
            "trades_py": float(sim["trades"][0, inside].sum() / years),
            "exposure": expo, "daily_values": sim["values"][0], "days": sim["days"]}


def evaluate(conf, ctx, cost, lag=1, rets=None, cash=None, rf=None) -> dict:
    """Regel + volle baseline + baseline met dezelfde tijd in de markt."""
    rf = ctx.rf if rf is None else rf
    w = weights(conf, ctx)
    b = base_weights(conf, ctx)
    s = run_weights(w, ctx, cost, lag, rets, cash)
    base = run_weights(b, ctx, cost, lag, rets, cash)
    matched = run_weights(b * s["exposure"], ctx, cost, lag, rets, cash)
    return {"conf": conf, "w": w, "strat": s, "base": base, "matched": matched, "rf": rf}


def diffs(ev, months=None) -> dict:
    """Sharpe-verschil (vs volle baseline) en MDD-verschil (vs zelfde tijd in de markt)."""
    pick = (lambda x: x) if months is None else (lambda x: x[x.index.isin(months)])
    s, b, mt, rf = (pick(ev["strat"]["r"]), pick(ev["base"]["r"]), pick(ev["matched"]["r"]), pick(ev["rf"]))
    return {"sharpe": float(stats.metric_diff("sharpe", s.to_numpy(), b.to_numpy(), rf.to_numpy())),
            "mdd": float(stats.metric_diff("mdd", s.to_numpy(), mt.to_numpy(), rf.to_numpy()))}


def describe(run: dict, rf: pd.Series) -> dict:
    out = stats.summary(run["r"], rf)
    out.update({"turnover_py": run.get("turnover_py"), "trades_py": run.get("trades_py"),
                "exposure": run.get("exposure"),
                "mdd_daily": stats.daily_mdd(run["daily_values"][run["days"] >= run["r"].index[0]])})
    return out


# ---------------------------------------------------------------------------
# Robuustheid
# ---------------------------------------------------------------------------

def subperiod_diffs(ev, ctx, cost) -> list:
    """Per subperiode; de baseline met dezelfde tijd in de markt gebruikt ē van die subperiode."""
    out = []
    w = ev["w"]
    ex = portfolio.exec_dates(w.index, ctx.rets.index, 1)
    for a, b in ctx.cfg["periods"]["subperiods"]:
        months = ev["strat"]["r"].index[(ev["strat"]["r"].index >= a) & (ev["strat"]["r"].index < b)]
        inside = (ex >= pd.Timestamp(a)) & (ex < pd.Timestamp(b))
        e_sub = float(w.to_numpy().sum(1)[np.asarray(inside)].mean())
        matched = run_weights(base_weights(ev["conf"], ctx) * e_sub, ctx, cost)
        ev_sub = dict(ev, matched=matched)
        d = diffs(ev_sub, months)
        d.update({"from": a, "to": b, "exposure": e_sub})
        out.append(d)
    return out


def without_best_years(ev) -> dict:
    """Haal per maatstaf de twee jaren met het grootste voordeel voor de regel weg."""
    out = {}
    for kind, ref in (("sharpe", "base"), ("mdd", "matched")):
        yr_s = (1 + ev["strat"]["r"]).groupby(ev["strat"]["r"].index.year).prod()
        yr_b = (1 + ev[ref]["r"]).groupby(ev[ref]["r"].index.year).prod()
        best = list((yr_s - yr_b).sort_values(ascending=False).index[:2])
        months = ev["strat"]["r"].index[~ev["strat"]["r"].index.year.isin(best)]
        out[kind] = {"removed_years": [int(y) for y in best], "diff": diffs(ev, months)[kind]}
    return out


def leave_one_year_out(ev) -> dict:
    """Draagt één jaar alles? Verschil zonder elk kalenderjaar apart (PLAN3 §10, punt 4)."""
    idx = ev["strat"]["r"].index
    out = {int(y): diffs(ev, idx[idx.year != y]) for y in sorted(set(idx.year))}
    return {"by_year": out, "min_sharpe": min(v["sharpe"] for v in out.values()),
            "min_mdd": min(v["mdd"] for v in out.values())}


def per_asset_vol_target(conf, ctx, cost) -> dict:
    """Toevoeging na de resultaten (PLAN3 §11): F3-regel op elke asset afzonderlijk vs buy-and-hold."""
    out = {}
    assets = list(ctx.cfg["sixty_forty"]) if conf["base"] == "sixty_forty" else ctx.assets()
    for a in assets:
        b = rules.single_asset(ctx.avail, a).loc[ctx.sig]
        w = rules.f3_vol_target(b, ctx.rets, conf["target"], conf["window"])
        first = b.index[b[a] > 0][0]
        sub = Context.__new__(Context)
        sub.__dict__.update(ctx.__dict__)
        sub.start = max(ctx.start, portfolio.exec_dates(pd.DatetimeIndex([first]), ctx.rets.index)[0].to_period("M").to_timestamp())
        sub.rf = ctx.rf[ctx.rf.index >= sub.start]
        s, bh = run_weights(w, sub, cost), run_weights(b, sub, cost)
        m = run_weights(b * s["exposure"], sub, cost)
        out[a] = {"from": str(sub.start.date()), "exposure": s["exposure"],
                  **diffs({"strat": s, "base": bh, "matched": m, "rf": sub.rf}),
                  "sharpe_strat": float(stats.sharpe(s["r"].to_numpy(), sub.rf.to_numpy())),
                  "sharpe_bh": float(stats.sharpe(bh["r"].to_numpy(), sub.rf.to_numpy()))}
    return out


def rolling_windows(ev, length=120) -> pd.DataFrame:
    idx = ev["strat"]["r"].index
    rows = []
    for i in range(0, len(idx) - length + 1):
        d = diffs(ev, idx[i:i + length])
        rows.append({"end": idx[i + length - 1], **d})
    return pd.DataFrame(rows)


def random_timing(conf, ctx, cost, n, rng, min_shift) -> dict:
    """1000 simulaties met dezelfde tijd in de markt, ander moment (PLAN3 §5)."""
    me, av = ctx.me.loc[ctx.sig], ctx.avail.loc[ctx.sig]
    if conf["family"] == "F1":
        ind = (rules.trend_on(ctx.me, conf["n"]) & ctx.avail).loc[ctx.sig]
        W = rules.random_timing_assets(ind, av, rules.equal_weight(ctx.avail).loc[ctx.sig], n, rng, min_shift)
    elif conf["family"] == "F2":
        ind = weights(conf, ctx) > 0
        W = rules.random_timing_assets(ind, av, av.astype(float) / conf["k"], n, rng, min_shift)
    else:
        b = base_weights(conf, ctx)
        e = rules.f3_exposure(b, ctx.rets, conf["target"], conf["window"])
        W = rules.random_timing_exposure(e, b, n, rng, min_shift)
    sim = portfolio.simulate(W, ctx.sig, ctx.rets, ctx.cash, cost, end=ctx.end)
    m = portfolio.monthly_returns(sim["values"], sim["days"], ctx.start, ctx.end).to_numpy().T
    rf = ctx.rf.to_numpy()
    inside = (sim["exec"] >= ctx.start) & (sim["exec"] < ctx.end)
    years = m.shape[1] / 12
    return {"sharpe": stats.sharpe(m, rf), "mdd": stats.max_drawdown(m), "cagr": stats.cagr(m),
            "exposure": float(W[:, :len(sim["exec"])][:, inside].sum(2).mean()),
            "turnover_py": float(sim["turnover"][:, inside].sum(1).mean() / years)}


def neighbours(conf, all_confs) -> list:
    f = conf["family"]
    same = [c for c in all_confs if c["family"] == f]
    if f == "F1":
        ns = sorted(c["n"] for c in same)
        i = ns.index(conf["n"])
        keep = {ns[j] for j in (i - 1, i + 1) if 0 <= j < len(ns)}
        return [c for c in same if c["n"] in keep]
    if f == "F2":
        ks, ls = sorted({c["k"] for c in same}), sorted({c["L"] for c in same})
        ki, li = ks.index(conf["k"]), ls.index(conf["L"])
        cells = {(ks[j], conf["L"]) for j in (ki - 1, ki + 1) if 0 <= j < len(ks)}
        cells |= {(conf["k"], ls[j]) for j in (li - 1, li + 1) if 0 <= j < len(ls)}
        return [c for c in same if (c["k"], c["L"]) in cells]
    same = [c for c in same if c["base"] == conf["base"]]
    ts, ws = sorted({c["target"] for c in same}), sorted({c["window"] for c in same})
    ti, wi = ts.index(conf["target"]), ws.index(conf["window"])
    cells = {(ts[j], conf["window"]) for j in (ti - 1, ti + 1) if 0 <= j < len(ts)}
    cells |= {(conf["target"], ws[j]) for j in (wi - 1, wi + 1) if 0 <= j < len(ws)}
    return [c for c in same if (c["target"], c["window"]) in cells]


def grid_members(conf, all_confs) -> list:
    same = [c for c in all_confs if c["family"] == conf["family"]]
    if conf["family"] == "F3":
        same = [c for c in same if c["base"] == conf["base"]]
    return same


def leave_one_out(conf, cfg, cost, start, end, until) -> dict:
    out = {}
    for a in cfg["universe"]:
        ctx = Context(cfg, [t for t in cfg["universe"] if t != a], start, end, until)
        out[a] = diffs(evaluate(conf, ctx, cost))
    return out


def eur_context(ctx, cfg, cash_in_eur: bool):
    """Rendementen in EUR (zonder afdekking). cash_in_eur: cash-deel tegen de euro-3m-rente."""
    fx = data.read_fred(cfg["data"]["fred_eurusd"], cfg, ctx.until)
    fx = fx.reindex(ctx.rets.index.union(fx.index)).ffill().reindex(ctx.rets.index)
    f = fx.shift(1) / fx                                    # USD -> EUR: (X_{t-1} / X_t)
    rets = (1 + ctx.rets).mul(f, axis=0) - 1
    eur_cash = data.cash_daily(cfg, ctx.rets.index, series=cfg["data"]["fred_eur_cash"], until=ctx.until)
    cash = eur_cash if cash_in_eur else (1 + ctx.cash) * f - 1
    return rets, cash.fillna(0.0), portfolio.monthly_cash(eur_cash, ctx.start, ctx.end)


def dividend_check(cfg, until) -> dict:
    """Totaalrendement uit Adj Close vs slotkoers + zelf herbelegde dividenden, per jaar."""
    out = {}
    for t in cfg["universe"]:
        h = data.read_ticker(t, cfg, until)
        h = h[h.index >= "2005-01-01"]
        tr_adj = h["Adj Close"] / h["Adj Close"].iloc[0]
        own = ((h["Close"] + h["Dividends"]) / h["Close"].shift(1)).fillna(1.0).cumprod()
        ya = tr_adj.groupby(h.index.year).last() / tr_adj.groupby(h.index.year).last().shift(1) - 1
        yo = own.groupby(h.index.year).last() / own.groupby(h.index.year).last().shift(1) - 1
        dif = ((ya - yo) * 100).dropna()
        cagr_a = float(tr_adj.iloc[-1] ** (252 / len(h)) - 1) * 100
        cagr_o = float(own.iloc[-1] ** (252 / len(h)) - 1) * 100
        out[t] = {"max_abs_year_diff_pp": float(dif.abs().max()), "cagr_adj": cagr_a, "cagr_own": cagr_o}
    return out


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------

def judge(kind, p: dict, scfg) -> dict:
    """Criteria uit PLAN3 §9 voor één maatstaf. p = verzamelde uitkomsten van de primaire configuratie."""
    bs = p["ci"][kind]
    width = bs["hi"] - bs["lo"]
    limit = scfg["max_ci_width_sharpe"] if kind == "sharpe" else scfg["max_ci_width_mdd_pp"]
    sub_ok = sum(1 for s in p["subperiods"] if s[kind] > 0)
    loo = p.get("loo")
    c = {
        "1_estimate_positive": bs["est"] > 0,
        "2_p_improve": bs["p_improve"] >= scfg["min_prob_improvement"],
        "3_ci_width": width <= limit,
        "4a_subperiods": sub_ok >= scfg["min_subperiods_improved"],
        "4b_without_best_two_years": p["without_best"][kind]["diff"] > 0,
        "4c_leave_one_asset_out": (min(v[kind] for v in loo.values()) > 0) if loo else None,
        "5_costs_3x": p["costs"]["0.003"][kind] > 0,
        "6_plateau": p["plateau"][kind]["neighbour_share"] >= scfg["plateau_neighbour_share"]
                     and p["plateau"][kind]["grid_share"] >= scfg["plateau_grid_share"],
    }
    if kind == "mdd":
        c["7_sharpe_not_worse"] = p["ci"]["sharpe"]["est"] >= -0.10
    passed = all(v for v in c.values() if v is not None)
    return {"criteria": c, "passed": bool(passed), "ci_width": width, "subperiods_improved": sub_ok}


def verdict(p: dict, scfg) -> str:
    st = p["status"]
    if st["claims"] and "sharpe" in st["claims"]:
        return "c"
    if st["claims"] and "mdd" in st["claims"]:
        s, b = p["summary"]["strat"], p["summary"]["base"]
        if abs(s["mdd"]) < abs(b["mdd"]) and s["cagr"] >= b["cagr"] - scfg["similar_cagr_pp"]:
            return "b"
    return "a"


# ---------------------------------------------------------------------------
# Hoofdprogramma
# ---------------------------------------------------------------------------

def strip(o):
    if isinstance(o, dict):
        return {str(k): strip(v) for k, v in o.items() if k not in ("boot", "daily_values", "days", "r", "w")}
    if isinstance(o, (list, tuple)):
        return [strip(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if isinstance(o, pd.Timestamp):
        return str(o.date())
    return o


def main():
    cfg = data.load_config()
    per = cfg["periods"]
    start, end, until = per["research_start"], per["research_end"], per["research_end"]
    cost = cfg["costs"]["default"]
    ctx = Context(cfg, cfg["universe"], start, end, until)
    assert ctx.prices.index.max() < pd.Timestamp(until), "research mag geen H3-data bevatten"
    confs = trial_list(cfg)
    prim = primary_ids(cfg)
    rng = np.random.default_rng(cfg["bootstrap"]["seed"])
    T = len(ctx.rf)
    idx = stats.stationary_indices(T, cfg["bootstrap"]["n"], cfg["bootstrap"]["mean_block_months"], rng)
    rf = ctx.rf.to_numpy()

    # 1. Alle trials bij elk kostenniveau
    evs = {}
    grid = []
    for c in confs:
        for k in cfg["costs"]["sensitivity"]:
            ev = evaluate(c, ctx, k)
            if k == cost:
                evs[c["id"]] = ev
            d = diffs(ev)
            grid.append({**{x: c.get(x) for x in ("id", "family", "n", "k", "L", "base", "target", "window")},
                         "cost": k, "sharpe_diff": d["sharpe"], "mdd_diff": d["mdd"],
                         "sharpe": stats.summary(ev["strat"]["r"], ctx.rf)["sharpe"],
                         "base_sharpe": stats.summary(ev["base"]["r"], ctx.rf)["sharpe"],
                         "mdd": stats.summary(ev["strat"]["r"], ctx.rf)["mdd"],
                         "matched_mdd": stats.summary(ev["matched"]["r"], ctx.rf)["mdd"],
                         "base_mdd": stats.summary(ev["base"]["r"], ctx.rf)["mdd"],
                         "cagr": stats.summary(ev["strat"]["r"], ctx.rf)["cagr"],
                         "base_cagr": stats.summary(ev["base"]["r"], ctx.rf)["cagr"],
                         "exposure": ev["strat"]["exposure"], "turnover_py": ev["strat"]["turnover_py"]})
        print("trial", c["id"])
    grid = pd.DataFrame(grid)
    grid.to_csv(OUT / "grid.csv", index=False)
    pd.DataFrame([{"trial": i + 1, "id": c["id"], "family": c["family"]} for i, c in enumerate(confs)]).to_csv(
        OUT / "trials.csv", index=False)

    # 2. Baselines (beschrijvend)
    ew = run_weights(rules.equal_weight(ctx.avail).loc[ctx.sig], ctx, cost)
    sf = run_weights(rules.fixed_weights(ctx.avail, cfg["sixty_forty"]).loc[ctx.sig], ctx, cost)
    baselines = {"EW": describe(ew, ctx.rf), "60/40": describe(sf, ctx.rf)}
    per_asset = {}
    g10 = cfg["families"]["F1_trend"]["primary"]["sma_months"]
    for a in cfg["universe"]:
        av = ctx.avail.loc[ctx.sig, a]
        first_exec = portfolio.exec_dates(pd.DatetimeIndex([av.index[av][0]]), ctx.rets.index)[0]
        sub = Context.__new__(Context)
        sub.__dict__.update(ctx.__dict__)
        sub.start = max(ctx.start, first_exec.to_period("M").to_timestamp())
        sub.rf = ctx.rf[ctx.rf.index >= sub.start]
        bh = run_weights(rules.single_asset(ctx.avail, a).loc[ctx.sig], sub, cost)
        on = (rules.trend_on(ctx.me, g10) & ctx.avail)[[a]].astype(float).loc[ctx.sig]
        tf = run_weights(on, sub, cost)
        per_asset[a] = {"from": str(sub.start.date()), "buy_hold": describe(bh, sub.rf), "trend": describe(tf, sub.rf)}
    print("baselines klaar")

    # 3. Bootstrap van alle trials (voor de Reality Check) en analyses van de primaire configuraties
    pairs = {"sharpe": [(evs[c["id"]]["strat"]["r"].to_numpy(), evs[c["id"]]["base"]["r"].to_numpy()) for c in confs],
             "mdd": [(evs[c["id"]]["strat"]["r"].to_numpy(), evs[c["id"]]["matched"]["r"].to_numpy()) for c in confs]}
    results = {}
    monthly = {"rf": ctx.rf, "EW": ew["r"], "60/40": sf["r"]}
    rolling = {}
    rt_rng = np.random.default_rng(cfg["random_timing"]["seed"])
    gcost = grid[grid["cost"] == cost].set_index("id")
    for pid in prim:
        conf = next(c for c in confs if c["id"] == pid)
        ev = evs[pid]
        p = {"conf": conf, "baseline": base_name(conf)}
        p["summary"] = {"strat": describe(ev["strat"], ctx.rf), "base": describe(ev["base"], ctx.rf),
                        "matched": describe(ev["matched"], ctx.rf)}
        s_arr, b_arr, m_arr = (ev[x]["r"].to_numpy() for x in ("strat", "base", "matched"))
        p["ci"] = {"sharpe": stats.bootstrap_diff("sharpe", s_arr, b_arr, rf, idx),
                     "mdd": stats.bootstrap_diff("mdd", s_arr, m_arr, rf, idx)}
        p["power"] = {k: {"se": p["ci"][k]["se"], "mde": stats.mde(p["ci"][k]["se"])} for k in ("sharpe", "mdd")}
        p["reality_check"] = {k: stats.reality_check(k, p["ci"][k]["est"], pairs[k], rf, idx) for k in ("sharpe", "mdd")}
        p["subperiods"] = subperiod_diffs(ev, ctx, cost)
        p["without_best"] = without_best_years(ev)
        p["costs"] = {str(k): {"sharpe": float(gcost_k.loc[pid, "sharpe_diff"]), "mdd": float(gcost_k.loc[pid, "mdd_diff"])}
                      for k, gcost_k in ((k, grid[grid["cost"] == k].set_index("id")) for k in cfg["costs"]["sensitivity"])}
        p["timing"] = {f"lag{lag}": diffs(evaluate(conf, ctx, cost, lag=lag)) for lag in (0, 2)}
        if not (conf["family"] == "F3" and conf["base"] == "sixty_forty"):
            p["loo"] = leave_one_out(conf, cfg, cost, start, end, until)
        nb, gm = neighbours(conf, confs), grid_members(conf, confs)
        p["plateau"] = {}
        for k, col in (("sharpe", "sharpe_diff"), ("mdd", "mdd_diff")):
            p["plateau"][k] = {"neighbours": {c["id"]: float(gcost.loc[c["id"], col]) for c in nb},
                               "neighbour_share": float(np.mean([gcost.loc[c["id"], col] > 0 for c in nb])),
                               "grid_share": float(np.mean([gcost.loc[c["id"], col] > 0 for c in gm]))}
        rt = random_timing(conf, ctx, cost, cfg["random_timing"]["n"], rt_rng, cfg["random_timing"]["min_shift_months"])
        st = p["summary"]["strat"]
        p["random_timing"] = {"n": len(rt["sharpe"]), "exposure_random": rt["exposure"], "exposure_strategy": ev["strat"]["exposure"],
                              "turnover_random_py": rt["turnover_py"], "turnover_strategy_py": ev["strat"]["turnover_py"],
                              "sharpe_random_mean": float(np.nanmean(rt["sharpe"])),
                              "sharpe_random_p5_p95": [float(x) for x in np.nanpercentile(rt["sharpe"], [5, 95])],
                              "sharpe_pct": float(np.mean(rt["sharpe"] < st["sharpe"]) * 100),
                              "mdd_random_mean": float(np.nanmean(rt["mdd"])),
                              "mdd_random_p5_p95": [float(x) for x in np.nanpercentile(rt["mdd"], [5, 95])],
                              "mdd_pct": float(np.mean(rt["mdd"] < st["mdd"]) * 100),
                              "cagr_random_mean": float(np.nanmean(rt["cagr"]))}
        # EUR
        p["eur"] = {}
        for name, in_eur in (("usd_cash_converted", False), ("cash_in_eur", True)):
            r_e, c_e, rf_e = eur_context(ctx, cfg, in_eur)
            ev_e = evaluate(conf, ctx, cost, rets=r_e, cash=c_e, rf=rf_e)
            p["eur"][name] = {**diffs(ev_e), "strat": stats.summary(ev_e["strat"]["r"], rf_e),
                              "base": stats.summary(ev_e["base"]["r"], rf_e)}
        p["leave_one_year_out"] = leave_one_year_out(ev)
        if conf["family"] == "F3":
            p["per_asset"] = per_asset_vol_target(conf, ctx, cost)
        rolling[pid] = rolling_windows(ev)
        monthly[pid] = ev["strat"]["r"]
        monthly[pid + "|matched"] = ev["matched"]["r"]
        monthly[pid + "|base"] = ev["base"]["r"]
        # status
        sc = cfg["status"]
        p["judge"] = {k: judge(k, p, sc) for k in ("sharpe", "mdd")}
        claims = [k for k in ("sharpe", "mdd") if p["judge"][k]["passed"]]
        p["status"] = {"status": "candidate" if claims else "rejected", "claims": claims}
        p["verdict"] = verdict(p, sc)
        tg = cfg["too_good"]
        p["too_good"] = bool(p["ci"]["sharpe"]["est"] > tg["sharpe_gain"] or
                             (abs(st["mdd"]) < tg["max_dd_pct"] and st["cagr"] >= p["summary"]["base"]["cagr"]))
        results[pid] = p
        print("primair", pid, p["status"], "verdict", p["verdict"])

    # 4. Voorbeeldgewichten (voor uitleg in het rapport) en wegschrijven
    weights_out = {pid: evs[pid]["w"] for pid in prim}
    for pid, w in weights_out.items():
        w.to_csv(OUT / f"weights_{pid}.csv")
    pd.DataFrame(monthly).to_csv(OUT / "monthly_returns.csv")
    for pid, df in rolling.items():
        df.to_csv(OUT / f"rolling_{pid}.csv", index=False)
    power_prior = {f"rho{rho}": {"se": stats.memmel_se(0.5, 0.5, rho, 16), "mde": stats.mde(stats.memmel_se(0.5, 0.5, rho, 16))}
                   for rho in (0.9, 0.7)}
    out = {"period": {"start": start, "end": end, "months": T}, "costs": cfg["costs"], "n_trials": len(confs),
           "primary": prim, "results": results, "baselines": baselines, "per_asset_F1": per_asset,
           "dividend_check": dividend_check(cfg, until), "power_prior": power_prior,
           "universe_by_month": {str(d.date()): int(ctx.avail.loc[d].sum()) for d in ctx.sig},
           "holdout_opened": {"H3": 0, "P": 0}}
    (OUT / "results.json").write_text(json.dumps(strip(out), indent=1))
    print("klaar")


if __name__ == "__main__":
    main()
