"""Kengetallen en onzekerheid op maandrendementen (PLAN3 §6 en §8).

- Sharpe: gemiddeld maandrendement boven cash / standaardafwijking daarvan x sqrt(12).
- MDD: maximale daling op maandslotwaarden (in %, negatief getal).
- Stationaire block bootstrap (Politis & Romano 1994): blokken met een willekeurige lengte
  (geometrisch verdeeld, gemiddeld 12 maanden), die rond het einde doorlopen. Alle reeksen
  worden met dezelfde getrokken maanden herberekend (gepaard).
- Reality Check (White 2000; Romano-Wolf voor één hypothese): het verschil van de primaire
  configuratie vergeleken met het grootste toevalsverschil over alle trials.
Alle functies werken op arrays met de tijd langs de LAATSTE as, zodat ze ook op
bootstrap-matrices (trekkingen x maanden) werken.
"""
import numpy as np
import pandas as pd


def sharpe(r, rf):
    ex = np.asarray(r, float) - np.asarray(rf, float)
    sd = ex.std(axis=-1, ddof=1)
    return np.where(sd > 0, ex.mean(axis=-1) / np.where(sd > 0, sd, 1) * np.sqrt(12), np.nan)


def max_drawdown(r):
    """Maximale daling in % (negatief), op maandslotwaarden, startwaarde 1 inbegrepen."""
    r = np.asarray(r, float)
    eq = np.cumprod(1 + r, axis=-1)
    eq = np.concatenate([np.ones(eq.shape[:-1] + (1,)), eq], axis=-1)
    peak = np.maximum.accumulate(eq, axis=-1)
    return ((eq / peak - 1).min(axis=-1)) * 100


def cagr(r):
    r = np.asarray(r, float)
    years = r.shape[-1] / 12
    return (np.prod(1 + r, axis=-1) ** (1 / years) - 1) * 100


def vol(r):
    return np.asarray(r, float).std(axis=-1, ddof=1) * np.sqrt(12) * 100


def sortino(r, rf):
    ex = np.asarray(r, float) - np.asarray(rf, float)
    down = np.sqrt((np.minimum(ex, 0) ** 2).mean(axis=-1))
    return np.where(down > 0, ex.mean(axis=-1) / np.where(down > 0, down, 1) * np.sqrt(12), np.nan)


def daily_mdd(values: np.ndarray) -> float:
    v = np.asarray(values, float)
    return float((v / np.maximum.accumulate(v) - 1).min() * 100)


def summary(r: pd.Series, rf: pd.Series) -> dict:
    """Alle kengetallen van één maandreeks (pandas, index = maandbegin)."""
    yr = (1 + r).groupby(r.index.year).prod() - 1
    c, m = float(cagr(r.to_numpy())), float(max_drawdown(r.to_numpy()))
    return {"cagr": c, "vol": float(vol(r.to_numpy())), "sharpe": float(sharpe(r.to_numpy(), rf.to_numpy())),
            "sortino": float(sortino(r.to_numpy(), rf.to_numpy())), "mdd": m,
            "calmar": c / abs(m) if m < 0 else np.nan,
            "worst_year": float(yr.min() * 100), "worst_year_at": int(yr.idxmin()),
            "years": {int(y): float(v * 100) for y, v in yr.items()}}


# ----------------------------- bootstrap ---------------------------------

def stationary_indices(T: int, n: int, mean_block: float, rng) -> np.ndarray:
    """n reeksen maand-indexen (n, T) volgens de stationaire bootstrap."""
    p = 1 / mean_block
    idx = np.empty((n, T), int)
    idx[:, 0] = rng.integers(0, T, n)
    new_block = rng.random((n, T)) < p
    starts = rng.integers(0, T, (n, T))
    for t in range(1, T):
        idx[:, t] = np.where(new_block[:, t], starts[:, t], (idx[:, t - 1] + 1) % T)
    return idx


def metric_diff(kind: str, r_strat, r_base, rf):
    """Verbetering (positief = beter) van de regel t.o.v. de baseline.
    kind 'sharpe': Sharpe(regel) - Sharpe(baseline); 'mdd': |MDD baseline| - |MDD regel| (procentpunt)."""
    if kind == "sharpe":
        return sharpe(r_strat, rf) - sharpe(r_base, rf)
    return max_drawdown(r_strat) - max_drawdown(r_base)


def bootstrap_diff(kind, r_strat, r_base, rf, idx) -> dict:
    """Puntschatting, 95%-interval en aandeel trekkingen met verbetering."""
    a, b, c = (np.asarray(x, float) for x in (r_strat, r_base, rf))
    est = float(metric_diff(kind, a, b, c))
    boot = metric_diff(kind, a[idx], b[idx], c[idx])
    lo, hi = np.nanpercentile(boot, [2.5, 97.5])
    return {"est": est, "lo": float(lo), "hi": float(hi), "p_improve": float(np.mean(boot > 0)),
            "se": float(np.nanstd(boot, ddof=1)), "boot": boot}


def reality_check(kind, primary_est: float, pairs: list, rf, idx) -> dict:
    """p-waarde: aandeel trekkingen waarin het grootste gecentreerde toevalsverschil over alle
    trials (d_j^b - d_j) minstens zo groot is als het verschil van de primaire configuratie.
    pairs: lijst (r_strat, r_base) van ALLE trials, elk met zijn eigen baseline."""
    c = np.asarray(rf, float)
    centered = []
    for a, b in pairs:
        a, b = np.asarray(a, float), np.asarray(b, float)
        d = metric_diff(kind, a, b, c)
        centered.append(metric_diff(kind, a[idx], b[idx], c[idx]) - d)
    mx = np.nanmax(np.vstack(centered), axis=0)
    return {"p": float(np.mean(mx >= primary_est)), "max_null_p95": float(np.nanpercentile(mx, 95)),
            "n_trials": len(pairs)}


def mde(se: float) -> float:
    """Kleinste effect dat je met 80% kans vindt bij tweezijdig 5%: (1,96 + 0,84) x SE."""
    return 2.8 * se


def memmel_se(sr1, sr2, rho, years) -> float:
    """Benadering (Jobson-Korkie, Memmel 2003) van de standaardfout van een Sharpe-verschil."""
    return float(np.sqrt((2 * (1 - rho) + 0.5 * (sr1 ** 2 + sr2 ** 2 - 2 * sr1 * sr2 * rho ** 2)) / years))
