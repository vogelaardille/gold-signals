"""Ronde 4: backtest-engine voor valuta (PLAN4 §3).

- Entry op de open van de entry-bar: long koopt op de ASK, short verkoopt op de BID, plus
  slippage. Exit andersom (long verkoopt op de bid, short koopt terug op de ask). Zo zit de
  echte spread van dát uur in elke trade.
- Stop en target worden getoetst op de kant waarop je zou sluiten (bid-candle voor long,
  ask-candle voor short). Binnen één bar gaat de stop vóór het target. Opent een bar al
  voorbij de stop (of het target), dan is de exit op die open.
- Zonder stop/target: exit op de open van de exit-bar (tijdsexit).
- Max. 1 open trade: kandidaten worden op volgorde gefilterd (een trade mag pas openen als
  de vorige gesloten is).

Alles is gevectoriseerd met numpy, omdat de nulmodellen duizenden runs vragen.
"""
import numpy as np
import pandas as pd

NY = "America/New_York"


def prices(df: pd.DataFrame) -> dict:
    """Numpy-arrays van een geladen paar (fx.data.load_pair)."""
    out = {c: df[c].to_numpy(dtype=float) for c in df.columns if c != "volume"}
    out["time"] = df.index
    return out


def trading_day(times: pd.DatetimeIndex) -> np.ndarray:
    """Handelsdag in valuta: een dag loopt van 17:00 tot 17:00 New York.
    (+7 uur schuift 17:00 NY naar middernacht.)"""
    return np.asarray((times.tz_convert(NY).tz_localize(None) + pd.Timedelta(hours=7)).normalize(),
                      dtype="datetime64[D]")


def local_to_utc(naive: pd.DatetimeIndex, tz: str) -> pd.DatetimeIndex:
    """Lokale kloktijd (zonder tijdzone) naar UTC, zomertijd-bewust."""
    return naive.tz_localize(tz, ambiguous=True, nonexistent="shift_forward").tz_convert("UTC")


def next_local_time(after: pd.DatetimeIndex, tz: str, hour: int) -> pd.DatetimeIndex:
    """Eerste moment ná `after` waarop het in zone tz precies `hour`:00 is."""
    local = after.tz_convert(tz).tz_localize(None)
    cand = local.normalize() + pd.Timedelta(hours=hour)
    cand = cand.where(cand > local, cand + pd.Timedelta(days=1))
    return local_to_utc(pd.DatetimeIndex(cand), tz)


def force_exit_index(times: pd.DatetimeIndex, entry_idx: np.ndarray, ny_hour: int) -> np.ndarray:
    """Index van de eerste bar op of na het eerstvolgende `ny_hour`:00 NY na de entry."""
    force = next_local_time(times[entry_idx], NY, ny_hour)
    # pandas' searchsorted rekent tijdseenheden (ms/us/ns) om; ruwe asi8-getallen niet
    return times.searchsorted(force)


def returns_bp(base_is_usd: bool, direction: np.ndarray, entry: np.ndarray, exit_: np.ndarray) -> np.ndarray:
    """Winst in USD als fractie van de nominale waarde (in USD) bij entry, in basispunten.
    direction +1 = long de basisvaluta (EUR in EUR/USD, USD in USD/JPY)."""
    if base_is_usd:  # USD/JPY: winst in yen, omgerekend tegen de exitkoers
        r = np.where(direction > 0, 1 - entry / exit_, entry / exit_ - 1)
    else:            # EUR/USD, GBP/USD: winst direct in USD
        r = np.where(direction > 0, exit_ / entry - 1, 1 - exit_ / entry)
    return r * 1e4


