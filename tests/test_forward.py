"""Forward-test vol_squeeze_4h: vaste code (vingerafdruk), stopregel, geen lookahead, uitvoering."""
import re

import numpy as np
import pandas as pd
import pytest

from goldsignals.backtest.engine import anchor_to_entry
from goldsignals.config import project_path
from goldsignals.features import compute_features
from goldsignals.market import Market
from goldsignals.round2 import forward
from goldsignals.strategies.base import MarketView, Signal
from goldsignals.strategies.vol_squeeze_4h import VolSqueeze4h, bars_4h, crossed_4h_boundary


def test_fingerprint_matches_forward_md():
    """De code van de forward-strategie mag nooit meer veranderen (FORWARD.md)."""
    text = (project_path("research/round2/FORWARD.md")).read_text(encoding="utf-8")
    m = re.search(r"Vingerafdruk[^`]*`([0-9a-f]{16})`", text)
    assert m, "vingerafdruk ontbreekt in FORWARD.md"
    assert forward.fingerprint() == m.group(1), "strategiecode gewijzigd na het vastleggen!"


def closed(rs):
    t = pd.date_range("2027-01-01", periods=len(rs), freq="D", tz="UTC")
    return pd.DataFrame({"r": rs, "exit_time": t})


def test_stop_rule_from_trade_40():
    # 39 verliezen: nog geen controle. Bij trade 40 is het gemiddelde < -0,25 -> gestopt.
    assert forward.forward_state(closed([-1.0] * 39))["status"] == "actief"
    s = forward.forward_state(closed([-1.0] * 40))
    assert s["status"] == "gestopt" and s["at_trade"] == 40


def test_stop_rule_not_triggered_by_early_dip_that_recovers():
    rs = [-1.0] * 25 + [1.7] * 15          # na 40 trades gemiddeld +0,01 R
    assert forward.forward_state(closed(rs))["status"] == "actief"


def test_stop_rule_checked_after_every_trade_until_100():
    rs = [0.2] * 40 + [-1.0] * 40          # (8 - k) / (40 + k) < -0,25 vanaf k = 25 -> trade 65
    s = forward.forward_state(closed(rs))
    assert s["status"] == "gestopt" and s["at_trade"] == 65


def test_evaluation_pause_at_100():
    rs = [1.7, -1.0] * 50
    assert forward.forward_state(closed(rs))["status"] == "evaluatie"


def test_anchor_to_entry_keeps_distances():
    s = Signal("x", pd.Timestamp("2027-01-01", tz="UTC"), -1, 110.0, 80.0, "t", meta={"stop_dist": 5.0, "rr": 2.0})
    a = anchor_to_entry(s, 101.0)
    assert a.stop == 106.0 and a.target == 91.0
    plain = Signal("x", s.time, 1, 95.0, 110.0, "t")
    assert anchor_to_entry(plain, 101.0) is plain       # andere strategieën: ongewijzigd


def test_crossed_4h_boundary():
    t = pd.Timestamp("2026-10-07 13:00", tz="UTC")       # 09:00 NY (zomertijd) = 4h-grens
    assert crossed_4h_boundary(t - pd.Timedelta(hours=1), t)
    assert not crossed_4h_boundary(t, t + pd.Timedelta(hours=1))


@pytest.fixture(scope="module")
def market(candles, cfg):
    return Market(candles, compute_features(candles, cfg))


def signals_between(m, i0, i1, strat):
    out = {}
    for i in range(i0, i1):
        for s in strat.generate_signals(MarketView(m, i)):
            out[s.time] = (s.direction, round(s.meta["stop_dist"], 9))
    return out


def test_plugin_signals_do_not_use_future(market, candles, cfg):
    i0, i1 = 5800, 6700
    base = signals_between(market, i0, i1, VolSqueeze4h())
    assert len(base) > 0, "test zinloos zonder signalen"
    tampered = candles.copy()
    after = np.arange(len(candles)) >= i1
    for col in ("open", "high", "low", "close"):
        tampered.loc[after, col] += 300
    m2 = Market(tampered, compute_features(tampered, cfg))
    assert signals_between(m2, i0, i1, VolSqueeze4h()) == base


def test_signal_only_on_4h_close(market):
    strat = VolSqueeze4h()
    for i in range(5800, 6700):
        for s in strat.generate_signals(MarketView(market, i)):
            assert s.time.tz_convert("America/New_York").hour in {17, 21, 1, 5, 9, 13}


def test_forced_mode_uses_same_exits(market):
    i = 6000
    t = market.close_time[i]
    b = bars_4h(market.candles.iloc[:i + 1], t)
    # zoek een 1h-index waar net een 4h-candle sloot
    while b["close_time"].iloc[-1] != t:
        i += 1
        t = market.close_time[i]
        b = bars_4h(market.candles.iloc[:i + 1], t)
    s = VolSqueeze4h(forced={t: -1}).generate_signals(MarketView(market, i))
    assert len(s) == 1 and s[0].direction == -1 and s[0].meta["rr"] == 2.0
