"""Ronde 2: engine-regels, geen lookahead in de families, macro-publicatievertraging."""
import numpy as np
import pandas as pd
import pytest

from goldsignals.data.timeframes import resample
from goldsignals.round2 import families as fam
from goldsignals.round2 import indicators as ind
from goldsignals.round2.engine import simulate, with_costs
from goldsignals.round2.families import Signals


def bars_from(rows):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="D", tz="UTC")
    b = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    b["close_time"] = idx + pd.Timedelta(days=1)
    return b


def sig(n, at, d, stop_dist, **kw):
    e = np.zeros(n, np.int8)
    e[at] = d
    return Signals(e, np.full(n, float(stop_dist)), **kw)


# ---------------- engine ----------------

def test_entry_next_open_and_stop_first():
    b = bars_from([(100, 100, 100, 100), (101, 101, 101, 101), (101, 104, 98, 101)])
    t = simulate(b, sig(3, 0, 1, 2.0, target_r=1.0))
    assert t["entry"].iloc[0] == 101                    # open van candle 1
    # candle 1 raakt niets; candle 2 raakt stop (99) en target (103): stop telt
    assert t["result"].iloc[0] == "sl" and t["exit"].iloc[0] == 99


def test_gap_beyond_stop_exits_at_open():
    b = bars_from([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (95, 96, 94, 95)])
    t = simulate(b, sig(3, 0, 1, 2.0))
    assert t["exit"].iloc[0] == 95 and t["result"].iloc[0] == "sl"


def test_trailing_stop_moves_only_after_close():
    # entry 100, k=1, ATR=2 -> stop 98. Slot candle 1 = 105 -> nieuwe stop 103 (vanaf candle 2).
    rows = [(100, 100, 100, 100), (100, 105, 99, 105), (104, 104.5, 102.5, 103), (103, 103, 103, 103)]
    b = bars_from(rows)
    s = Signals(np.array([1, 0, 0, 0], np.int8), np.full(4, 2.0), trail_k=1.0, trail_atr=np.full(4, 2.0))
    t = simulate(b, s)
    # candle 1: low 99 > 98 -> geen exit (stop nog 98). Candle 2: low 102.5 <= 103 -> exit op 103.
    assert t["exit"].iloc[0] == 103 and t["exit_i"].iloc[0] == 2


def test_trailing_never_loosens():
    rows = [(100, 100, 100, 100), (100, 106, 99, 106), (106, 106, 104.2, 104.5), (104.5, 104.5, 103.9, 104)]
    s = Signals(np.array([1, 0, 0, 0], np.int8), np.full(4, 2.0), trail_k=1.0,
                trail_atr=np.array([2.0, 2.0, 0.1, 5.0]))
    t = simulate(bars_from(rows), s)
    # na candle 1: stop 104; candle 2 low 104.2 -> nee; slot 104.5, atr 0.1 -> best blijft 106 -> 105.9
    # candle 3: low 103.9 <= 105.9 -> exit op open 104.5 (gat onder de stop)
    assert t["exit"].iloc[0] == 104.5


def test_target_level_wrong_side_skips_trade():
    b = bars_from([(100, 100, 100, 100), (102, 102, 102, 102), (102, 102, 102, 102)])
    s = Signals(np.array([1, 0, 0], np.int8), np.full(3, 1.0), target_level=np.full(3, 101.0))
    assert simulate(b, s).empty                         # entry 102 ligt al boven het target 101


def test_time_stop_exits_on_close():
    rows = [(100, 100, 100, 100)] + [(100, 100.5, 99.5, 100.2)] * 5
    s = Signals(np.array([1, 0, 0, 0, 0, 0], np.int8), np.full(6, 5.0), time_stop=3)
    t = simulate(bars_from(rows), s)
    assert t["result"].iloc[0] == "tijd" and t["exit_i"].iloc[0] == 3


def test_costs_make_stop_minus_one_r():
    b = bars_from([(100, 100, 100, 100), (100, 100, 97, 98), (98, 98, 98, 98)])
    t = simulate(b, sig(3, 0, 1, 2.0))
    assert np.isclose(with_costs(t, 0.6)[0], -1.0)
    assert np.isclose(with_costs(t, 1.8)[0], -1.0)


def test_one_position_at_a_time():
    rows = [(100, 100.5, 99.5, 100)] * 10
    s = Signals(np.ones(10, np.int8), np.full(10, 5.0))
    t = simulate(bars_from(rows), s)
    assert len(t) == 1 and t["result"].iloc[0] == "einde"


# ---------------- families: geen lookahead ----------------

@pytest.fixture(scope="module")
def daily(candles, cfg):
    return resample(candles, "1d", "America/New_York", 17)


