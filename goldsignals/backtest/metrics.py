"""Kengetallen van een reeks trades.

De equity-curve rekenen we uit de R-waarden: elke trade riskeert risk_pct van de
equity op dat moment, dus na een trade met resultaat R is de equity x (1 + R x risk_pct/100).
Zo kun je trades uit verschillende walk-forward-vensters netjes achter elkaar zetten.
"""
import numpy as np
import pandas as pd


def equity_curve(trades: pd.DataFrame, start_equity: float, risk_pct: float) -> pd.Series:
    if trades.empty:
        return pd.Series([start_equity], dtype=float)
    t = trades.sort_values("exit_time")
    eq = start_equity * np.cumprod(1 + t["r"].to_numpy() * risk_pct / 100)
    return pd.Series(np.r_[start_equity, eq], index=[t["entry_time"].iloc[0]] + list(t["exit_time"]))


def max_drawdown_pct(eq: pd.Series) -> float:
    if len(eq) < 2:
        return 0.0
    peak = eq.cummax()
    return float(((eq - peak) / peak).min() * 100)


def summarize(trades: pd.DataFrame, start_equity: float = 10000, risk_pct: float = 1.0) -> dict:
    n = len(trades)
    if n == 0:
        return {"n": 0, "winrate": np.nan, "avg_r": np.nan, "total_r": 0.0, "pf": np.nan,
                "sharpe": np.nan, "max_dd_pct": 0.0, "return_pct": 0.0,
                "n_long": 0, "avg_r_long": np.nan, "n_short": 0, "avg_r_short": np.nan}
    r = trades["r"].to_numpy(float)
    eq = equity_curve(trades, start_equity, risk_pct)
    gains, losses = r[r > 0].sum(), -r[r < 0].sum()
    long_, short_ = trades[trades["direction"] == 1], trades[trades["direction"] == -1]
    return {
        "n": n,
        "winrate": float((r > 0).mean() * 100),
        "avg_r": float(r.mean()),
        "total_r": float(r.sum()),
        "pf": float(gains / losses) if losses > 0 else np.inf,
        "sharpe": float(r.mean() / r.std(ddof=1)) if n > 1 and r.std(ddof=1) > 0 else np.nan,
        "max_dd_pct": max_drawdown_pct(eq),
        "return_pct": float(eq.iloc[-1] / start_equity * 100 - 100),
        "n_long": len(long_), "avg_r_long": float(long_["r"].mean()) if len(long_) else np.nan,
        "n_short": len(short_), "avg_r_short": float(short_["r"].mean()) if len(short_) else np.nan,
    }


def r_by_year(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {}
    y = pd.to_datetime(trades["entry_time"]).dt.year
    g = trades.groupby(y)["r"]
    return {int(k): {"n": int(v.count()), "total_r": float(v.sum()), "avg_r": float(v.mean())} for k, v in g}
