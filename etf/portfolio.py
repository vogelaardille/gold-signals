"""Portefeuille-simulatie op dagbasis (PLAN3 §3).

Conventie:
- signaal op het slot van de laatste handelsdag van maand m (alleen koersen t/m die dag);
- uitvoering op het slot van de eerste handelsdag van maand m+1 (`lag=1`, standaard).
  Het rendement van die dag valt nog onder de oude gewichten;
- tussen twee uitvoeringen drijven de gewichten mee met de koersen;
- kosten = tarief x verhandeld bedrag (som |doel - meegedreven| over de risicovolle assets),
  afgeboekt op de uitvoeringsdag. Cash in- en uitstappen is gratis.

De simulatie kan meerdere portefeuilles tegelijk doorrekenen (eerste as van `w` = aantal
simulaties), zodat 1000 willekeurige-timing-simulaties snel gaan.
"""
import numpy as np
import pandas as pd


def month_end_dates(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """Laatste handelsdag van elke kalendermaand in de index."""
    s = pd.Series(index, index=index)
    return pd.DatetimeIndex(s.groupby(index.to_period("M")).max().to_numpy())


def month_end_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Slotkoers per asset op de laatste handelsdag van elke maand (NaN als nog niet genoteerd)."""
    return prices.loc[month_end_dates(prices.index)]


def exec_dates(signal_dates: pd.DatetimeIndex, index: pd.DatetimeIndex, lag: int = 1) -> pd.DatetimeIndex:
    """Uitvoeringsdag bij elk signaal: `lag` handelsdagen na de signaaldag (1 = eerste
    handelsdag van de volgende maand). Signalen zonder uitvoeringsdag in de index vallen weg."""
    pos = index.get_indexer(signal_dates)
    if (pos < 0).any():
        raise ValueError("signaaldag niet in de dagindex")
    pos = pos + lag
    return pd.DatetimeIndex([index[p] if p < len(index) else pd.NaT for p in pos])


def simulate(w, signal_dates, rets: pd.DataFrame, cash: pd.Series, cost: float, lag: int = 1,
             end=None) -> dict:
    """Simuleer portefeuilles.

    w: doelgewichten per signaaldag, vorm (signalen, assets) of (simulaties, signalen, assets),
       in dezelfde kolomvolgorde als `rets`. Rest (1 - som) = cash.
    signal_dates: de signaaldagen (rijen van w).
    rets: dagrendementen per asset (NaN = 0, gewicht moet dan 0 zijn).
    cash: dagrendement van cash.
    Start in cash op de eerste uitvoeringsdag (waarde 1 vóór de eerste aankoop).

    Geeft: values (simulaties, dagen), days, turnover en trades per uitvoering (simulaties, uitvoeringen),
    exec (uitvoeringsdagen)."""
    w = np.asarray(w, float)
    if w.ndim == 2:
        w = w[None]
    S, E, A = w.shape
    ex = exec_dates(pd.DatetimeIndex(signal_dates), rets.index, lag)
    keep = ~ex.isna()
    if end is not None:
        keep &= ex < pd.Timestamp(end)
    ex, w = ex[keep], w[:, keep]
    days = rets.index[(rets.index >= ex[0]) & ((rets.index < pd.Timestamp(end)) if end is not None else True)]
    R = np.nan_to_num(rets.loc[days].to_numpy(float))
    C = cash.reindex(days).to_numpy(float)
    epos = days.get_indexer(ex)
    is_exec = np.full(len(days), -1)
    is_exec[epos] = np.arange(len(ex))

    h = np.zeros((S, A))
    c = np.ones(S)
    values = np.empty((S, len(days)))
    turnover = np.zeros((S, len(ex)))
    trades = np.zeros((S, len(ex)), int)
    for t in range(len(days)):
        if t > 0:
            h = h * (1 + R[t])
            c = c * (1 + C[t])
        V = h.sum(1) + c
        k = is_exec[t]
        if k >= 0:
            target = w[:, k]
            drift = h / V[:, None]
            dw = np.abs(target - drift)
            turn = dw.sum(1)
            V = V * (1 - cost * turn)
            h = target * V[:, None]
            c = (1 - target.sum(1)) * V
            turnover[:, k] = turn
            trades[:, k] = (dw > 0.005).sum(1)
        values[:, t] = V
    return {"values": values, "days": days, "turnover": turnover, "trades": trades, "exec": ex}


def monthly_returns(values: np.ndarray, days: pd.DatetimeIndex, start, end) -> pd.DataFrame:
    """Kalendermaand-rendementen uit dagwaarden (simulaties als kolommen), van start t/m end (excl.).
    De eerste maand wordt gemeten t.o.v. de waarde 1 bij de start van de simulatie."""
    v = pd.DataFrame(np.asarray(values).T, index=days)
    me = v.groupby(days.to_period("M")).last()
    prev = pd.concat([pd.DataFrame(np.ones((1, v.shape[1])), index=[me.index[0] - 1]), me])
    r = (prev / prev.shift(1) - 1).iloc[1:]
    r.index = r.index.to_timestamp()
    return r[(r.index >= pd.Timestamp(start)) & (r.index < pd.Timestamp(end))]


def monthly_cash(cash: pd.Series, start, end) -> pd.Series:
    m = (1 + cash).groupby(cash.index.to_period("M")).prod() - 1
    m.index = m.index.to_timestamp()
    return m[(m.index >= pd.Timestamp(start)) & (m.index < pd.Timestamp(end))]
