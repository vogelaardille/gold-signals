"""Indicatoren per 1h-candle: ATR, RSI, EMA's, daily-trend en volatiliteitsregime.

Elke waarde op rij i gebruikt ALLEEN candles die uiterlijk bij het sluiten van candle i
bekend waren. Dat geldt vanzelf voor ATR/RSI/EMA (die kijken alleen terug). Voor de
daily-trend moeten we opletten: de daily candle van vandaag loopt nog, dus we gebruiken
de laatste daily candle met close_time <= sluittijd van de 1h-candle.
tests/test_features.py controleert dat de waarden niet veranderen als je de toekomst
weghaalt.
"""
import numpy as np
import pandas as pd

from goldsignals.data.timeframes import TF_DURATION, resample
from goldsignals.sr.pivots import atr


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """RSI volgens Wilder: gemiddelde winst / gemiddeld verlies, geschaald naar 0-100."""
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100.0)


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def daily_trend(candles_1h: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Per 1h-candle: slot en EMA van de laatste GESLOTEN daily candle, en de trend (+1/-1)."""
    d = cfg["data"]
    daily = resample(candles_1h, "1d", d["session_tz"], d["session_close_hour"])
    daily = daily.assign(d_ema=ema(daily["close"], cfg["features"]["daily_trend_ema"]))
    daily = daily[["close_time", "close", "d_ema"]].rename(columns={"close": "d_close"})

    left = pd.DataFrame({"close_time": candles_1h.index + TF_DURATION["1h"]})
    left["close_time"] = left["close_time"].astype(daily["close_time"].dtype)
    # merge_asof: neem per 1h-sluiting de laatste daily met close_time <= die sluiting
    m = pd.merge_asof(left, daily.sort_values("close_time"), on="close_time", direction="backward")
    m.index = candles_1h.index
    m["d_trend"] = np.where(m["d_close"] > m["d_ema"], 1, np.where(m["d_close"] < m["d_ema"], -1, 0))
    m.loc[m["d_ema"].isna(), "d_trend"] = 0
    return m[["d_close", "d_ema", "d_trend"]]


def compute_features(candles_1h: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    f = cfg["features"]
    out = pd.DataFrame(index=candles_1h.index)
    out["close_time"] = candles_1h.index + TF_DURATION["1h"]
    out["atr"] = atr(candles_1h, f["atr_period"])
    out["rsi"] = rsi(candles_1h["close"], f["rsi_period"])
    out["ema_fast"] = ema(candles_1h["close"], f["ema_fast"])
    out["ema_slow"] = ema(candles_1h["close"], f["ema_slow"])
    out = out.join(daily_trend(candles_1h, cfg))
    # Volatiliteitsregime: hoe hoog is de ATR nu t.o.v. het afgelopen jaar (percentiel)?
    # ATR als % van de koers, anders is 'hoog' vooral 'goud is duurder geworden'.
    atr_rel = out["atr"] / candles_1h["close"]
    out["vol_pct"] = atr_rel.rolling(f"{f['vol_lookback_days']}D").rank(pct=True) * 100
    out["vol_regime"] = np.select(
        [out["vol_pct"] < f["vol_low_pct"], out["vol_pct"] > f["vol_high_pct"]],
        ["laag", "hoog"], default="midden")
    return out
