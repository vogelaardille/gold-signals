"""KRITIEK: zones_as_of(t) mag alleen informatie gebruiken die op moment t bekend was.

Aanpak: bereken de zones op t, verander daarna ALLES na t (andere prijzen, extreme
spikes, extra toekomstige candles) en bereken opnieuw. De uitkomst moet exact
gelijk zijn. Als controle dat de test niet 'altijd slaagt': een wijziging net
VOOR t moet de uitkomst wel veranderen.
"""
import numpy as np
import pandas as pd
import pandas.testing as pdt
import pytest

from goldsignals.sr import zones_as_of
from goldsignals.sr.pivots import find_pivots
from goldsignals.data.timeframes import resample

# Mix van momenten: midden in een sessie, vlak na een daily close, op maandagochtend
AS_OF_TIMES = ["2024-06-12 14:00", "2024-09-04 21:00", "2024-11-18 03:00", "2025-01-15 09:00"]


def tamper_after(df: pd.DataFrame, t: pd.Timestamp, seed=1) -> pd.DataFrame:
    """Verander alle candles die NA t sluiten, en plak er nog fake toekomst achter."""
    rng = np.random.default_rng(seed)
    out = df.copy()
    after = out.index + pd.Timedelta(hours=1) > t
    k = int(after.sum())
    shift = rng.normal(0, 80, k)
    for col in ("open", "high", "low", "close"):
        out.loc[after, col] = out.loc[after, col] + shift
    out.loc[after, "high"] += 500     # absurde spikes, zou elke zone verstoren
    out.loc[after, "low"] -= 500
    future = df.iloc[-200:].copy()
    future.index = future.index + pd.Timedelta(days=60)
    future[["open", "high", "low", "close"]] += 1000
    return pd.concat([out, future])


def assert_same(r1, r2):
    assert r1.price == r2.price
    assert r1.atr == r2.atr
    pdt.assert_frame_equal(r1.pivots, r2.pivots)
    pdt.assert_frame_equal(r1.raw, r2.raw)
    pdt.assert_frame_equal(r1.merged, r2.merged)


@pytest.mark.parametrize("method", ["A", "B"])
@pytest.mark.parametrize("t", AS_OF_TIMES)
def test_zones_do_not_change_when_future_changes(candles, cfg, method, t):
    t = pd.Timestamp(t, tz="UTC")
    original = zones_as_of(candles, t, cfg, method)
    assert len(original.merged) > 0, "test is zinloos zonder zones"
    tampered = zones_as_of(tamper_after(candles, t), t, cfg, method)
    assert_same(original, tampered)


@pytest.mark.parametrize("method", ["A", "B"])
def test_change_before_t_does_change_zones(candles, cfg, method):
    """Controle: de test hierboven moet iets kunnen detecteren."""
    t = pd.Timestamp(AS_OF_TIMES[0], tz="UTC")
    changed = candles.copy()
    last_closed = changed.index[changed.index + pd.Timedelta(hours=1) <= t][-1]
    changed.loc[last_closed, ["high", "close"]] += 300
    r1 = zones_as_of(candles, t, cfg, method)
    r2 = zones_as_of(changed, t, cfg, method)
    assert r1.price != r2.price
    assert not r1.raw.equals(r2.raw)


def test_all_pivots_confirmed_before_as_of(candles, cfg):
    for t in AS_OF_TIMES:
        t = pd.Timestamp(t, tz="UTC")
        r = zones_as_of(candles, t, cfg, "A")
        assert (r.pivots["confirmed_time"] <= t).all()
        assert (r.raw["last_touch"] < t).all()


def test_pivot_only_known_after_confirmation_candles():
    """Een swing high op candle i is pas bekend als candle i+n gesloten is."""
    n = 3
    highs = [10, 11, 12, 15, 12, 11, 10, 9, 8, 7]   # piek op positie 3
    idx = pd.date_range("2024-01-01", periods=len(highs), freq="h", tz="UTC")
    df = pd.DataFrame({"open": highs, "high": highs, "low": [h - 1 for h in highs],
                       "close": highs, "volume": 1.0}, index=idx)
    df = resample(df, "1h")

    # Tot en met candle 3+n-1 = 5 gesloten: nog geen pivot
    assert len(find_pivots(df.iloc[:6], n, "1h").query("kind == 'high'")) == 0
    # Na sluiting van candle 6 (= 3 + n) wel
    found = find_pivots(df.iloc[:7], n, "1h").query("kind == 'high'")
    assert list(found["price"]) == [15]
    assert found["confirmed_time"].iloc[0] == df["close_time"].iloc[6]
