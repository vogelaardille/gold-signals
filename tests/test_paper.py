"""Paper trading: herstartbaar, idempotent, geen dubbele trades of meldingen."""
import copy

import pandas as pd
import pytest

from goldsignals.paper import runner
from goldsignals.paper.state import State
from goldsignals.strategies.base import Signal, Strategy


class EveryNBars(Strategy):
    """Test-strategie: long op elke n-de candle, stop/target 3 USD."""
    name = "test_strat"
    zone_method = None

    def generate_signals(self, view):
        if view.i % self.params["n"] == 0:
            c = view.bar["close"]
            return [Signal(self.name, view.t, 1, c - 3, c + 3, "test")]
        return []


@pytest.fixture
def pcfg(cfg):
    c = copy.deepcopy(cfg)
    c["strategies_override"] = {"test_strat": {"status": "candidate", "title": "Test",
                                               "instance": EveryNBars({"n": 5}), "backtest": {}}}
    c["notify"]["zone_alert"]["min_score"] = 0.0
    c["notify"]["weekly"]["enabled"] = False
    c["notify"]["signal"]["chart"] = False      # charts tekenen is traag en hier niet nodig
    return c


def run_upto(pcfg, state_dir, candles, k):
    part = candles.iloc[:k]
    now = part.index[-1] + pd.Timedelta(hours=1, minutes=5)
    return runner.run(pcfg, state_dir, now=now, send=False, candles=part, log=lambda *_: None)


def test_rerun_with_same_data_changes_nothing(pcfg, candles, tmp_path):
    run_upto(pcfg, tmp_path, candles, 3000)
    run_upto(pcfg, tmp_path, candles, 3060)
    s1 = State(tmp_path)
    trades1, outbox1 = s1.trades.copy(), list(s1.outbox)
    res = run_upto(pcfg, tmp_path, candles, 3060)            # exact dezelfde run nog een keer
    s2 = State(tmp_path)
    assert res["status"] == "geen nieuwe candle"
    pd.testing.assert_frame_equal(trades1, s2.trades)
    assert outbox1 == s2.outbox


def test_trades_unique_and_processed_in_order(pcfg, candles, tmp_path):
    run_upto(pcfg, tmp_path, candles, 3000)
    for k in range(3001, 3200, 7):                           # runs met gaten (gemiste uren)
        run_upto(pcfg, tmp_path, candles, k)
    s = State(tmp_path)
    assert s.trades["id"].is_unique
    assert (s.open_trades().shape[0]) <= 1                   # max 1 open trade per strategie
    closed = s.closed_trades().sort_values("entry_time")
    assert (closed["exit_time"] >= closed["entry_time"]).all()
    # trades overlappen niet in tijd (max 1 open)
    assert (closed["entry_time"].iloc[1:].to_numpy() >= closed["exit_time"].iloc[:-1].to_numpy()).all()


def test_same_result_with_catchup_or_hourly(pcfg, candles, tmp_path):
    """Elk uur draaien of een paar uur missen en inhalen moet dezelfde trades geven."""
    a, b = tmp_path / "a", tmp_path / "b"
    run_upto(pcfg, a, candles, 3000)
    run_upto(pcfg, b, candles, 3000)
    for k in range(3001, 3080):
        run_upto(pcfg, a, candles, k)
    run_upto(pcfg, b, candles, 3040)
    run_upto(pcfg, b, candles, 3079)
    cols = ["id", "entry", "exit", "result", "r"]
    pd.testing.assert_frame_equal(State(a).trades[cols].reset_index(drop=True),
                                  State(b).trades[cols].reset_index(drop=True))


def test_messages_never_sent_twice(pcfg, candles, tmp_path, monkeypatch):
    sent = []
    import goldsignals.notify.telegram as tg
    monkeypatch.setattr(tg, "send_message", lambda text: sent.append(text))
    monkeypatch.setattr(tg, "send_photo", lambda path, caption: sent.append(caption))
    part = candles.iloc[:3050]
    now = part.index[-1] + pd.Timedelta(hours=1, minutes=5)
    runner.run(pcfg, tmp_path, now=now, send=True, candles=part, log=lambda *_: None)
    n = len(sent)
    assert n > 0 and State(tmp_path).outbox == []
    runner.run(pcfg, tmp_path, now=now, send=True, candles=part, log=lambda *_: None)
    assert len(sent) == n
    s = State(tmp_path)
    assert not s.queue(s.sent[0], "x", "dubbel")             # sleutel al verstuurd -> geweigerd


def test_failed_send_stays_in_outbox(pcfg, candles, tmp_path, monkeypatch):
    import goldsignals.notify.telegram as tg

    def boom(*a, **k):
        raise tg.TelegramError("netwerk weg")
    monkeypatch.setattr(tg, "send_message", boom)
    monkeypatch.setattr(tg, "send_photo", boom)
    part = candles.iloc[:3050]
    now = part.index[-1] + pd.Timedelta(hours=1, minutes=5)
    runner.run(pcfg, tmp_path, now=now, send=True, candles=part, log=lambda *_: None)
    assert len(State(tmp_path).outbox) > 0


def test_zone_alert_cooldown(pcfg, candles, tmp_path):
    pcfg["notify"]["zone_alert"]["max_distance_atr"] = 100.0     # altijd 'dichtbij'
    run_upto(pcfg, tmp_path, candles, 3000)
    n1 = sum(1 for m in State(tmp_path).outbox if m["kind"] == "zone")
    run_upto(pcfg, tmp_path, candles, 3001)                       # een uur later: cooldown
    n2 = sum(1 for m in State(tmp_path).outbox if m["kind"] == "zone")
    assert n1 > 0 and n2 == n1


def test_rejected_strategy_never_trades(cfg, candles, tmp_path):
    c = copy.deepcopy(cfg)
    c["notify"]["weekly"]["enabled"] = False
    # active_strategies filtert op status; simuleer met een strategies.json
    import json
    p = tmp_path / "strategies.json"
    p.write_text(json.dumps({"x": {"status": "rejected", "class": "tests.test_paper:EveryNBars", "params": {"n": 1}}}))
    orig, orig_fwd = runner.STRATEGIES_FILE, runner.FORWARD_FILE
    runner.STRATEGIES_FILE = str(p)
    runner.FORWARD_FILE = str(tmp_path / "geen_forward.json")   # echte forward-tests hier buiten beschouwing
    try:
        assert runner.active_strategies(c) == {}
    finally:
        runner.STRATEGIES_FILE, runner.FORWARD_FILE = orig, orig_fwd
