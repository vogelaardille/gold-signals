"""Strategie (a): S/R-bounce met RSI en daily-trendfilter.

Long (short gespiegeld), beoordeeld op de slotkoers van een 1h-candle:
1. De candle raakte een support-zone die op dat moment bekend was: de vorige slotkoers
   lag boven de zone, de low van deze candle kwam in de zone, en de slotkoers bleef
   boven de onderkant (zone niet doorgebroken).
2. Optioneel: confluence van de zone >= min_confluence.
3. RSI(14) op de slotkoers <= rsi_max (oververkocht-achtig). 100 = filter uit.
4. Daily-trendfilter: alleen long als de daily-trend omhoog is (trend_filter = true).
5. Stop = onderkant zone - stop_atr x ATR(1h).
6. Target = onderkant van de eerstvolgende zone van een HOGER timeframe (4h of daily)
   boven de koers. Geeft dat minder dan min_rr (1:2), dan geen trade: het volgende
   obstakel ligt te dichtbij.
"""
import numpy as np

from goldsignals.strategies.base import Signal, Strategy

HTF = ("4h", "1d")


def touched_zones(z, prev_close: float, bar, direction: int):
    """Masker van zones die deze candle raakte vanaf de goede kant en die hielden op slot."""
    low, high = z["low"].to_numpy(), z["high"].to_numpy()
    if direction == 1:
        return (prev_close > high) & (bar["low"] <= high) & (bar["close"] > low)
    return (prev_close < low) & (bar["high"] >= low) & (bar["close"] < high)


def next_htf_target(z, price: float, direction: int):
    """Dichtstbijzijnde rand van de volgende 4h/daily-zone in de handelsrichting, of None."""
    htf = z[z["timeframes"].str.contains("4h|1d")]
    if direction == 1:
        ahead = htf[htf["low"] > price]
        return float(ahead["low"].min()) if len(ahead) else None
    ahead = htf[htf["high"] < price]
    return float(ahead["high"].max()) if len(ahead) else None


def zone_text(zone) -> str:
    return (f"{zone['low']:.2f}–{zone['high']:.2f} ({zone['timeframes']}, score {zone['score']:.1f}, "
            f"{int(zone['touches'])} aanrakingen)")


class SRBounce(Strategy):
    name = "sr_bounce"
    description = "Bounce op een S/R-zone met RSI- en daily-trendfilter, target = volgende 4h/daily-zone"
    zone_method = "A"

    def __init__(self, params=None):
        super().__init__(params)
        self.zone_method = self.params.get("method", "A")

    def generate_signals(self, view):
        p = self.params
        f = view.feat
        rsi = f["rsi"]
        directions = []
        if rsi <= p["rsi_max"] and (not p["trend_filter"] or f["d_trend"] == 1):
            directions.append(1)
        if p["allow_short"] and rsi >= 100 - p["rsi_max"] and (not p["trend_filter"] or f["d_trend"] == -1):
            directions.append(-1)
        if not directions:
            return []
        z = view.zones(self.zone_method)
        if z.empty:
            return []
        z = z[z["confluence"] >= p["min_confluence"]]
        bar = view.bar
        prev_close = view.array("close", 2)[0]
        atr = f["atr"]
        for d in directions:
            hit = touched_zones(z, prev_close, bar, d)
            if not hit.any():
                continue
            zone = z[hit].sort_values("score", ascending=False).iloc[0]
            stop = zone["low"] - p["stop_atr"] * atr if d == 1 else zone["high"] + p["stop_atr"] * atr
            target = next_htf_target(z, bar["close"], d)
            if target is None:
                continue
            risk = d * (bar["close"] - stop)
            if risk <= 0 or d * (target - bar["close"]) / risk < p["min_rr"]:
                continue
            kind = "support" if d == 1 else "resistance"
            why = (f"Koers raakte {kind}-zone {zone_text(zone)} en sloot {'erboven' if d == 1 else 'eronder'}. "
                   f"RSI {rsi:.0f}{'' if p['rsi_max'] >= 100 else (' (≤ ' if d == 1 else ' (≥ ') + str(p['rsi_max'] if d == 1 else 100 - p['rsi_max']) + ')'}"
                   f"{', daily-trend ' + ('omhoog' if d == 1 else 'omlaag') if p['trend_filter'] else ''}. "
                   f"Target = volgende 4h/daily-zone ({target:.2f}).")
            return [Signal(self.name, view.t, d, float(stop), float(target), why, min_rr=p["min_rr"],
                           zone={k: zone[k] for k in ("low", "high", "timeframes", "score")})]
        return []
