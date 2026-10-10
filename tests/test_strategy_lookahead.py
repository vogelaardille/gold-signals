"""Strategieën mogen op candle i alleen informatie t/m i gebruiken.

Aanpak: bereken signalen op een reeks candles. Verander daarna alle candles NA i
(absurde prijzen) en bereken opnieuw: de signalen op i moeten identiek zijn.
Zones komen via zones_as_of (snapshots), dus die zijn al los getest.
"""
import numpy as np
import pandas as pd
import pytest

from goldsignals.features import compute_features
from goldsignals.market import Market
from goldsignals.snapshots import snapshot_frame
from goldsignals.sr import zones_as_of
from goldsignals.strategies.base import MarketView
from goldsignals.strategies.breakout_retest import BreakoutRetest
from goldsignals.strategies.ema_pullback import EmaPullback
from goldsignals.strategies.sr_bounce import SRBounce

STRATS = [
    SRBounce({"method": "A", "rsi_max": 100, "stop_atr": 0.5, "trend_filter": False, "min_confluence": 1,
              "allow_short": True, "min_rr": 0.5, "fresh_only": False, "reject_candle": False}),
    BreakoutRetest({"method": "A", "lookback": 48, "break_atr": 0.2, "stop_atr": 0.5, "rr": 2.0,
                    "min_confluence": 1, "allow_short": True}),
    EmaPullback({"stop_atr": 1.5, "rr": 2.0, "daily_filter": False, "allow_short": True}),
]


def market_for(candles, cfg, idx):
    feats = compute_features(candles, cfg)
    snaps = pd.concat([snapshot_frame(zones_as_of(candles, candles.index[i] + pd.Timedelta(hours=1), cfg, "A"))
                       for i in idx], ignore_index=True)
    return Market(candles, feats, {"A": snaps})


def signals(m, idx, strat):
    out = {}
    for i in idx:
        s = strat.generate_signals(MarketView(m, i))
        out[i] = [(x.direction, round(x.stop, 6), round(x.target, 6)) for x in s]
    return out


@pytest.mark.parametrize("strat", STRATS, ids=lambda s: s.name)
def test_signals_unchanged_when_future_changes(candles, cfg, strat):
    idx = list(range(4000, 4160))
    cut = idx[-1]
    m1 = market_for(candles, cfg, idx)
    tampered = candles.copy()
    after = np.arange(len(candles)) > cut
    rng = np.random.default_rng(3)
    for col in ("open", "high", "low", "close"):
        tampered.loc[after, col] += rng.normal(0, 200, after.sum())
    tampered.loc[after, "high"] += 500
    m2 = market_for(tampered, cfg, idx)
    s1, s2 = signals(m1, idx, strat), signals(m2, idx, strat)
    assert s1 == s2
    assert sum(len(v) for v in s1.values()) > 0 or strat.name != "ema_pullback"
