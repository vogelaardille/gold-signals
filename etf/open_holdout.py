"""H3 of P openen voor één candidate-configuratie (PLAN3 §2 en §9). EENMALIG per blok.

Volgorde:
1. status uit research/round3/results/results.json moet 'candidate' zijn;
2. de opening wordt gelogd (etf/holdout.py), vóórdat er data geladen wordt;
3. datakwaliteit van het blok;
4. exact dezelfde regel en meting als in research (kosten 0,10%, en ter info 0,30%).

Draaien: .venv/bin/python -m etf.open_holdout <config_id> H3|P
Uitvoer: research/round3/results/holdout_<blok>_<config_id>.json
"""
import json
import sys

import numpy as np
import pandas as pd

from etf import data, holdout, portfolio, stats
from etf.data import ROOT
from etf.run import OUT, Context, describe, diffs, evaluate, strip, trial_list


def block_quality(cfg, tickers, start, until) -> dict:
    """Ontbrekende dagen en de dividend-/uitkeringscorrectie binnen het blok."""
    out = {}
    for t in tickers:
        h = data.read_ticker(t, cfg, until)
        h = h[h.index >= pd.Timestamp(start) - pd.DateOffset(years=2)]
        cal = data.read_ticker(cfg["data"]["calendar_ticker"], cfg, until).index
        cal = cal[(cal >= h.index[0])]
        ratio = h["Adj Close"] / h["Close"]
        jump = ratio.pct_change().abs() > 1e-4
        div = h["Dividends"] != 0
        cg = h["Capital Gains"].fillna(0) != 0 if "Capital Gains" in h else pd.Series(False, index=h.index)
        ev = div | cg | (h["Stock Splits"] != 0)
        near = ev | ev.shift(1, fill_value=False) | ev.shift(-1, fill_value=False)
        near_cg = cg | cg.shift(1, fill_value=False) | cg.shift(-1, fill_value=False)
        # Wordt een uitkering van koerswinst (capital gain) ook in Adj Close verwerkt?
        cg_days = h.index[cg]
        cg_adjusted = int(sum(bool(jump[(jump.index >= d - pd.Timedelta(days=3)) & (jump.index <= d + pd.Timedelta(days=3))].any())
                              for d in cg_days))
        out[t] = {"first": str(h.index[0].date()), "missing_days": int(len(cal.difference(h.index))),
                  "ratio_jumps_without_event": int((jump & ~near).sum()),
                  "capital_gain_events": int(cg.sum()), "capital_gain_events_adjusted": cg_adjusted,
                  "big_moves_gt15pct": int((h["Adj Close"].pct_change().abs() > 0.15).sum()),
                  "unadjusted_cg_pct_per_year": float((h.loc[cg, "Capital Gains"] / h["Close"].shift(1)[cg]).sum()
                                                      / max((h.index[-1] - h.index[0]).days / 365.25, 1) * 100)
                  if cg.any() and cg_adjusted < cg.sum() else 0.0,
                  "_near_cg_jumps": int((jump & near_cg).sum())}
    return out


def main(config_id: str, block: str):
    cfg = data.load_config()
    res = json.loads((OUT / "results.json").read_text())
    status = res["results"].get(config_id, {}).get("status", {}).get("status")
    holdout.open_block(block, config_id, status)            # weigert als niet candidate of al open
    per = cfg["periods"]
    conf = next(c for c in trial_list(cfg) if c["id"] == config_id)
    if block == "H3":
        tickers, rename = cfg["universe"], None
        start, end, until = per["h3_start"], per["h3_end"], per["h3_end"]
    else:
        pairs = {etf: px for etf, px in cfg["proxies"].items() if px}
        tickers, rename = list(pairs.values()), {px: etf for etf, px in pairs.items()}
        start, end, until = per["p_start"], per["p_end"], per["p_end"]
    quality = block_quality(cfg, tickers, start, until)
    ctx = Context(cfg, tickers, start, end, until, rename=rename)
    assert ctx.prices.index.max() < pd.Timestamp(until)
    out = {"config": config_id, "block": block, "period": [start, end], "months": len(ctx.rf),
           "tickers": tickers, "quality": quality,
           "universe_by_month": {str(d.date()): int(ctx.avail.loc[d].sum()) for d in ctx.sig}}
    for cost in (cfg["costs"]["default"], 0.003):
        ev = evaluate(conf, ctx, cost)
        d = diffs(ev)
        rec = {**d, "strat": describe(ev["strat"], ctx.rf), "base": describe(ev["base"], ctx.rf),
               "matched": describe(ev["matched"], ctx.rf)}
        if cost == cfg["costs"]["default"]:
            rng = np.random.default_rng(cfg["bootstrap"]["seed"])
            idx = stats.stationary_indices(len(ctx.rf), cfg["bootstrap"]["n"], cfg["bootstrap"]["mean_block_months"], rng)
            rf = ctx.rf.to_numpy()
            s, b, m = (ev[x]["r"].to_numpy() for x in ("strat", "base", "matched"))
            rec["ci"] = {"sharpe": stats.bootstrap_diff("sharpe", s, b, rf, idx),
                         "mdd": stats.bootstrap_diff("mdd", s, m, rf, idx)}
            rec["exposure_by_month"] = {str(k.date()): float(v) for k, v in ev["w"].sum(axis=1).items()}
            rec["monthly"] = {str(k.date()): [float(ev["strat"]["r"][k]), float(ev["base"]["r"][k])]
                              for k in ev["strat"]["r"].index}
        out[f"cost_{cost}"] = rec
    claims = res["results"][config_id]["status"]["claims"]
    main_rec = out[f"cost_{cfg['costs']['default']}"]
    out["claims"] = claims
    out["positive"] = {k: bool(main_rec[k] > 0) for k in claims}
    path = OUT / f"holdout_{block}_{config_id}.json"
    keep = {k: v for k, v in out.items()}
    for k in list(keep):
        if k.startswith("cost_"):
            mon, expo = keep[k].pop("monthly", None), keep[k].pop("exposure_by_month", None)
            keep[k] = strip(keep[k])
            if mon is not None:
                keep[k]["monthly"], keep[k]["exposure_by_month"] = mon, expo
    path.write_text(json.dumps(strip({k: v for k, v in keep.items() if not k.startswith("cost_")}) |
                               {k: v for k, v in keep.items() if k.startswith("cost_")}, indent=1))
    print(json.dumps({k: v for k, v in strip(out).items() if k not in ("universe_by_month",)}, indent=1)[:6000])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
