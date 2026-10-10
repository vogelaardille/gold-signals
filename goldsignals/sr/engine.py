"""zones_as_of: alle zones zoals ze op een bepaald moment bekend waren.

Dit is de enige functie die de rest van het systeem (later: strategie, backtest)
hoeft aan te roepen. Hij garandeert dat er geen informatie uit de toekomst
meetelt:
- alleen candles die op as_of gesloten waren (ook voor 4h en daily);
- pivots alleen als hun bevestigingscandles ook al gesloten waren;
- ATR, recency en 'huidige prijs' allemaal berekend op as_of.
tests/test_no_lookahead.py controleert dit.
"""
from dataclasses import dataclass

import pandas as pd

from goldsignals.data.timeframes import build_timeframes
from goldsignals.sr.clustering import detect_zones_cluster
from goldsignals.sr.common import ZONE_COLUMNS
from goldsignals.sr.kde import detect_zones_kde
from goldsignals.sr.merge import merge_zones
from goldsignals.sr.pivots import atr, find_pivots

METHODS = {"A": detect_zones_cluster, "B": detect_zones_kde}


@dataclass
class ZoneResult:
    as_of: pd.Timestamp
    price: float              # slotkoers van de laatste gesloten 1h-candle
    method: str
    raw: pd.DataFrame         # zones per timeframe, nog niet samengevoegd
    merged: pd.DataFrame      # samengevoegd, gesorteerd op score
    pivots: pd.DataFrame
    atr: dict                 # ATR per timeframe op as_of


def zones_as_of(candles_1h: pd.DataFrame, as_of: pd.Timestamp, cfg: dict, method: str = "A") -> ZoneResult:
    zcfg = cfg["zones"]
    detect = METHODS[method]
    frames = build_timeframes(candles_1h, cfg, as_of)
    price = float(frames["1h"]["close"].iloc[-1])

    raw_parts, pivot_parts, atr_values = [], [], {}
    for tf, df in frames.items():
        if len(df) < zcfg["atr_period"] + 1:
            continue  # te weinig historie voor deze timeframe
        atr_values[tf] = float(atr(df, zcfg["atr_period"]).iloc[-1])
        recent = df.iloc[-zcfg["lookback_bars"][tf]:]
        pivots = find_pivots(recent, zcfg["pivot_window"][tf], tf)
        pivot_parts.append(pivots)
        raw_parts.append(detect(pivots, atr_values[tf], as_of, tf, zcfg))

    raw = pd.concat(raw_parts, ignore_index=True) if raw_parts else pd.DataFrame(columns=ZONE_COLUMNS)
    pivots = pd.concat(pivot_parts, ignore_index=True) if pivot_parts else pd.DataFrame()

    merged = merge_zones(raw, cfg["merge"]["timeframe_weights"], price)

    return ZoneResult(as_of, price, method, raw, merged, pivots, atr_values)