def simulate(px: dict, entry_idx, direction, pip: float, slip_pips: float, base_is_usd: bool,
             exit_idx=None, force_ny_hour: int = 16, stop_level=None, stop_dist=None,
             target_r=None) -> pd.DataFrame:
    """Simuleer kandidaat-trades en houd max. 1 open trade over.

    entry_idx: bar waarop (op de open) wordt ingestapt. exit_idx: tijdsexit (open van die bar);
    zonder exit_idx geldt de geforceerde exit op `force_ny_hour`:00 NY.
    stop_level (prijs) of stop_dist (afstand vanaf de fill); target_r = target in R (of None).
    """
    e = np.asarray(entry_idx, dtype=np.int64)
    d = np.asarray(direction, dtype=np.int64)
    n = len(px["time"])
    order = np.argsort(e, kind="stable")
    e, d = e[order], d[order]
    pick = lambda a: None if a is None else np.broadcast_to(np.asarray(a, dtype=float), (len(order),))[order]
    stop_level, stop_dist = pick(stop_level), pick(stop_dist)
    target_r = None if target_r is None else float(target_r)

    lim = (np.asarray(exit_idx, dtype=np.int64)[order] if exit_idx is not None
           else force_exit_index(px["time"], np.minimum(e, n - 1), force_ny_hour))
    ok = (e < n) & (lim > e) & (lim < n)
    e, d, lim = e[ok], d[ok], lim[ok]
    if stop_level is not None:
        stop_level = stop_level[ok]
    if stop_dist is not None:
        stop_dist = stop_dist[ok]
    if len(e) == 0:
        return pd.DataFrame()

    slip = slip_pips * pip
    long = d > 0
    fill = np.where(long, px["ask_open"][e] + slip, px["bid_open"][e] - slip)

    exit_bar = lim.copy()
    exit_px = np.where(long, px["bid_open"][lim] - slip, px["ask_open"][lim] + slip)
    reason = np.full(len(e), "time", dtype=object)
    free_from = lim.copy()
    risk = np.full(len(e), np.nan)

    if stop_level is not None or stop_dist is not None:
        stop = stop_level if stop_level is not None else np.where(long, fill - stop_dist, fill + stop_dist)
        risk = np.where(long, fill - stop, stop - fill)
        valid = risk > 0
        target = (np.where(long, fill + target_r * risk, fill - target_r * risk)
                  if target_r is not None else np.full(len(e), np.nan))
        k = int((lim - e).max())
        idx = np.minimum(e[:, None] + np.arange(k)[None, :], n - 1)
        inside = (e[:, None] + np.arange(k)[None, :]) < lim[:, None]
        lo = np.where(long[:, None], px["bid_low"][idx], px["ask_low"][idx])
        hi = np.where(long[:, None], px["bid_high"][idx], px["ask_high"][idx])
        stop_hit = np.where(long[:, None], lo <= stop[:, None], hi >= stop[:, None]) & inside
        tgt_hit = (np.where(long[:, None], hi >= target[:, None], lo <= target[:, None]) & inside
                   if target_r is not None else np.zeros_like(stop_hit))
        any_hit = stop_hit | tgt_hit
        has = any_hit.any(axis=1)
        first = any_hit.argmax(axis=1)
        rows = np.arange(len(e))
        j = e + first
        is_stop = stop_hit[rows, first]  # stop gaat voor target binnen dezelfde bar
        open_exit_side = np.where(long, px["bid_open"][j], px["ask_open"][j])
        # gat voorbij het niveau: exit op de open
        stop_px = np.where(long, np.minimum(stop, open_exit_side), np.maximum(stop, open_exit_side))
        tgt_px = np.where(long, np.maximum(target, open_exit_side), np.minimum(target, open_exit_side))
        level_px = np.where(is_stop, stop_px, tgt_px)
        level_px = np.where(long, level_px - slip, level_px + slip)
        exit_px = np.where(has, level_px, exit_px)
        exit_bar = np.where(has, j, exit_bar)
        free_from = np.where(has, j + 1, free_from)
        reason = np.where(has, np.where(is_stop, "stop", "target"), reason)
        keep = valid
        e, d, lim, fill, exit_px, exit_bar, free_from, reason, risk, long = (
            a[keep] for a in (e, d, lim, fill, exit_px, exit_bar, free_from, reason, risk, long))

    # max. 1 open trade: op volgorde van entry
    take = np.zeros(len(e), dtype=bool)
    busy_until = -1
    for i in range(len(e)):
        if e[i] >= busy_until:
            take[i] = True
            busy_until = free_from[i]
    e, d, fill, exit_px, exit_bar, reason, risk, long = (
        a[take] for a in (e, d, fill, exit_px, exit_bar, reason, risk, long))

    net = returns_bp(base_is_usd, d, fill, exit_px)
    half_spread_exit = (px["ask_open"][exit_bar] - px["bid_open"][exit_bar]) / 2
    exit_mid = np.where(long, exit_px + slip + half_spread_exit, exit_px - slip - half_spread_exit)
    gross = returns_bp(base_is_usd, d, px["open"][e], exit_mid)  # "open" = mid
    pnl_px = np.where(long, exit_px - fill, fill - exit_px)
    return pd.DataFrame({
        "entry_time": px["time"][e], "exit_time": px["time"][exit_bar], "direction": d,
        "entry_px": fill, "exit_px": exit_px, "reason": reason,
        "net_bp": net, "gross_bp": gross, "cost_bp": gross - net,
        "r": pnl_px / risk,
    })
