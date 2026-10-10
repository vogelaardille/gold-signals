"""Ronde 2: de vier strategie-families als signaal-arrays (zie research/round2/PLAN2.md §4).

Elke familie geeft per candle (op het SLOT van die candle):
- entry: +1 (long), -1 (short) of 0
- stop_dist: afstand entry -> initiële stop (in USD), per candle
- exit-regels: vaste target (niveau of veelvoud van R), ATR-trailing stop, tijdstop
De engine (engine.py) voert ze uit. Random entries met dezelfde exits gebruiken
dezelfde exit-arrays, alleen op willekeurige candles.
"""
import itertools
from dataclasses import dataclass

import numpy as np
import pandas as pd

from goldsignals.round2 import indicators as ind
from goldsignals.sr.pivots import atr


@dataclass
class Signals:
    entry: np.ndarray                 # int8: +1 / -1 / 0
    stop_dist: np.ndarray             # float, > 0 (NaN = niet handelbaar)
    target_level: np.ndarray = None   # vast target-niveau per candle (F3), of None
    target_r: float = None            # target als veelvoud van het risico (F2), of None
    trail_k: float = None             # ATR-trailing (chandelier): k x trail_atr
    trail_atr: np.ndarray = None
    time_stop: int = None             # exit op het slot na zoveel candles
    dir_from_target: bool = False     # random-baseline: richting = kant van het target


def variants(cfg: dict, family: str) -> list:
    """Alle varianten (dicts) van een familie, in vaste volgorde."""
    f = cfg["round2"]["families"][family]
    if family == "F1":
        return [{"family": "F1", "entry": e, "trail_atr": k} for e, k in itertools.product(f["entry"], f["trail_atr"])]
    if family == "F2":
        return [{"family": "F2", "timeframe": tf, "squeeze_pct": p, "exit": x}
                for tf, p, x in itertools.product(f["timeframe"], f["squeeze_pct"], f["exit"])]
    if family == "F3":
        return [{"family": "F3", "timeframe": tf, "regime": rg, "band_z": z, "stop_atr": k}
                for tf, rg, z, k in itertools.product(f["timeframe"], f["regime"], f["band_z"], f["stop_atr"])]
    if family == "F4":
        f1 = cfg["round2"]["families"]["F1"]
        return [{"family": "F4", "entry": e, "trail_atr": k, "filter": flt}
                for e, k, flt in itertools.product(f1["entry"], f1["trail_atr"], f["filter"])]
    raise ValueError(family)


def timeframe_of(v: dict) -> str:
    return v.get("timeframe", "1d")


def variant_id(v: dict) -> str:
    return "|".join(f"{k}={v[k]}" for k in v)


# ---------------------------------------------------------------------------

def trend_entry(b: pd.DataFrame, entry: str) -> np.ndarray:
    """F1-entry: Donchian-breakout of tijdreeks-momentum, op het daily slot."""
    c = b["close"]
    if entry.startswith("donchian"):
        n = int(entry.replace("donchian", ""))
        up = c > b["high"].shift(1).rolling(n).max()      # boven het hoogste high van de VORIGE n dagen
        dn = c < b["low"].shift(1).rolling(n).min()
    else:
        lookback = {"tsmom3": 63, "tsmom6": 126, "tsmom12": 252}[entry]
        ret = c / c.shift(lookback) - 1
        up, dn = ret > 0, ret < 0
    return np.where(up, 1, np.where(dn, -1, 0)).astype(np.int8)


def f1(b: pd.DataFrame, v: dict, cfg: dict, long_only: bool = False, allow: np.ndarray = None) -> Signals:
    a = atr(b, cfg["round2"]["families"]["F1"]["atr_period"]).to_numpy()
    e = trend_entry(b, v["entry"])
    if long_only:
        e = np.where(e == 1, 1, 0).astype(np.int8)
    if allow is not None:
        e = np.where(allow, e, 0).astype(np.int8)
    k = float(v["trail_atr"])
    return Signals(e, k * a, trail_k=k, trail_atr=a)


def f2(b: pd.DataFrame, v: dict, cfg: dict) -> Signals:
    p = cfg["round2"]["families"]["F2"]
    a = atr(b, 14)
    lower, mid, upper = ind.bollinger(b["close"], 20, 2.0)
    width_pct = ind.pct_rank_1y((upper - lower) / mid)
    squeeze = (width_pct <= v["squeeze_pct"]).astype(float)
    recent = squeeze.shift(1).rolling(p["squeeze_lookback_bars"]).max() > 0   # compressie in de 5 candles ervoor
    n = p["breakout_bars"]
    up = (b["close"] > b["high"].shift(1).rolling(n).max()) & recent
    dn = (b["close"] < b["low"].shift(1).rolling(n).min()) & recent
    e = np.where(up, 1, np.where(dn, -1, 0)).astype(np.int8)
    stop = p["stop_atr"] * a.to_numpy()
    if v["exit"] == "target_2R":
        return Signals(e, stop, target_r=2.0)
    return Signals(e, stop, trail_k=3.0, trail_atr=a.to_numpy())


def f3(b: pd.DataFrame, v: dict, cfg: dict) -> Signals:
    p = cfg["round2"]["families"]["F3"]
    a = atr(b, 14)
    lower, mid, upper = ind.bollinger(b["close"], 20, v["band_z"])
    if v["regime"] == "adx":
        calm = ind.adx(b, 14) < p["adx_max"]
    else:
        calm = ind.pct_rank_1y(a / b["close"]) < p["atr_pct_max"]
    long_ = (b["close"] < lower) & calm
    short = (b["close"] > upper) & calm
    e = np.where(long_, 1, np.where(short, -1, 0)).astype(np.int8)
    return Signals(e, v["stop_atr"] * a.to_numpy(), target_level=mid.to_numpy(),
                   time_stop=p["time_stop_bars"], dir_from_target=True)


def macro_allow(b: pd.DataFrame, flt: str, cfg: dict) -> np.ndarray:
    """F4-filter: long alleen als de reële rente / dollar de afgelopen 20 handelsdagen daalde."""
    if flt == "geen":
        return np.ones(len(b), bool)
    from goldsignals.round2.data import fred
    series = {"reele_rente": "DFII10", "dollar": "DTWEXBGS"}[flt]
    lag = cfg["round2"]["macro_lag_days"][series]
    chg = ind.macro_change(fred(series), lag, cfg["round2"]["families"]["F4"]["change_days"], b["close_time"])
    return np.nan_to_num(chg, nan=1.0) < 0     # onbekend = niet toegestaan


def signals(b: pd.DataFrame, v: dict, cfg: dict) -> Signals:
    fam = v["family"]
    if fam == "F1":
        return f1(b, v, cfg)
    if fam == "F2":
        return f2(b, v, cfg)
    if fam == "F3":
        return f3(b, v, cfg)
    if fam == "F4":
        return f1(b, v, cfg, long_only=True, allow=macro_allow(b, v["filter"], cfg))
    raise ValueError(fam)
