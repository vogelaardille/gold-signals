"""Doelgewichten per signaaldag (maandslot) voor de families en baselines (PLAN3 §4-5).

Alle functies krijgen alleen koersen t/m de signaaldag: `me` = maandslotkoersen
(rij = laatste handelsdag van de maand). Uitvoering pas op de volgende handelsdag
(zie portfolio.simulate). Uitkomst: DataFrame met gewichten (rijen = signaaldagen,
kolommen = assets); 1 - som = cash.
"""
import numpy as np
import pandas as pd


def available(me: pd.DataFrame, min_month_ends: int) -> pd.DataFrame:
    """True als de asset op dat maandslot al >= min_month_ends maandsloten heeft (incl. deze)."""
    return me.notna().cumsum() >= min_month_ends


def equal_weight(avail: pd.DataFrame) -> pd.DataFrame:
    k = avail.sum(axis=1).replace(0, np.nan)
    return avail.astype(float).div(k, axis=0).fillna(0.0)


def fixed_weights(avail: pd.DataFrame, weights: dict) -> pd.DataFrame:
    """Vaste gewichten (bijv. 60/40); een asset die nog niet meedoet krijgt 0 (dat deel = cash)."""
    w = pd.DataFrame(0.0, index=avail.index, columns=avail.columns)
    for a, x in weights.items():
        w[a] = np.where(avail[a], x, 0.0)
    return w


def single_asset(avail: pd.DataFrame, asset: str) -> pd.DataFrame:
    return fixed_weights(avail, {asset: 1.0})


# ----------------------------- F1 trendfilter -----------------------------

def trend_on(me: pd.DataFrame, n: int) -> pd.DataFrame:
    """Maandslot boven het gemiddelde van de laatste n maandsloten (incl. dit slot)."""
    sma = me.rolling(n, min_periods=n).mean()
    return me > sma


def f1_trend(me, avail, n) -> pd.DataFrame:
    """Elke asset 1/K als hij boven zijn n-maands gemiddelde ligt, anders dat deel cash."""
    on = trend_on(me, n) & avail
    k = avail.sum(axis=1).replace(0, np.nan)
    return on.astype(float).div(k, axis=0).fillna(0.0)


# ----------------------------- F2 dual momentum ---------------------------

def momentum(me: pd.DataFrame, lookback: int) -> pd.DataFrame:
    return me / me.shift(lookback) - 1


def f2_selected(me, avail, k, lookback, cash_ret: pd.Series) -> pd.DataFrame:
    """True voor de top-k assets op `lookback`-maands rendement, als dat boven cash ligt."""
    mom = momentum(me, lookback).where(avail)
    sel = pd.DataFrame(False, index=me.index, columns=me.columns)
    for d in me.index:
        row = mom.loc[d].dropna()
        if row.empty:
            continue
        top = row.sort_values(ascending=False, kind="mergesort").iloc[:k]
        ok = top[top > cash_ret.get(d, np.nan)]
        sel.loc[d, ok.index] = True
    return sel


def f2_dual_momentum(me, avail, k, lookback, cash_ret) -> pd.DataFrame:
    return f2_selected(me, avail, k, lookback, cash_ret).astype(float) / k


# ----------------------------- F3 volatility targeting --------------------

def realized_vol(base_w: pd.DataFrame, rets: pd.DataFrame, window: int) -> pd.Series:
    """Jaarvolatiliteit van de basisportefeuille (huidige basisgewichten) over de laatste
    `window` handelsdagen t/m de signaaldag."""
    out = {}
    idx = rets.index
    for d in base_w.index:
        p = idx.get_loc(d)
        if p + 1 < window:
            out[d] = np.nan
            continue
        r = np.nan_to_num(rets.iloc[p + 1 - window:p + 1].to_numpy(float)) @ base_w.loc[d].to_numpy(float)
        out[d] = float(np.std(r, ddof=1) * np.sqrt(252))
    return pd.Series(out)


def f3_exposure(base_w, rets, target, window, max_exposure=1.0) -> pd.Series:
    vol = realized_vol(base_w, rets, window)
    return (target / vol).clip(upper=max_exposure).fillna(0.0)


def f3_vol_target(base_w, rets, target, window, max_exposure=1.0) -> pd.DataFrame:
    e = f3_exposure(base_w, rets, target, window, max_exposure)
    return base_w.mul(e, axis=0)


# ----------------------------- willekeurige timing ------------------------

def circular_shift(x: np.ndarray, rng, min_shift: int) -> np.ndarray:
    """Verschuif een reeks circulair met een willekeurig aantal stappen in [min_shift, n - min_shift]."""
    n = len(x)
    if n <= 2 * min_shift:
        return x.copy()
    return np.roll(x, rng.integers(min_shift, n - min_shift + 1))


def random_timing_assets(indicator: pd.DataFrame, avail: pd.DataFrame, unit: pd.DataFrame,
                         n: int, rng, min_shift: int) -> np.ndarray:
    """F1/F2: per asset de aan/uit-reeks circulair verschuiven binnen de maanden dat hij meedoet.
    Gewicht = aan x unit (1/K bij F1, 1/k bij F2). Som > 1 -> naar rato omlaag.
    Uitkomst: array (n, signalen, assets)."""
    ind = indicator.to_numpy(float)
    av = avail.to_numpy(bool)
    u = unit.to_numpy(float)
    out = np.zeros((n,) + ind.shape)
    for s in range(n):
        sh = np.zeros_like(ind)
        for a in range(ind.shape[1]):
            rows = np.flatnonzero(av[:, a])
            if len(rows):
                sh[rows, a] = circular_shift(ind[rows, a], rng, min_shift)
        w = sh * u
        tot = w.sum(1, keepdims=True)
        out[s] = np.where(tot > 1, w / np.where(tot > 0, tot, 1), w)
    return out


def random_timing_exposure(exposure: pd.Series, base_w: pd.DataFrame, n: int, rng, min_shift: int) -> np.ndarray:
    """F3: de reeks blootstellingen als geheel circulair verschuiven; basisgewichten blijven op hun tijd."""
    e = exposure.to_numpy(float)
    b = base_w.to_numpy(float)
    return np.stack([b * circular_shift(e, rng, min_shift)[:, None] for _ in range(n)])
