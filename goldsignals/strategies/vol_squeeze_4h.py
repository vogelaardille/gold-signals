"""Forward-test (ronde 2): volatiliteitscompressie gevolgd door een breakout, op 4h.

AANWIJZING, NIET BEWEZEN. Regels vastgelegd in research/round2/FORWARD.md en NOOIT meer
aanpassen (ook geen comments: de vingerafdruk van dit bestand staat in FORWARD.md).

Op het slot van elke 4h-candle (17/21/01/05/09/13 uur New York):
1. Compressie: de Bollinger-bandbreedte (20 candles, 2 sigma) gedeeld door het
   20-candle-gemiddelde ligt in het laagste 20% van het afgelopen jaar (365 dagen).
2. Die compressie was er in minstens één van de 5 candles vóór deze candle.
3. Breakout: slot boven het hoogste high van de vorige 20 candles -> long;
   slot onder het laagste low van de vorige 20 candles -> short.
4. Stop: 2 x ATR(14) van de 4h-candles vanaf de entry. Target: 2 x het risico (2R).
Entry op de open van de eerstvolgende candle (zoals alle strategieën).
"""
import numpy as np
import pandas as pd

from goldsignals.data.timeframes import resample
from goldsignals.round2 import families
from goldsignals.strategies.base import Signal, Strategy

PARAMS = {"timeframe": "4h", "squeeze_pct": 20, "squeeze_lookback_bars": 5, "breakout_bars": 20,
          "bb_period": 20, "bb_sigma": 2.0, "atr_period": 14, "stop_atr": 2.0, "rr": 2.0,
          "history_days": 450}
LABEL = "AANWIJZING, NIET BEWEZEN"


BOUNDARY_HOURS_NY = {17, 21, 1, 5, 9, 13}   # sluituren van 4h-candles in New York-tijd


def crossed_4h_boundary(t_prev: pd.Timestamp, t: pd.Timestamp) -> bool:
    """Ligt er een 4h-grens in (t_prev, t]? (Snel vooraf checken, zodat we niet elk uur resamplen.)"""
    h = t_prev.floor("h") + pd.Timedelta(hours=1)
    while h <= t:
        if h.tz_convert("America/New_York").hour in BOUNDARY_HOURS_NY:
            return True
        h += pd.Timedelta(hours=1)
    return False


def bars_4h(candles_1h: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    """4h-candles uit 1h-candles, alleen die op t gesloten waren."""
    b = resample(candles_1h, "4h", "America/New_York", 17)
    return b[b["close_time"] <= t]


class VolSqueeze4h(Strategy):
    name = "vol_squeeze_4h"
    description = "Volatiliteitscompressie -> breakout op 4h, stop 2 ATR, target 2R (forward-test)"
    zone_method = None

    def __init__(self, params=None, forced: dict = None):
        """forced: alleen voor de random-baseline bij de evaluatie: {sluittijd 4h-candle: richting}.
        Dan wordt het instapmoment niet door de regels maar door deze lijst bepaald; exits gelijk."""
        super().__init__({**PARAMS, **(params or {})})
        self.forced = forced

    def generate_signals(self, view):
        p = self.params
        prev = view.candles(2)
        if len(prev) < 2:
            return []
        t, t_prev = view.t, prev.index[0] + pd.Timedelta(hours=1)
        if not crossed_4h_boundary(t_prev, t):
            return []
        c = view.candles(int(p["history_days"] * 24))
        b = bars_4h(c, t)
        if len(b) == 0:
            return []
        last_close = b["close_time"].iloc[-1]
        # Alleen handelen als er sinds het vorige 1h-slot een 4h-candle is gesloten
        if not (t_prev < last_close <= t):
            return []
        v = {"family": "F2", "timeframe": "4h", "squeeze_pct": p["squeeze_pct"], "exit": "target_2R"}
        s = families.f2(b, v, {"round2": {"families": {"F2": {"squeeze_lookback_bars": p["squeeze_lookback_bars"],
                                                                "breakout_bars": p["breakout_bars"],
                                                                "stop_atr": p["stop_atr"]}}}})
        if self.forced is not None:
            d = int(self.forced.get(last_close, 0))
        else:
            d = int(s.entry[-1])
        sd = float(s.stop_dist[-1])
        if d == 0 or not np.isfinite(sd) or sd <= 0:
            return []
        close = float(b["close"].iloc[-1])
        stop = close - d * sd
        target = close + d * p["rr"] * sd
        why = ("Rustige markt (bandbreedte in laagste 20% van het jaar), daarna een slot "
               f"{'boven het hoogste' if d == 1 else 'onder het laagste'} punt van de vorige 20 4h-candles. "
               f"{LABEL}.")
        # Stop en target zijn hier t.o.v. het slot; bij de echte entry (volgende open) worden ze
        # verschoven zodat de afstand gelijk blijft: zie meta['stop_dist'] (engine/paper).
        return [Signal(self.name, view.t, d, stop, target, why, min_rr=0.0,
                       meta={"stop_dist": sd, "rr": p["rr"], "label": LABEL})]
