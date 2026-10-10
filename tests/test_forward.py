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


# ---------------- koppeling met de live paper-runner ----------------

import copy  # noqa: E402
import json  # noqa: E402

from goldsignals.paper import runner  # noqa: E402
from goldsignals.paper.state import State  # noqa: E402
from goldsignals.strategies.base import Strategy  # noqa: E402


class AlwaysLosesLong(Strategy):
    """Long op elke 2e candle met een piepkleine stop: verliest vrijwel altijd (-1R)."""
    name = "fwd_test"
    zone_method = None

    def generate_signals(self, view):
        if view.i % 2 == 0:
            c = view.bar["close"]
            return [Signal(self.name, view.t, 1, c - 0.01, c + 1000, "test")]
        return []


@pytest.fixture
def fcfg(cfg):
    c = copy.deepcopy(cfg)
    c["strategies_override"] = {"fwd_test": {"status": "forward", "label": forward.LABEL, "notify_signals": False,
                                             "instance": AlwaysLosesLong(), "backtest": {}}}
    c["notify"]["zone_alert"]["enabled"] = False
    c["notify"]["weekly"]["enabled"] = False
    c["notify"]["signal"]["chart"] = False
    return c


def run_to(fcfg, d, candles, k):
    part = candles.iloc[:k]
    return runner.run(fcfg, d, now=part.index[-1] + pd.Timedelta(hours=1, minutes=5), send=False,
                      candles=part, log=lambda *_: None)


def test_forward_no_signal_messages_but_logged_and_labelled(fcfg, candles, tmp_path):
    run_to(fcfg, tmp_path, candles, 3000)
    run_to(fcfg, tmp_path, candles, 3040)
    s = State(tmp_path)
    assert not any(m["kind"] == "signal" for m in s.outbox)          # geen signaalmeldingen
    assert len(s.meta["signal_log"]) > 0                              # wel gelogd
    updates = [m["text"] for m in s.outbox if m["kind"] == "trade"]
    assert updates and all(forward.LABEL in u for u in updates)       # label in elke trade-update
    assert s.meta["forward_start"]["fwd_test"] == candles.index[2999].isoformat()


def test_forward_stop_rule_blocks_new_trades(fcfg, candles, tmp_path):
    run_to(fcfg, tmp_path, candles, 3000)
    for k in range(3072, 3500, 72):
        run_to(fcfg, tmp_path, candles, k)
    s = State(tmp_path)
    closed = s.closed_trades()
    assert s.meta["forward_status"]["fwd_test"] == "gestopt"
    assert len(closed) == forward.STOP_AFTER_TRADES                   # na trade 40 geen nieuwe trades
    assert s.open_trades().empty and not s.pending
    assert any("STOPREGEL" in m["text"] for m in s.outbox)


def test_forward_requires_approval_and_matching_fingerprint(tmp_path, monkeypatch):
    p = tmp_path / "fwd.json"
    base = {"class": "goldsignals.strategies.vol_squeeze_4h:VolSqueeze4h", "params": {}, "status": "forward",
            "label": forward.LABEL}
    monkeypatch.setattr(runner, "FORWARD_FILE", str(p))
    p.write_text(json.dumps({"a": {**base, "fingerprint": forward.fingerprint()}}))
    assert runner.forward_strategies() == {}                          # geen akkoord
    p.write_text(json.dumps({"a": {**base, "approved_by_user": "2026-10-10", "fingerprint": "0" * 16}}))
    assert runner.forward_strategies() == {}                          # code gewijzigd
    p.write_text(json.dumps({"a": {**base, "approved_by_user": "2026-10-10", "fingerprint": forward.fingerprint()}}))
    assert list(runner.forward_strategies()) == ["a"]
