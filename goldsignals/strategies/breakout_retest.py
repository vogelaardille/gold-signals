"""Strategie (b): breakout en retest.

Long (short gespiegeld):
1. Binnen de laatste `lookback` candles sloot de koers duidelijk BOVEN een zone
   (>= break_atr x ATR boven de bovenkant), terwijl hij aan het begin van dat venster
   nog ONDER de zone stond: een doorbraak omhoog.
2. Nu raakt een candle de zone weer van bovenaf (retest) en sluit erboven: de oude
   weerstand werkt als steun.
3. Stop = onderkant zone - stop_atr x ATR. Target = entry + rr x risico.
"""
import numpy as np

from goldsignals.strategies.base import Signal, Strategy
from goldsignals.strategies.sr_bounce import zone_text


class BreakoutRetest(Strategy):
    name = "breakout_retest"
    description = "Doorbraak door een zone, instap bij de retest van die zone"
    zone_method = "A"

    def __init__(self, params=None):
        super().__init__(params)
        self.zone_method = self.params.get("method", "A")

    def generate_signals(self, view):
        p = self.params
        z = view.zones(self.zone_method)
        if z.empty:
            return []
        z = z[z["confluence"] >= p["min_confluence"]]
        closes = view.array("close", p["lookback"] + 1)
        if len(closes) < p["lookback"] + 1:
            return []
        past, first = closes[:-1], closes[0]
        bar, atr = view.bar, view.feat["atr"]
        low, high = z["low"].to_numpy(), z["high"].to_numpy()
        b = p["break_atr"] * atr
        up = (first < low) & (past.max() > (high + b)) & (bar["low"] <= high) & (bar["close"] > high)
        down = (first > high) & (past.min() < (low - b)) & (bar["high"] >= low) & (bar["close"] < low)
        if not p["allow_short"]:
            down[:] = False
        for d, mask in ((1, up), (-1, down)):
            if not mask.any():
                continue
            zone = z[mask].sort_values("score", ascending=False).iloc[0]
            stop = zone["low"] - p["stop_atr"] * atr if d == 1 else zone["high"] + p["stop_atr"] * atr
            risk = d * (bar["close"] - stop)
            if risk <= 0:
                continue
            target = bar["close"] + d * p["rr"] * risk
            why = (f"Zone {zone_text(zone)} werd de afgelopen {p['lookback']} uur "
                   f"{'omhoog' if d == 1 else 'omlaag'} doorbroken; nu retest en slot "
                   f"{'erboven' if d == 1 else 'eronder'} (oude {'weerstand wordt steun' if d == 1 else 'steun wordt weerstand'}).")
            return [Signal(self.name, view.t, d, float(stop), float(target), why, min_rr=p["rr"] * 0.8,
                           zone={k: zone[k] for k in ("low", "high", "timeframes", "score")})]
        return []
