"""Swing highs/lows (pivots) en ATR.

Een pivot high op candle i: de high is hoger dan de n candles ervoor en minstens
zo hoog als de n candles erna (een 'fractal'). Belangrijk: dat weet je pas als
die n candles erna ook gesloten zijn. Daarom krijgt elke pivot een
'confirmed_time' = sluittijd van candle i+n. Pas vanaf dat moment mag een
strategie hem gebruiken.
"""
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view

PIVOT_COLUMNS = ["time", "confirmed_time", "price", "kind", "timeframe"]


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range (Wilder). Gebruikt alleen candles uit het verleden."""
    prev_close = df["close"].shift(1)
    true_range = pd.concat([
        df["high"] - df["low"],
        (df["high"] - prev_close).abs(),
        (df["low"] - prev_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False).mean()


def find_pivots(df: pd.DataFrame, window: int, timeframe: str) -> pd.DataFrame:
    """Vind bevestigde swing highs en lows.

    Waarom niet scipy.signal.argrelextrema? Die eist dat het punt STRIKT hoger is
    dan beide kanten, waardoor een dubbele top met exact gelijke highs wordt gemist.
    Hier: strikt hoger dan links, en >= rechts. Zo telt bij een gelijke top de
    eerste candle als pivot.
    """
    n = window
    if len(df) < 2 * n + 1:
        return pd.DataFrame(columns=PIVOT_COLUMNS)

    rows = []
    for kind, col in (("high", "high"), ("low", "low")):
        values = df[col].to_numpy()
        # Bij lows draaien we het teken om, dan is het dezelfde test als bij highs.
        v = values if kind == "high" else -values
        windows = sliding_window_view(v, 2 * n + 1)   # elk venster: n links, midden, n rechts
        center = windows[:, n]
        is_pivot = (center > windows[:, :n].max(axis=1)) & (center >= windows[:, n + 1:].max(axis=1))
        idx = np.flatnonzero(is_pivot) + n           # positie van de pivot-candle
        for i in idx:
            rows.append({
                "time": df.index[i],
                "confirmed_time": df["close_time"].iloc[i + n],
                "price": values[i],
                "kind": kind,
                "timeframe": timeframe,
            })
    out = pd.DataFrame(rows, columns=PIVOT_COLUMNS)
    return out.sort_values("time").reset_index(drop=True)
