"""Indicatoren voor ronde 2. Allemaal causaal: de waarde op candle i gebruikt alleen
candles t/m i (tests/test_round2.py controleert dat door de toekomst te veranderen)."""
import numpy as np
import pandas as pd

from goldsignals.data.timeframes import TF_DURATION, resample
from goldsignals.round2 import data
from goldsignals.sr.pivots import atr

TF_DURATION = {**TF_DURATION, "15m": pd.Timedelta(minutes=15)}


def bars(tf: str, until: pd.Timestamp, cfg: dict) -> pd.DataFrame:
    """Candles van timeframe tf, alleen gesloten vóór `until`, met kolom close_time."""
    if tf == "15m":
        c = data.load("15m", until=until)
        c = c.assign(close_time=c.index + TF_DURATION["15m"])
    else:
        c1 = data.load("1h", until=until)
        d = cfg["data"]
        c = resample(c1, tf, d["session_tz"], d["session_close_hour"])
        c = c[c["close_time"] <= until]
    return c


def sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def bollinger(close: pd.Series, n: int = 20, z: float = 2.0):
    m = close.rolling(n).mean()
    sd = close.rolling(n).std(ddof=0)
    return m - z * sd, m, m + z * sd


def adx(c: pd.DataFrame, n: int = 14) -> pd.Series:
    """Average Directional Index (Wilder). Laag (< 20) = geen duidelijke trend."""
    up = c["high"].diff()
    down = -c["low"].diff()
    plus_dm = np.where((up > down) & (up > 0), up, 0.0)
    minus_dm = np.where((down > up) & (down > 0), down, 0.0)
    tr = atr(c, 1)  # true range (period 1 = ruwe TR)
    a = 1 / n
    atr_n = tr.ewm(alpha=a, adjust=False).mean()
    pdi = 100 * pd.Series(plus_dm, index=c.index).ewm(alpha=a, adjust=False).mean() / atr_n
    mdi = 100 * pd.Series(minus_dm, index=c.index).ewm(alpha=a, adjust=False).mean() / atr_n
    dx = 100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan)
    return dx.ewm(alpha=a, adjust=False).mean()


def pct_rank_1y(s: pd.Series) -> pd.Series:
    """Percentiel (0-100) van de huidige waarde t.o.v. het afgelopen jaar (incl. nu)."""
    return s.rolling("365D").rank(pct=True) * 100


def macro_change(series: pd.Series, lag_days: int, change_obs: int, close_times: pd.Series) -> np.ndarray:
    """Verandering over `change_obs` waarnemingen van een FRED-reeks, zoals bekend op elk
    sluitmoment: een waarde van datum d is pas bruikbaar vanaf d + lag_days (publicatie)."""
    chg = series.diff(change_obs).dropna()
    avail = pd.DataFrame({"t": (chg.index + pd.Timedelta(days=lag_days)).tz_localize("UTC"),
                          "chg": chg.to_numpy()})
    left = pd.DataFrame({"t": pd.to_datetime(close_times).astype("datetime64[ns, UTC]")})
    avail["t"] = avail["t"].astype("datetime64[ns, UTC]")
    m = pd.merge_asof(left.reset_index(drop=True), avail.sort_values("t"), on="t", direction="backward")
    return m["chg"].to_numpy()
