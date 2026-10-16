"""Ronde 4: de drie families uit PLAN4 §4. Elke functie geeft trades (via fx.engine.simulate).

Signalen gebruiken alleen mid-candles t/m de signaalbar; de entry is altijd een latere bar.
"""
import numpy as np
import pandas as pd

from fx import engine
from fx.data import in_fx_session

BASE_IS_USD = {"EUR/USD": False, "GBP/USD": False, "USD/JPY": True}


def _usd_to_base(pair: str, usd_direction: int) -> int:
    """+1 = long USD. In EUR/USD is dat short de basisvaluta, in USD/JPY long."""
    return usd_direction if BASE_IS_USD[pair] else -usd_direction


# ---------------------------------------------------------------------------
# F1 – fix-reversal: vaste vensters
# ---------------------------------------------------------------------------

def f1_windows(times: pd.DatetimeIndex, leg: dict, shift_hours: int = 0):
    """Entry- en exit-index per dag voor één been. Een dag valt weg als de entry-bar ontbreekt,
    als het exitmoment buiten de handelssessie valt, of als de trade over 17:00 NY zou lopen.
    shift_hours: alleen voor de placebo (zelfde lengte, ander startuur)."""
    etz, eh = leg["entry"]
    xtz, xh = leg["exit"]
    days = pd.date_range(times[0].tz_convert(etz).date(), times[-1].tz_convert(etz).date(), freq="D")
    entry_t = engine.local_to_utc(days + pd.Timedelta(hours=eh), etz)
    exit_t = engine.next_local_time(entry_t, xtz, xh)
    if shift_hours:
        entry_t, exit_t = entry_t + pd.Timedelta(hours=shift_hours), exit_t + pd.Timedelta(hours=shift_hours)
    ei = times.get_indexer(entry_t)
    xi = times.searchsorted(exit_t)  # pandas rekent tijdseenheden (ms/us) om
    ok = (ei >= 0) & (xi < len(times)) & in_fx_session(exit_t)
    ei, xi = ei[ok], xi[ok]
    same_day = engine.trading_day(times[ei]) == engine.trading_day(times[xi])
    return ei[same_day], xi[same_day]


def f1_leg(px: dict, pair: str, leg: dict, pip: float, slip: float, shift_hours: int = 0) -> pd.DataFrame:
    ei, xi = f1_windows(px["time"], leg, shift_hours)
    d = np.full(len(ei), _usd_to_base(pair, leg["usd"]))
    return engine.simulate(px, ei, d, pip, slip, BASE_IS_USD[pair], exit_idx=xi)


# ---------------------------------------------------------------------------
# F2 – ronde getallen
# ---------------------------------------------------------------------------

def atr(px: dict, period: int) -> np.ndarray:
    """Gemiddelde true range over de laatste `period` bars t/m deze bar (causaal, mid)."""
    h, l, c = px["high"], px["low"], px["close"]
    cp = np.r_[np.nan, c[:-1]]
    tr = np.nanmax(np.vstack([h - l, np.abs(h - cp), np.abs(l - cp)]), axis=0)
    return pd.Series(tr).rolling(period).mean().to_numpy()


def f2_signals(px: dict, step: float, offset: float, variant: str, fresh_bars: int):
    """Signaalbars en richting (+1 long, −1 short) voor niveaus offset + k·step.

    Vers niveau = niet geraakt in de `fresh_bars` bars vóór de signaalbar. Omdat 1h-candles
    op elkaar aansluiten, is dat hetzelfde als: het niveau ligt boven het hoogste high (of
    onder het laagste low) van die bars."""
    h, l, c = px["high"], px["low"], px["close"]
    cp = np.r_[np.nan, c[:-1]]
    roll_hi = pd.Series(h).shift(1).rolling(fresh_bars).max().to_numpy()
    roll_lo = pd.Series(l).shift(1).rolling(fresh_bars).min().to_numpy()
    above = lambda x: offset + (np.floor((x - offset) / step) + 1) * step  # kleinste niveau > x
    below = lambda x: offset + (np.ceil((x - offset) / step) - 1) * step   # grootste niveau < x
    with np.errstate(invalid="ignore"):
        if variant == "bounce":
            lr = above(np.maximum(cp, c))
            short = (h >= lr) & (lr > roll_hi)
            ls = below(np.minimum(cp, c))
            long_ = (l <= ls) & (ls < roll_lo)
            both = short & long_
            short, long_ = short & ~both, long_ & ~both
        elif variant == "breakout":
            lu = below(c)
            long_ = (lu > cp) & (lu > roll_hi)
            ld = above(c)
            short = (ld < cp) & (ld < roll_lo)
        else:
            raise ValueError(variant)
    sig = np.flatnonzero(long_ | short)
    return sig, np.where(long_[sig], 1, -1)


def _entry_allowed(times: pd.DatetimeIndex, entry_idx: np.ndarray, no_entry_hours) -> np.ndarray:
    hours = times[entry_idx].tz_convert(engine.NY).hour
    return ~np.isin(hours, no_entry_hours)


