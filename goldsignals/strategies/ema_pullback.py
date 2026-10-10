"""Benchmark zonder S/R: EMA-trend pullback.

Idee: in een trend (EMA50 boven EMA200 op 1h) koop je een terugval naar de EMA50,
zodra de candle weer boven de EMA50 sluit. Short gespiegeld. Stop een vast aantal
ATR onder de entry, target een vaste R:R. Dit is de lat waar S/R-strategieën overheen
moeten: als die niet beter doen, voegen de zones niets toe.
"""
from goldsignals.strategies.base import Signal, Strategy


class EmaPullback(Strategy):
    name = "ema_pullback"
    description = "EMA50/200-trend, instap na een terugval naar de EMA50 (benchmark zonder zones)"

    def generate_signals(self, view):
        p = self.params
        f, bar = view.feat, view.bar
        atr = f["atr"]
        up = f["ema_fast"] > f["ema_slow"]
        if p["daily_filter"]:
            # Alleen handelen als de daily-trend dezelfde kant op wijst
            if (up and f["d_trend"] != 1) or (not up and f["d_trend"] != -1):
                return []
        touched = bar["low"] <= f["ema_fast"] < bar["close"] if up else bar["high"] >= f["ema_fast"] > bar["close"]
        if not touched or (not up and not p["allow_short"]):
            return []
        d = 1 if up else -1
        stop = bar["close"] - d * p["stop_atr"] * atr
        target = bar["close"] + d * p["rr"] * p["stop_atr"] * atr
        why = (f"{'Uptrend' if up else 'Downtrend'} op 1h (EMA50 {'>' if up else '<'} EMA200), koers tikte de "
               f"EMA50 ({f['ema_fast']:.2f}) en sloot weer {'erboven' if up else 'eronder'}.")
        return [Signal(self.name, view.t, d, stop, target, why, min_rr=p["rr"] * 0.8)]
