"""Walk-forward met Optuna, binnen de research-periode.

Idee: je mag parameters alleen kiezen met data uit het verleden. Daarom:
  train 12 maanden -> beste parameters kiezen -> test op de 3 maanden erna
  schuif 3 maanden op en herhaal.
De trades uit alle TEST-vensters samen zijn het eerlijke (out-of-sample) resultaat.

Elke geprobeerde parameterset (trial) wordt gelogd in research/results/trials.csv,
want hoe meer varianten je probeert, hoe groter de kans dat er één toevallig goed
uitziet. Dat aantal gebruikt de deflated Sharpe ratio (validation.py).

Parameterruimte: per strategie in config.yaml onder strategies.<naam>.space,
als lijsten met toegestane waarden (bewust klein en vooraf vastgelegd).
"""
import json

import numpy as np
import optuna
import pandas as pd

from goldsignals.backtest.engine import run_backtest
from goldsignals.market import period_bounds

optuna.logging.set_verbosity(optuna.logging.WARNING)


def windows(cfg: dict) -> list:
    """Lijst van (train_start, train_end, test_start, test_end) binnen de research-periode."""
    w = cfg["walkforward"]
    start, end = period_bounds(cfg, "research")
    out = []
    test_start = start + pd.DateOffset(months=w["train_months"])
    while test_start + pd.DateOffset(months=w["test_months"]) <= end:
        test_end = test_start + pd.DateOffset(months=w["test_months"])
        out.append((test_start - pd.DateOffset(months=w["train_months"]), test_start, test_start, test_end))
        test_start = test_start + pd.DateOffset(months=w["step_months"])
    return out


def index_range(market, t_start, t_end) -> tuple:
    """Candle-indexen met sluitmoment in (t_start, t_end]."""
    ct = market.close_time
    i0 = int(np.searchsorted(ct, t_start, side="right"))
    i1 = int(np.searchsorted(ct, t_end, side="right")) - 1
    return i0, i1


def objective_value(trades: pd.DataFrame, min_trades: int) -> float:
    """Wat Optuna maximaliseert: gemiddelde R na kosten, mits genoeg trades."""
    if len(trades) < min_trades:
        return -1.0
    return float(trades["r"].mean())


def optimize(make_strategy, space: dict, market, cfg, i0, i1, i_hard_end, label, trial_log: list) -> dict:
    """Zoek de beste parameters in [i0, i1]. Elke trial wordt aan trial_log toegevoegd."""
    ocfg = cfg["optuna"]
    if not space:
        return {}
    sampler = optuna.samplers.TPESampler(seed=ocfg["seed"])
    study = optuna.create_study(direction="maximize", sampler=sampler)
    seen = {}

    def obj(trial):
        params = {k: trial.suggest_categorical(k, v) for k, v in space.items()}
        key = json.dumps(params, sort_keys=True)
        if key in seen:                       # al geprobeerd: niet opnieuw tellen
            return seen[key]
        tr = run_backtest(make_strategy(params), market, i0, i1, cfg, i_hard_end=i_hard_end).trades
        val = objective_value(tr, ocfg["min_train_trades"])
        r = tr["r"].to_numpy()
        trial_log.append({**label, "trial": len(seen), "params": key, "n": len(tr),
                          "avg_r": float(r.mean()) if len(r) else np.nan,
                          "sharpe": float(r.mean() / r.std(ddof=1)) if len(r) > 2 and r.std(ddof=1) > 0 else np.nan,
                          "objective": val})
        seen[key] = val
        return val

    study.optimize(obj, n_trials=ocfg["trials_per_window"])
    return dict(study.best_params)


def walk_forward(make_strategy, space: dict, defaults: dict, market, cfg, name: str,
                 trial_log: list, cost_mults=(1.0,)) -> dict:
    """Voer de walk-forward uit. Geeft per kosten-multiplier de OOS-trades en de
    gekozen parameters per venster."""
    _, research_end = period_bounds(cfg, "research")
    i_hard = index_range(market, market.close_time[0], research_end)[1]
    oos = {m: [] for m in cost_mults}
    chosen = []
    free_from = {m: 0 for m in cost_mults}    # eerste candle waarop weer een trade mag (max 1 open)
    for k, (tr0, tr1, te0, te1) in enumerate(windows(cfg)):
        a0, a1 = index_range(market, tr0, tr1)
        b0, b1 = index_range(market, te0, te1)
        # Trades in het train-venster mogen doorlopen tot de start van het testvenster, niet verder
        best = optimize(make_strategy, space, market, cfg, a0, a1, b0 - 1,
                        {"strategy": name, "window": k}, trial_log)
        params = {**defaults, **best}
        chosen.append({"window": k, "test_start": te0, "test_end": te1, "params": params})
        for m in cost_mults:
            # Testvenster: entries alleen binnen het venster; open trades lopen door
            # (uiterlijk tot het einde van de research-periode, nooit de hold-out in).
            start = max(b0, free_from[m])
            t = run_backtest(make_strategy(params), market, start, b1, cfg, cost_mult=m, i_hard_end=i_hard).trades
            t["window"] = k
            if len(t):   # loopt een trade door in het volgende venster, dan daar pas later instappen
                free_from[m] = market.index_of_close(t["exit_time"].max()) + 1
            oos[m].append(t)
    return {"oos": {m: pd.concat(v, ignore_index=True) if v else pd.DataFrame() for m, v in oos.items()},
            "chosen": chosen}


def final_params(make_strategy, space: dict, defaults: dict, market, cfg, name: str, trial_log: list) -> dict:
    """Parameters voor hold-out en paper trading: dezelfde procedure op de laatste
    train_months van de research-periode (het venster vlak voor de hold-out)."""
    _, end = period_bounds(cfg, "research")
    start = end - pd.DateOffset(months=cfg["walkforward"]["train_months"])
    a0, a1 = index_range(market, start, end)
    best = optimize(make_strategy, space, market, cfg, a0, a1, a1, {"strategy": name, "window": "final"}, trial_log)
    return {**defaults, **best}
