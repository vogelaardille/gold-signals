"""Indicatoren mogen op rij i alleen candles t/m i gebruiken (geen lookahead)."""
import numpy as np
import pandas as pd
import pandas.testing as pdt

from goldsignals.features import compute_features

CUTS = ["2024-06-12 14:00", "2024-09-04 21:00", "2025-01-15 09:00"]


def test_features_do_not_depend_on_future(candles, cfg):
    full = compute_features(candles, cfg)
    for cut in CUTS:
        t = pd.Timestamp(cut, tz="UTC")
        past = candles[candles.index + pd.Timedelta(hours=1) <= t]
        part = compute_features(past, cfg)
        pdt.assert_frame_equal(full.loc[past.index], part)


def test_daily_trend_uses_only_closed_daily(candles, cfg):
    """Midden op de dag mag de daily-slotkoers niet die van de lopende dag zijn."""
    f = compute_features(candles, cfg)
    t = pd.Timestamp("2024-06-12 14:00", tz="UTC")      # woensdag, daily loopt nog
    row = f[f["close_time"] == t].iloc[0]
    # laatste gesloten daily: dinsdag 17:00 NY = 21:00 UTC
    prev_close_1h = candles.loc[pd.Timestamp("2024-06-11 20:00", tz="UTC"), "close"]
    assert row["d_close"] == prev_close_1h


def test_rsi_bounds(candles, cfg):
    f = compute_features(candles, cfg)
    assert f["rsi"].between(0, 100).all()
    assert set(f["vol_regime"].unique()) <= {"laag", "midden", "hoog"}
    assert np.isfinite(f["atr"]).all()
