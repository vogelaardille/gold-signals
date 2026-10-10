"""Onderzoeksdefinities op kleine, met de hand gemaakte koersreeksen."""
import numpy as np
import pandas as pd

from goldsignals.research.events import (Arrays, detect_events, first_true, measure_outcomes,
                                         simulate_trades)

RCFG = {"horizon_bars": 4, "bounce_atr": 1.0, "break_atr": 0.5}


def arrays(o, h, l, c):
    t = pd.date_range("2024-01-01", periods=len(c), freq="h", tz="UTC")
    return Arrays(t, *(np.asarray(x, float) for x in (o, h, l, c)))


def zone_rows(i, low, high, atr=1.0):
    return pd.DataFrame({"i": [i], "as_of": [pd.Timestamp("2024-01-01", tz="UTC")], "low": [low],
                         "high": [high], "atr_1h": [atr], "atr_1d": [5.0], "timeframe": ["1d"],
                         "confluence": [3], "touches": [2], "first_touch": [pd.Timestamp("2023-12-01", tz="UTC")],
                         "last_touch": [pd.Timestamp("2023-12-20", tz="UTC")], "score": [1.0]})


def test_first_true():
    m = np.array([[False, True, True], [False, False, False]])
    assert list(first_true(m)) == [1, 3]


def test_support_test_detected_only_from_above():
    # Zone 99-100. Vorige slot 101 (erboven), candle 1 raakt 99.5 -> support-test.
    a = arrays([101, 101, 100, 101, 102, 103, 104], [101, 101.2, 101, 102, 103, 104, 105],
               [100.5, 99.5, 99.8, 100.5, 101, 102, 103], [101, 100.2, 100.8, 101.8, 102.8, 103.8, 104.8])
    ev = detect_events(zone_rows(1, 99, 100), a)
    assert len(ev) == 1 and ev["side"].iloc[0] == 1
    # Als de vorige slot al IN de zone zat: geen nieuwe test
    a2 = arrays([99.5] * 7, [100] * 7, [99] * 7, [99.5] * 7)
    assert len(detect_events(zone_rows(1, 99, 100), a2)) == 0


def test_bounce_vs_break_same_candle_counts_as_break():
    # Candle 2 heeft high >= 101 (bounce) EN slot <= 98.5 (break): break telt.
    a = arrays([101, 101, 100, 99, 99, 99, 99], [101, 101, 101.5, 99, 99, 99, 99],
               [100.5, 99.5, 98, 98, 98, 98, 98], [101, 100.2, 98.4, 98.5, 98.5, 98.5, 98.5])
    ev = measure_outcomes(detect_events(zone_rows(1, 99, 100), a), a, RCFG)
    assert ev["outcome"].iloc[0] == "break"


def test_clean_bounce():
    a = arrays([101, 101, 100.5, 100.8, 101], [101, 101, 100.9, 101.2, 101.5],
               [100.5, 99.6, 100.2, 100.6, 100.9], [101, 100.4, 100.7, 101.1, 101.4] )
    a = arrays(list(a.open) + [101.4, 101.4], list(a.high) + [101.5, 101.5],
               list(a.low) + [101.3, 101.3], list(a.close) + [101.4, 101.4])
    ev = measure_outcomes(detect_events(zone_rows(1, 99, 100), a), a, RCFG)
    assert ev["outcome"].iloc[0] == "bounce"     # high 101.2 >= 100 + 1 ATR op candle 3


def test_sl_first_when_both_hit_in_same_candle():
    # Entry op open[1] = 100, stop 99, target 102. Candle 1 raakt beide -> SL.
    a = arrays([100, 100, 100, 100], [100, 102.5, 100, 100], [100, 98.5, 100, 100], [100, 100, 100, 100])
    sim = simulate_trades(a, np.array([0]), np.array([1]), np.array([99.0]), 2.0, 2, cost=0.0)
    assert sim["result"][0] == "sl"
    assert sim["r"][0] == -1.0


def test_gap_through_stop_fills_at_open():
    # Short op open[1] = 100, stop 101. Candle 2 opent op 103 (gat boven de stop) -> exit 103.
    a = arrays([100, 100, 103, 103], [100, 100.5, 104, 104], [100, 99.5, 102, 102], [100, 100, 103, 103])
    sim = simulate_trades(a, np.array([0]), np.array([-1]), np.array([101.0]), 2.0, 2, cost=0.0)
    assert sim["result"][0] == "sl"
    assert np.isclose(sim["r_gross"][0], -3.0)


def test_costs_make_stop_exactly_minus_one_r():
    a = arrays([100, 100, 100], [100, 100, 100], [100, 98, 100], [100, 100, 100])
    sim = simulate_trades(a, np.array([0]), np.array([1]), np.array([99.0]), 2.0, 1, cost=0.6)
    assert np.isclose(sim["r"][0], -1.0)
    a = arrays([100, 100, 100], [100, 103, 100], [100, 100, 100], [100, 100, 100])
    sim = simulate_trades(a, np.array([0]), np.array([1]), np.array([99.0]), 2.0, 1, cost=0.6)
    assert np.isclose(sim["r"][0], (2 - 0.6) / (1 + 0.6))
