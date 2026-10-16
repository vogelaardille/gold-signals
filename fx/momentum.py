"""Ronde 5: intraday momentum (PLAN5 §4). G1 = momentum van de dag tot nu toe, G2 = noise-area
breakout. Trades lopen via de ongewijzigde engine van ronde 4 (fills op bid/ask).

Richting = richting van de koers van het paar (+1 = long de basisvaluta).
"""
import numpy as np
import pandas as pd

from fx import engine

NY = engine.NY


def base_is_usd(pair: str) -> bool:
    return pair.startswith("USD/")


# ---------------------------------------------------------------------------
# G1 – momentum van de dag tot nu toe
# ---------------------------------------------------------------------------

def g1_setups(times: pd.DatetimeIndex, close: np.ndarray, open_: np.ndarray,
              day_open_hour: int, s_hour: int, x_hour: int) -> pd.DataFrame:
    """Per valutadag: entry-bar S, exit-bar X en het teken van het rendement t/m de close van bar S−1.
    Een dag valt weg als de 17:00-bar, S−1, S of X ontbreekt."""
    ny_hour = times.tz_convert(NY).hour
    a = np.flatnonzero(ny_hour == day_open_hour)
    t0 = times[a]
    s_t = engine.next_local_time(t0, NY, s_hour)
    x_t = engine.next_local_time(t0, NY, x_hour)
    s = times.get_indexer(s_t)
    x = times.get_indexer(x_t)
    ok = (s > 0) & (x > s)
    a, s, x = a[ok], s[ok], x[ok]
    ok = (times[s - 1] == times[s] - pd.Timedelta(hours=1)) & (s - 1 > a)
    a, s, x = a[ok], s[ok], x[ok]
    ret = close[s - 1] / open_[a] - 1
    d = np.sign(ret).astype(int)
    keep = d != 0
    return pd.DataFrame({"anchor": a[keep], "entry": s[keep], "exit": x[keep], "dir": d[keep]})


def g1_run(px: dict, pair: str, pip: float, slip: float, cfg5: dict, window, directions=None) -> pd.DataFrame:
    g1 = cfg5["g1"]
    st = g1_setups(px["time"], px["close"], px["open"], g1["day_open_ny_hour"], window[0], window[1])
    d = st["dir"].to_numpy() if directions is None else directions
    return engine.simulate(px, st["entry"].to_numpy(), d, pip, slip, base_is_usd(pair),
                           exit_idx=st["exit"].to_numpy())


# ---------------------------------------------------------------------------
# G2 – noise-area breakout
# ---------------------------------------------------------------------------

def g2_bands(px: dict, anchor_tz: str, anchor_hour: int, lookback: int, min_days: int,
             force_ny_hour: int) -> pd.DataFrame:
    """Per bar binnen een ankerdag: ankerdag, k (uren na het anker), O en σ_k.
    σ_k gebruikt alleen de `lookback` VOORGAANDE ankerdagen (niet vandaag)."""
    t = px["time"]
    local = t.tz_convert(anchor_tz)
    a_idx = np.flatnonzero(local.hour == anchor_hour)
    a_time = t[a_idx]
    end_time = engine.next_local_time(a_time, NY, force_ny_hour)  # einde van de ankerdag
    end_idx = t.searchsorted(end_time)
    rows = []
    for day, (ai, ei) in enumerate(zip(a_idx, end_idx)):
        if ei <= ai:
            continue
        idx = np.arange(ai, min(ei + 1, len(t)))  # t/m de bar van de geforceerde exit
        k = np.round((t[idx] - t[ai]) / pd.Timedelta(hours=1)).astype(int)
        rows.append(pd.DataFrame({"i": idx, "day": day, "k": k, "O": px["open"][ai], "end": ei}))
    b = pd.concat(rows, ignore_index=True)
    b["move"] = np.abs(px["close"][b["i"]] / b["O"] - 1)
    piv = b.pivot_table(index="day", columns="k", values="move", aggfunc="first")
    sigma = piv.shift(1).rolling(lookback, min_periods=min_days).mean()
    b["sigma"] = sigma.stack().reindex(pd.MultiIndex.from_arrays([b["day"], b["k"]])).to_numpy()
    return b


def g2_trades(px: dict, bands: pd.DataFrame, m: float, no_entry_hours) -> pd.DataFrame:
    """Toestandsmachine per ankerdag: entry na een close buiten de band, exit na een close terug
    in de band (of de geforceerde exit). Geeft entry-bar, richting en exit-bar."""
    b = bands.dropna(subset=["sigma"])
    close = px["close"]
    ny_hour = px["time"].tz_convert(NY).hour
    out = []
    for _, g in b.groupby("day", sort=True):
        i = g["i"].to_numpy()
        up = (g["O"] * (1 + m * g["sigma"])).to_numpy()
        lo = (g["O"] * (1 - m * g["sigma"])).to_numpy()
        end = int(g["end"].iloc[0])
        pos, entry = 0, None
        for j in range(len(i)):
            c = close[i[j]]
            nxt = i[j] + 1
            if pos == 0:
                sig = 1 if c > up[j] else (-1 if c < lo[j] else 0)
                if sig and nxt < end and ny_hour[nxt] not in no_entry_hours:
                    pos, entry = sig, nxt
            elif j and i[j] >= entry:
                back = (pos > 0 and c <= up[j]) or (pos < 0 and c >= lo[j])
                if back:
                    out.append((entry, pos, min(nxt, end)))
                    pos = 0
        if pos:
            out.append((entry, pos, end))
    return pd.DataFrame(out, columns=["entry", "dir", "exit"])


def g2_run(px: dict, pair: str, pip: float, slip: float, setups: pd.DataFrame, directions=None) -> pd.DataFrame:
    d = setups["dir"].to_numpy() if directions is None else directions
    return engine.simulate(px, setups["entry"].to_numpy(), d, pip, slip, base_is_usd(pair),
                           exit_idx=setups["exit"].to_numpy())