VARIANTS = [
    ("1d", {"family": "F1", "entry": "donchian50", "trail_atr": 3}),
    ("1d", {"family": "F1", "entry": "tsmom3", "trail_atr": 4}),
    ("1d", {"family": "F2", "timeframe": "1d", "squeeze_pct": 20, "exit": "trail_3atr"}),
    ("1h", {"family": "F2", "timeframe": "4h", "squeeze_pct": 20, "exit": "target_2R"}),
    ("1h", {"family": "F3", "timeframe": "1h", "regime": "adx", "band_z": 2.0, "stop_atr": 1.5}),
    ("1h", {"family": "F3", "timeframe": "1h", "regime": "atr_pct", "band_z": 2.0, "stop_atr": 1.5}),
]


@pytest.mark.parametrize("src,v", VARIANTS, ids=lambda x: str(x))
def test_family_signals_do_not_use_future(candles, daily, cfg, src, v):
    b = daily if src == "1d" else candles.assign(close_time=candles.index + pd.Timedelta(hours=1))
    if v.get("timeframe") == "4h":
        b = resample(candles, "4h", "America/New_York", 17)
    cut = int(len(b) * 0.8)
    full = fam.signals(b, v, cfg)
    part = fam.signals(b.iloc[:cut], v, cfg)
    np.testing.assert_array_equal(full.entry[:cut], part.entry)
    np.testing.assert_allclose(full.stop_dist[:cut], part.stop_dist, equal_nan=True)
    if full.target_level is not None:
        np.testing.assert_allclose(full.target_level[:cut], part.target_level, equal_nan=True)
    assert (full.entry != 0).sum() > 0, "test zinloos zonder signalen"


def test_donchian_uses_previous_bars_only():
    rows = [(100, 101, 99, 100)] * 60 + [(100, 101.5, 99, 101.2)]
    b = bars_from(rows)
    e = fam.trend_entry(b, "donchian50")
    assert e[-1] == 1 and (e[:-1] == 0).all()           # pas als het slot boven de vorige highs uitkomt


def test_macro_value_only_after_publication_lag():
    s = pd.Series([1.0, 2.0, 3.0, 2.0], index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]))
    ct = pd.Series(pd.to_datetime(["2024-01-04 22:00", "2024-01-05 22:00", "2024-01-07 22:00"], utc=True))
    chg = ind.macro_change(s, lag_days=3, change_obs=1, close_times=ct)
    # verandering op 01-02 (+1) is bruikbaar vanaf 01-05 00:00; op 01-04 nog niets bekend
    assert np.isnan(chg[0])
    assert chg[1] == 1.0          # 01-05 22:00: laatste bekende = 01-02
    assert chg[2] == -1.0         # 01-07 22:00: 01-04 (+3 dagen = 01-07 00:00) is bekend


# ---------------- F5: 15m-candle gebruikt de snapshot van het laatst gesloten uur ----------------

def test_15m_bar_uses_last_closed_hour_snapshot():
    from goldsignals.round2.zone15 import snapshot_for_bars
    snaps = pd.DatetimeIndex(["2024-01-01 10:00", "2024-01-01 11:00", "2024-01-01 12:00"], tz="UTC").to_numpy()
    opens = pd.DatetimeIndex(["2024-01-01 10:59", "2024-01-01 11:00", "2024-01-01 11:45",
                              "2024-01-01 09:30"], tz="UTC").to_numpy()
    k = snapshot_for_bars(snaps, opens)
    # 10:59 -> snapshot 10:00; 11:00 -> uur 10-11 is net gesloten -> 11:00; 11:45 -> nog steeds 11:00
    assert list(k) == [0, 1, 1, -1]


def test_zone_table_rows_never_from_future_snapshot():
    from goldsignals.round2.zone15 import build_zone_table
    idx = pd.date_range("2024-01-01 10:00", periods=12, freq="15min", tz="UTC")
    c15 = pd.DataFrame({"open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 1.0}, index=idx)
    snap = pd.DataFrame({"as_of": pd.DatetimeIndex(["2024-01-01 10:00", "2024-01-01 11:00", "2024-01-01 12:00"], tz="UTC"),
                         "low": [1.0, 2.0, 3.0], "high": [1.5, 2.5, 3.5], "atr_1d": 1.0, "timeframe": "1d",
                         "confluence": 3, "touches": 2, "first_touch": pd.Timestamp("2023-01-01", tz="UTC"),
                         "last_touch": pd.Timestamp("2023-06-01", tz="UTC"), "score": 1.0})
    z = build_zone_table(snap, c15, 0, 11)
    bar_open = c15.index[z["i"].to_numpy()]
    assert (pd.DatetimeIndex(z["as_of"]) <= bar_open).all()
    early = bar_open < pd.Timestamp("2024-01-01 12:00", tz="UTC")
    assert len(z) == 12 and set(z.loc[early, "low"]) == {1.0, 2.0}   # snapshot 12:00 nooit vóór 12:00
    assert set(z.loc[~early, "low"]) == {3.0}
