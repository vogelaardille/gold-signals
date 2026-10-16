"""Ronde 4: statistiek (PLAN4 §6 en §8)."""
import numpy as np
import pandas as pd

from fx import engine


def research_days(start: str, end: str) -> pd.DatetimeIndex:
    """Alle valuta-handelsdagen (ma t/m vr) in [start, end)."""
    return pd.bdate_range(start, pd.Timestamp(end) - pd.Timedelta(days=1))


def daily_series(trades: pd.DataFrame, days: pd.DatetimeIndex) -> np.ndarray:
    """Som van de netto bp per handelsdag (dag van de entry); 0 op dagen zonder trade."""
    if trades is None or len(trades) == 0:
        return np.zeros(len(days))
    day = pd.DatetimeIndex(engine.trading_day(pd.DatetimeIndex(trades["entry_time"])))
    s = trades["net_bp"].groupby(day).sum()
    return s.reindex(days, fill_value=0.0).to_numpy()


def sharpe(x: np.ndarray) -> float:
    sd = x.std(ddof=1)
    return float(x.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0


def bootstrap_index(n_days: int, n_draws: int, mean_block: int, seed: int) -> np.ndarray:
    """Stationaire block bootstrap (Politis & Romano): blokken met een willekeurige lengte
    (gemiddeld `mean_block` dagen), circulair. Geeft een matrix n_draws × n_days met dagindexen."""
    rng = np.random.default_rng(seed)
    new_block = rng.random((n_draws, n_days)) < 1.0 / mean_block
    new_block[:, 0] = True
    starts = rng.integers(0, n_days, size=(n_draws, n_days))
    pos = np.arange(n_days)[None, :]
    block_start_pos = np.maximum.accumulate(np.where(new_block, pos, 0), axis=1)
    block_start_val = np.take_along_axis(starts, block_start_pos, axis=1)
    return (block_start_val + (pos - block_start_pos)) % n_days


def bootstrap_mean(x: np.ndarray, idx: np.ndarray) -> np.ndarray:
    return x[idx].mean(axis=1)


def bootstrap_sharpe(x: np.ndarray, idx: np.ndarray) -> np.ndarray:
    s = x[idx]
    sd = s.std(axis=1, ddof=1)
    return np.where(sd > 0, s.mean(axis=1) / np.where(sd > 0, sd, 1) * np.sqrt(252), 0.0)


def reality_check(series: dict, primary: str, idx: np.ndarray) -> float:
    """White's Reality Check (Romano–Wolf-vorm voor één hypothese) op de Sharpe van de dagreeks.
    p = aandeel trekkingen waarin max_j (S_j^b − S_j) ≥ S_primair."""
    names = list(series)
    real = np.array([sharpe(series[k]) for k in names])
    centered_max = np.full(idx.shape[0], -np.inf)
    for k, s_real in zip(names, real):
        centered_max = np.maximum(centered_max, bootstrap_sharpe(series[k], idx) - s_real)
    return float((centered_max >= sharpe(series[primary])).mean())


def summarize(trades: pd.DataFrame, days: pd.DatetimeIndex, idx: np.ndarray) -> dict:
    """Kerngetallen van één configuratie in het research-blok."""
    if trades is None or len(trades) == 0:
        return {"n_trades": 0}
    x = daily_series(trades, days)
    boot = bootstrap_mean(x, idx)
    per_trade = len(trades) / len(days)  # trades per dag, om het daggemiddelde om te rekenen
    by_year = trades.groupby(pd.DatetimeIndex(trades["entry_time"]).year)["net_bp"].sum()
    return {
        "n_trades": int(len(trades)),
        "net_bp": float(trades["net_bp"].mean()),
        "gross_bp": float(trades["gross_bp"].mean()),
        "cost_bp": float(trades["cost_bp"].mean()),
        "r": float(trades["r"].mean()) if trades["r"].notna().any() else None,
        "hit_rate": float((trades["net_bp"] > 0).mean()),
        "sharpe": sharpe(x),
        "boot_pos": float((boot > 0).mean()),
        "ci95_net_bp": [float(np.percentile(boot, 2.5) / per_trade), float(np.percentile(boot, 97.5) / per_trade)],
        "max_dd_bp": float((np.cumsum(x) - np.maximum.accumulate(np.cumsum(x))).min()),
        "best_year": int(by_year.idxmax()),
        "net_bp_without_best_year": float(trades.loc[pd.DatetimeIndex(trades["entry_time"]).year
                                                     != by_year.idxmax(), "net_bp"].mean()),
        "net_bp_by_year": {int(k): round(float(v), 1) for k, v in by_year.items()},
        "long_net_bp": float(trades.loc[trades.direction > 0, "net_bp"].mean()) if (trades.direction > 0).any() else None,
        "short_net_bp": float(trades.loc[trades.direction < 0, "net_bp"].mean()) if (trades.direction < 0).any() else None,
    }