def f2_run(px: dict, pair: str, cfg: dict, level: str, variant: str, target_r: float,
           slip: float, offset_frac: float = 0.0) -> pd.DataFrame:
    f2, ex = cfg["f2"], cfg["execution"]
    step = f2["level_step"][pair] / (1 if level == "00" else 2)
    sig, d = f2_signals(px, step, offset_frac * step, variant, f2["fresh_bars"])
    a = atr(px, f2["atr_period"])
    e = sig + 1
    ok = (e < len(px["time"])) & ~np.isnan(a[sig])
    sig, d, e = sig[ok], d[ok], e[ok]
    ok = _entry_allowed(px["time"], e, ex["no_entry_ny_hours"])
    sig, d, e = sig[ok], d[ok], e[ok]
    return engine.simulate(px, e, d, cfg["pairs"][pair], slip, BASE_IS_USD[pair],
                           force_ny_hour=ex["force_exit_ny_hour"],
                           stop_dist=f2["stop_atr"] * a[sig], target_r=target_r)


def f2_null_offsets(cfg: dict, level: str, rng: np.random.Generator) -> np.ndarray:
    """Willekeurige verschuivingen δ (als fractie van de niveau-afstand), PLAN4 §4."""
    f2 = cfg["f2"]
    parts = f2["null_delta_00"] if level == "00" else f2["null_delta_0050"]
    lengths = np.array([b - a for a, b in parts])
    which = rng.choice(len(parts), size=f2["null_replicates"], p=lengths / lengths.sum())
    lo = np.array([parts[i][0] for i in which])
    return lo + rng.random(len(which)) * lengths[which]


# ---------------------------------------------------------------------------
# F3 – London breakout
# ---------------------------------------------------------------------------

def f3_setups(px: dict, cfg: dict) -> pd.DataFrame:
    """Per Londense dag: de range (00:00–06:00) en het eerste signaal (07:00–10:00)."""
    f3 = cfg["f3"]
    t = px["time"]
    lon = t.tz_convert("Europe/London")
    d = pd.DataFrame({"h": px["high"], "l": px["low"], "c": px["close"], "lh": lon.hour,
                      "day": lon.normalize().tz_localize(None), "i": np.arange(len(t))})
    r0, r1 = f3["range_london_hours"]
    s0, s1 = f3["signal_london_hours"]
    rng = d[d.lh.between(r0, r1)].groupby("day").agg(rh=("h", "max"), rl=("l", "min"), n=("h", "size"))
    rng = rng[rng.n == r1 - r0 + 1]
    sig = d[d.lh.between(s0, s1)].join(rng, on="day", how="inner")
    sig["dir"] = np.where(sig.c > sig.rh, 1, np.where(sig.c < sig.rl, -1, 0))
    first = sig[sig.dir != 0].groupby("day").head(1)
    return first[["day", "i", "dir", "rh", "rl"]].reset_index(drop=True), sig[["day", "i"]]


def _f3_stop(setups: pd.DataFrame, stop: str) -> np.ndarray:
    if stop == "opposite":
        return np.where(setups.dir > 0, setups.rl, setups.rh)
    return ((setups.rh + setups.rl) / 2).to_numpy()


def f3_run(px: dict, pair: str, cfg: dict, stop: str, target_r, slip: float) -> pd.DataFrame:
    setups, _ = f3_setups(px, cfg)
    e = setups.i.to_numpy() + 1
    ok = e < len(px["time"])
    setups, e = setups[ok], e[ok]
    return engine.simulate(px, e, setups.dir.to_numpy(), cfg["pairs"][pair], slip, BASE_IS_USD[pair],
                           force_ny_hour=cfg["execution"]["force_exit_ny_hour"],
                           stop_level=_f3_stop(setups, stop), target_r=target_r)


def f3_null_prep(px: dict, cfg: dict, stop: str) -> dict:
    """Wat elke F3-nulreplicatie nodig heeft (één keer per paar en stoptype uitgerekend)."""
    setups, window = f3_setups(px, cfg)
    setups = setups[setups.i + 1 < len(px["time"])].reset_index(drop=True)
    dist = np.abs(px["open"][setups.i.to_numpy() + 1] - _f3_stop(setups, stop))
    w = window[window.day.isin(setups.day)].sort_values(["day", "i"])
    g = w.groupby("day").i.agg(["size"]).reindex(setups.day)
    starts = np.r_[0, np.cumsum(g["size"].to_numpy())[:-1]]
    return {"dist": dist, "bars": w.i.to_numpy(), "start": starts, "count": g["size"].to_numpy()}


def f3_null(px: dict, pair: str, cfg: dict, target_r, slip: float, rng: np.random.Generator,
            prep: dict) -> pd.DataFrame:
    """Eén replicatie: op dezelfde dagen een willekeurige signaalbar (07–10 Londen) en richting,
    met dezelfde stopafstand (in prijs) als de echte trade van die dag."""
    pos = prep["start"] + np.floor(rng.random(len(prep["start"])) * prep["count"]).astype(int)
    e = prep["bars"][pos] + 1
    ok = e < len(px["time"])
    d = rng.choice([-1, 1], size=len(e))
    return engine.simulate(px, e[ok], d[ok], cfg["pairs"][pair], slip, BASE_IS_USD[pair],
                           force_ny_hour=cfg["execution"]["force_exit_ny_hour"],
                           stop_dist=prep["dist"][ok], target_r=target_r)
