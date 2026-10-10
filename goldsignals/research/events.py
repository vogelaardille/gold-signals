"""Zone-tests (events), hun uitkomst, en de vaste 1:2-setup. Zie research/PLAN.md.

Alles is 'gevectoriseerd' met numpy: in plaats van een for-lus per event rekenen we
voor alle events tegelijk. Dat is nodig omdat het nulmodel 200 keer dezelfde
berekening doet.

Notatie: candle i = de candle die de zone raakt. De zones komen uit de snapshot op het
sluitmoment van candle i-1, dus zonder kennis van candle i zelf.
side = +1 voor een support-test (long-setup), -1 voor een resistance-test (short).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

ZONE_ATTRS = ["timeframe", "confluence", "touches", "first_touch", "last_touch", "score"]


@dataclass
class Arrays:
    """De candles als losse numpy-arrays (snel indexeren)."""
    time: pd.DatetimeIndex
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray

    @classmethod
    def from_candles(cls, c: pd.DataFrame) -> "Arrays":
        return cls(c.index, *(c[k].to_numpy(float) for k in ("open", "high", "low", "close")))

    @property
    def n(self):
        return len(self.close)


def zone_table(market, method: str) -> pd.DataFrame:
    """Alle (candle, zone)-combinaties: per candle i de zones uit de snapshot van i-1."""
    snap = market.snapshots[method]
    snap = snap[snap["low"].notna()]
    prev_pos = market.close_time.get_indexer(pd.DatetimeIndex(snap["as_of"]))
    i = prev_pos + 1
    keep = (prev_pos >= 0) & (i < len(market.candles))
    t = snap.loc[keep, ["as_of", "low", "high", "atr_1h", "atr_1d"] + ZONE_ATTRS].copy()
    t.insert(0, "i", i[keep])
    return t.reset_index(drop=True)


def first_true(mask: np.ndarray) -> np.ndarray:
    """Per rij de eerste kolom waar mask True is; mask.shape[1] als er geen is."""
    any_ = mask.any(axis=1)
    return np.where(any_, mask.argmax(axis=1), mask.shape[1])


def window(arr: np.ndarray, start: np.ndarray, length: int) -> np.ndarray:
    """Matrix met arr[start + 0 .. start + length-1] per rij (start moet passen)."""
    return arr[start[:, None] + np.arange(length)[None, :]]


def detect_events(zt: pd.DataFrame, a: Arrays, shift: np.ndarray = None, max_i: int = None) -> pd.DataFrame:
    """Vind zone-tests. shift (per rij, in USD) verschuift de zones (nulmodel).
    max_i: alleen events met i <= max_i (zodat het uitkomstvenster in de periode past)."""
    low = zt["low"].to_numpy() + (0 if shift is None else shift)
    high = zt["high"].to_numpy() + (0 if shift is None else shift)
    i = zt["i"].to_numpy()
    prev_close = a.close[i - 1]
    support = (prev_close > high) & (a.low[i] <= high)
    resist = (prev_close < low) & (a.high[i] >= low)
    hit = support | resist
    if max_i is not None:
        hit &= i <= max_i
    ev = zt.loc[hit].copy()
    ev["zlow"], ev["zhigh"] = low[hit], high[hit]
    ev["side"] = np.where(support[hit], 1, -1)
    ev["time"] = a.time[ev["i"].to_numpy()]
    return ev.reset_index(drop=True)


def measure_outcomes(ev: pd.DataFrame, a: Arrays, rcfg: dict) -> pd.DataFrame:
    """Bounce/break-uitkomst en MFE/MAE over de volgende N candles."""
    if ev.empty:
        return ev.assign(outcome=pd.Series(dtype=str), bounce=0.0, brk=0.0, mfe=0.0, mae=0.0, t_break=0)
    n_h = rcfg["horizon_bars"]
    i = ev["i"].to_numpy()
    side = ev["side"].to_numpy()
    atr = ev["atr_1h"].to_numpy()
    near = np.where(side == 1, ev["zhigh"], ev["zlow"])   # kant waar de koers vandaan komt
    far = np.where(side == 1, ev["zlow"], ev["zhigh"])

    H, L, C = (window(x, i, n_h + 1) for x in (a.high, a.low, a.close))   # kolom 0 = candle i
    s = side[:, None]
    brk = s * (C - (far - side * rcfg["break_atr"] * atr)[:, None]) <= 0
    extreme = np.where(s == 1, H, L)
    bounce = s * (extreme - (near + side * rcfg["bounce_atr"] * atr)[:, None]) >= 0
    bounce[:, 0] = False                       # de test-candle zelf telt niet als bounce
    t_brk, t_bnc = first_true(brk), first_true(bounce)
    outcome = np.where(t_bnc < t_brk, "bounce", np.where(t_brk <= n_h, "break", "geen"))

    entry = a.open[i + 1]
    fav = np.where(s == 1, H[:, 1:], -L[:, 1:]).max(axis=1)
    adv = np.where(s == 1, -L[:, 1:], H[:, 1:]).max(axis=1)
    out = ev.copy()
    out["outcome"] = outcome
    out["bounce"] = (outcome == "bounce").astype(float)
    out["brk"] = (outcome == "break").astype(float)
    out["t_break"] = t_brk
    out["mfe"] = (fav - side * entry) / atr
    out["mae"] = (adv + side * entry) / atr
    return out


def simulate_trades(a: Arrays, i_sig: np.ndarray, side: np.ndarray, stop: np.ndarray,
                    rr: float, max_bars: int, cost: float) -> dict:
    """Vaste setup: entry op open[i_sig+1], stop gegeven, target = rr x risico.
    Raakt een candle SL en TP tegelijk, dan telt SL (conservatief). Opent een candle al
    voorbij de stop (gat), dan is de exit die open (slechter dan de stop).
    Geeft R netto: (winst - kosten) / (risico + kosten); een stop = precies -1R."""
    entry = a.open[i_sig + 1]
    risk = side * (entry - stop)
    target = entry + side * rr * risk
    H, L, O = (window(x, i_sig + 1, max_bars) for x in (a.high, a.low, a.open))
    s = side[:, None]
    sl_hit = np.where(s == 1, L <= stop[:, None], H >= stop[:, None])
    tp_hit = np.where(s == 1, H >= target[:, None], L <= target[:, None])
    t_sl, t_tp = first_true(sl_hit), first_true(tp_hit)
    rows = np.arange(len(i_sig))
    t_sl_c = np.minimum(t_sl, max_bars - 1)
    open_at_sl = O[rows, t_sl_c]
    sl_exit = np.where(side == 1, np.minimum(open_at_sl, stop), np.maximum(open_at_sl, stop))
    last_close = a.close[i_sig + max_bars]
    exit_px = np.where(t_sl <= t_tp, np.where(t_sl < max_bars, sl_exit, last_close),
                       np.where(t_tp < max_bars, target, last_close))
    pnl = side * (exit_px - entry)
    r_net = (pnl - cost) / (risk + cost)
    r_gross = pnl / risk
    result = np.where(t_sl <= t_tp, np.where(t_sl < max_bars, "sl", "tijd"),
                      np.where(t_tp < max_bars, "tp", "tijd"))
    return {"entry": entry, "risk": risk, "r": r_net, "r_gross": r_gross, "result": result}


def zone_setup(ev: pd.DataFrame, a: Arrays, rcfg: dict, cost: float) -> pd.DataFrame:
    """De vaste 1:2-setup op elk event (zie PLAN.md). Kolom 'r' = NaN als er geen trade is."""
    out = ev.copy()
    out["r"], out["r_gross"] = np.nan, np.nan
    if ev.empty:
        return out
    i = ev["i"].to_numpy()
    side = ev["side"].to_numpy()
    atr = ev["atr_1h"].to_numpy()
    far = np.where(side == 1, ev["zlow"], ev["zhigh"])
    stop = far - side * rcfg["setup_stop_atr"] * atr
    held = side * (a.close[i] - far) > 0                     # zone niet doorgebroken op slot
    entry = a.open[i + 1]
    ok = held & (side * (entry - stop) >= rcfg["setup_min_risk_atr"] * atr)
    if ok.any():
        sim = simulate_trades(a, i[ok], side[ok], stop[ok], rcfg["setup_rr"], rcfg["setup_max_bars"], cost)
        out.loc[ok, "r"] = sim["r"]
        out.loc[ok, "r_gross"] = sim["r_gross"]
        out.loc[ok, "risk_atr"] = sim["risk"] / atr[ok]
    return out


def repeated_flag(ev: pd.DataFrame, window_bars: int) -> np.ndarray:
    """True als er in de window_bars candles ervoor een event was op een overlappende zone."""
    order = np.argsort(ev["i"].to_numpy(), kind="stable")
    i = ev["i"].to_numpy()[order]
    lo, hi = ev["zlow"].to_numpy()[order], ev["zhigh"].to_numpy()[order]
    rep = np.zeros(len(i), bool)
    start = np.searchsorted(i, i - window_bars, side="left")
    for k in range(len(i)):
        s = start[k]
        prev = slice(s, k)
        prev_mask = i[prev] < i[k]
        if prev_mask.any():
            rep[k] = bool(((lo[prev][prev_mask] <= hi[k]) & (hi[prev][prev_mask] >= lo[k])).any())
    out = np.empty(len(i), bool)
    out[order] = rep
    return out


def null_shifts(zt: pd.DataFrame, rcfg: dict, rng: np.random.Generator) -> np.ndarray:
    """Nulmodel: per kalendermaand een vaste verschuiving van de hele zone-set.
    Grootte uniform in [min, max] x daily ATR (aan het begin van die maand), teken willekeurig."""
    month = pd.DatetimeIndex(zt["as_of"]).tz_localize(None).to_period("M")
    codes, uniques = pd.factorize(month)
    atr_month = zt.groupby(codes)["atr_1d"].first().to_numpy()
    mag = rng.uniform(rcfg["null_offset_min_atr_1d"], rcfg["null_offset_max_atr_1d"], len(uniques))
    sign = rng.choice([-1.0, 1.0], len(uniques))
    return (sign * mag * atr_month)[codes]
