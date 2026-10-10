"""Baselines: willekeurige entries en buy-and-hold.

Waarom? Een strategie is pas interessant als hij beter doet dan:
- willekeurig instappen met dezelfde stop/target-regels (random_entry). Goud steeg
  sterk; willekeurige longs verdienen dan ook al. Dat is de 'gratis' trendwinst.
- gewoon kopen en vasthouden (buy-and-hold).
"""
import hashlib

import numpy as np
import pandas as pd

from goldsignals.strategies.base import Signal, Strategy


class RandomEntry(Strategy):
    name = "random_entry"
    description = "Willekeurige entries (baseline), stop x ATR, target 1:2"

    def _rng(self, t):
        # Dezelfde tijd geeft altijd dezelfde 'toevalsgetallen': reproduceerbaar en herstartbaar.
        h = hashlib.sha256(f"{self.params['seed']}|{t.isoformat()}".encode()).digest()
        return np.random.default_rng(int.from_bytes(h[:8], "little"))

    def generate_signals(self, view):
        p = self.params
        rng = self._rng(view.t)
        if rng.random() >= p["prob"]:
            return []
        d = int(rng.choice([-1, 1])) if p["allow_short"] else 1
        close, atr = view.bar["close"], view.feat["atr"]
        stop = close - d * p["stop_atr"] * atr
        target = close + d * p["rr"] * p["stop_atr"] * atr
        return [Signal(self.name, view.t, d, stop, target, "Willekeurige entry (baseline, geen echte reden).",
                       min_rr=p["rr"] * 0.8)]


def buy_and_hold(candles: pd.DataFrame, start_equity: float) -> dict:
    """Kopen op de eerste open, vasthouden tot de laatste slotkoers (zonder hefboom)."""
    if candles.empty:
        return {"return_pct": np.nan, "max_dd_pct": np.nan}
    eq = start_equity * candles["close"] / candles["open"].iloc[0]
    dd = ((eq - eq.cummax()) / eq.cummax()).min() * 100
    return {"return_pct": float(eq.iloc[-1] / start_equity * 100 - 100), "max_dd_pct": float(dd),
            "equity": eq}
