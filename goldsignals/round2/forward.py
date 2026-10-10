"""Forward-test van vol_squeeze_4h (research/round2/FORWARD.md). AANWIJZING, NIET BEWEZEN.

- fingerprint(): hash van ALLE code die bepaalt wat de strategie doet (signaal + uitvoering).
  Staat in FORWARD.md; tests/test_forward.py faalt als er iets aan verandert.
- forward_state(): stopregel en evaluatiemoment, uit de gesloten paper trades.
- main(): de vooraf vastgelegde evaluatie (na 100 trades): bootstrap-interval en
  vergelijking met random entries met exact dezelfde exits.
Evaluatie draaien: .venv/bin/python -m goldsignals.round2.forward
"""
import hashlib
import inspect
import json

import numpy as np
import pandas as pd

STRATEGY_ID = "vol_squeeze_4h"
LABEL = "AANWIJZING, NIET BEWEZEN"
STOP_AFTER_TRADES = 40       # vanaf deze trade wordt de stopregel gecontroleerd
STOP_MEAN_R = -0.25          # gemiddelde R (na kosten) waaronder de strategie stopt
EVALUATE_AT_TRADES = 100     # evaluatiemoment; daarna geen nieuwe entries tot de gebruiker beslist


def fingerprint() -> str:
    """sha256 over de broncode van alles wat het gedrag bepaalt."""
    from goldsignals.backtest import engine
    from goldsignals.data import timeframes
    from goldsignals.round2 import families, indicators
    from goldsignals.sr import pivots
    from goldsignals.strategies import vol_squeeze_4h
    parts = [inspect.getsource(vol_squeeze_4h),
             inspect.getsource(families.f2), inspect.getsource(families.Signals),
             inspect.getsource(indicators.bollinger), inspect.getsource(indicators.pct_rank_1y),
             inspect.getsource(pivots.atr), inspect.getsource(timeframes.resample),
             inspect.getsource(timeframes._localize), inspect.getsource(timeframes._same_time_unit),
             inspect.getsource(engine.anchor_to_entry), inspect.getsource(engine.try_fill),
             inspect.getsource(engine.check_exit), inspect.getsource(engine.cost_per_oz)]
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:16]


def forward_state(closed: pd.DataFrame) -> dict:
    """Status van de forward-test uit de gesloten trades van deze strategie (op volgorde).
    - 'gestopt': ergens vanaf trade 40 zakte het lopende gemiddelde onder -0,25 R;
    - 'evaluatie': 100 trades bereikt (pauze tot de gebruiker beslist);
    - 'actief': anders."""
    r = closed.sort_values("exit_time")["r"].astype(float).to_numpy() if len(closed) else np.array([])
    n = len(r)
    if n >= STOP_AFTER_TRADES:
        run_mean = np.cumsum(r) / np.arange(1, n + 1)
        hit = np.flatnonzero(run_mean[STOP_AFTER_TRADES - 1:min(n, EVALUATE_AT_TRADES)] < STOP_MEAN_R)
        if len(hit):
            k = int(hit[0]) + STOP_AFTER_TRADES
            return {"status": "gestopt", "n": n, "at_trade": k, "mean_r_at_stop": float(run_mean[k - 1])}
    if n >= EVALUATE_AT_TRADES:
        return {"status": "evaluatie", "n": n, "mean_r": float(r.mean())}
    return {"status": "actief", "n": n, "mean_r": float(r.mean()) if n else None}


def evaluate(trades: pd.DataFrame, market, cfg, start: pd.Timestamp, end: pd.Timestamp,
             n_rep: int = 200, seed: int = 2027) -> dict:
    """Vooraf vastgelegde evaluatie (FORWARD.md §5)."""
    from goldsignals.backtest.engine import run_backtest
    from goldsignals.backtest.walkforward import index_range
    from goldsignals.research.stats import bootstrap_mean
    from goldsignals.strategies.vol_squeeze_4h import VolSqueeze4h, bars_4h
    rng = np.random.default_rng(seed)
    t = trades.sort_values("exit_time").head(EVALUATE_AT_TRADES)
    r = t["r"].astype(float)
    months = pd.DatetimeIndex(pd.to_datetime(t["entry_time"], utc=True))
    ci = bootstrap_mean(r, months.year * 12 + months.month, 5000, rng)
    # Random entries met exact dezelfde exits: willekeurige 4h-sluitingen in dezelfde periode,
    # per kalenderjaar evenveel entries en dezelfde long/short-verhouding.
    i0, i1 = index_range(market, start, end)
    b4 = bars_4h(market.candles.iloc[:i1 + 1], end)
    closes = b4["close_time"][(b4["close_time"] > start) & (b4["close_time"] <= end)]
    years = months.year
    means = []
    for _ in range(n_rep):
        forced = {}
        for y in np.unique(years):
            k = int((years == y).sum())
            pool = closes[closes.dt.year == y].to_numpy()
            if len(pool) == 0:
                continue
            pick = rng.choice(pool, size=min(k, len(pool)), replace=False)
            share = float((t.loc[years == y, "direction"] == 1).mean())
            dirs = np.r_[np.ones(int(round(len(pick) * share))), -np.ones(len(pick) - int(round(len(pick) * share)))]
            rng.shuffle(dirs)
            forced.update({pd.Timestamp(p): int(d) for p, d in zip(pick, dirs)})
        rt = run_backtest(VolSqueeze4h(forced=forced), market, i0, i1, cfg).trades
        means.append(rt["r"].mean() if len(rt) else np.nan)
    means = np.array(means)
    pct = float((means < r.mean()).mean() * 100)
    if ci["hi"] < 0:
        verdict = "negatief: het interval ligt onder nul"
    elif ci["lo"] > 0 and pct >= 95:
        verdict = "aanwijzing bevestigd (nog steeds niet 'validated'; zie FORWARD.md §5)"
    else:
        verdict = "niet bevestigd: niet te onderscheiden van nul en/of van random"
    return {"n": len(t), "mean_r": float(r.mean()), "ci": ci, "random_mean": float(np.nanmean(means)),
            "random_p95": float(np.nanpercentile(means, 95)), "pct_vs_random": pct, "verdict": verdict,
            "fingerprint": fingerprint()}


def main():
    from goldsignals.config import load_config, project_path
    from goldsignals.features import compute_features
    from goldsignals.market import Market, load_candles
    from goldsignals.paper.state import State
    cfg = load_config()
    state = State(project_path(cfg["paper"]["state_dir"]))
    closed = state.closed_trades()
    closed = closed[closed["strategy"] == STRATEGY_ID]
    fs = forward_state(closed)
    if fs["n"] < EVALUATE_AT_TRADES:
        print(f"Nog geen evaluatie: {fs['n']} van {EVALUATE_AT_TRADES} trades (status {fs['status']}).")
        return
    c = load_candles(cfg)
    m = Market(c, compute_features(c, cfg))
    start = pd.Timestamp(state.meta["forward_start"][STRATEGY_ID])
    end = pd.to_datetime(closed["exit_time"], utc=True).sort_values().iloc[EVALUATE_AT_TRADES - 1]
    res = evaluate(closed, m, cfg, start, end)
    out = project_path("research/round2/results/forward_evaluation.json")
    out.write_text(json.dumps(res, indent=1, default=str))
    print(json.dumps(res, indent=1, default=str))


if __name__ == "__main__":
    main()
