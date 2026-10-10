"""Backtest-engine: fills, SL/TP-volgorde, kosten, positiegrootte, max open trades."""
import numpy as np
import pandas as pd
import pytest

from goldsignals.backtest import holdout
from goldsignals.backtest.engine import run_backtest
from goldsignals.backtest.validation import decide_status, deflated_sharpe, not_single_year
from goldsignals.market import Market
from goldsignals.strategies.base import Signal, Strategy

CFG = {"account": {"start_equity_eur": 10000, "risk_pct": 1.0, "eurusd": 1.10, "max_open_per_strategy": 1},
       "costs": {"spread_usd": 0.40, "slippage_usd": 0.10}}


def make_market(rows):
    """rows: lijst van (open, high, low, close)."""
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="h", tz="UTC")
    c = pd.DataFrame(rows, columns=["open", "high", "low", "close"], index=idx, dtype=float)
    c["volume"] = 1.0
    f = pd.DataFrame({"atr": 1.0}, index=idx)
    return Market(c, f)


class OneShot(Strategy):
    """Geeft op candle `at` een vast signaal."""
    name = "oneshot"

    def __init__(self, at, direction, stop, target, min_rr=0.0, every_bar=False):
        super().__init__({})
        self.at, self.d, self.stop, self.target, self.min_rr, self.every = at, direction, stop, target, min_rr, every_bar

    def generate_signals(self, view):
        if view.i == self.at or self.every:
            return [Signal(self.name, view.t, self.d, self.stop, self.target, "test", min_rr=self.min_rr)]
        return []


def test_entry_is_next_open_not_signal_close():
    m = make_market([(100, 100, 100, 100), (101, 101, 101, 101), (101, 104, 101, 103)])
    t = run_backtest(OneShot(0, 1, 99, 103.5), m, 0, 2, CFG, cost_mult=0).trades
    assert t["entry"].iloc[0] == 101          # open van candle 1, niet slot 100 van candle 0
    assert t["entry_time"].iloc[0] == m.candles.index[1]


def test_sl_counts_first_when_candle_hits_both():
    m = make_market([(100, 100, 100, 100), (100, 100, 100, 100), (100, 103, 98, 100)])
    t = run_backtest(OneShot(0, 1, 99, 102), m, 0, 2, CFG, cost_mult=0).trades
    assert t["result"].iloc[0] == "sl"
    assert t["r"].iloc[0] == pytest.approx(-1.0)


def test_short_tp_and_r():
    m = make_market([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (99, 99, 96, 97)])
    t = run_backtest(OneShot(0, -1, 101, 98), m, 0, 2, CFG, cost_mult=0).trades
    assert t["result"].iloc[0] == "tp"
    assert t["r"].iloc[0] == pytest.approx(2.0)


def test_gap_beyond_stop_exits_at_open():
    m = make_market([(100, 100, 100, 100), (100, 100.5, 99.5, 100), (97, 97.5, 96, 97)])
    t = run_backtest(OneShot(0, 1, 99, 102), m, 0, 2, CFG, cost_mult=0).trades
    assert t["exit"].iloc[0] == 97
    assert t["r"].iloc[0] == pytest.approx(-3.0)


def test_no_fill_when_open_already_beyond_target():
    m = make_market([(100, 100, 100, 100), (103, 103, 103, 103), (103, 103, 103, 103)])
    t = run_backtest(OneShot(0, 1, 99, 102), m, 0, 2, CFG, cost_mult=0).trades
    assert t.empty


def test_min_rr_checked_at_actual_entry():
    # Signaal met target 102, stop 99, min R:R 2. Open 100.5 -> R:R 1.5/1.5 = 1 -> geen trade.
    m = make_market([(100, 100, 100, 100), (100.5, 100.5, 100.5, 100.5), (100, 100, 100, 100)])
    t = run_backtest(OneShot(0, 1, 99, 102, min_rr=2.0), m, 0, 2, CFG, cost_mult=0).trades
    assert t.empty


def test_position_size_risk_one_percent_including_costs():
    m = make_market([(100, 100, 100, 100), (100, 100, 100, 100), (100, 100, 95, 96)])
    t = run_backtest(OneShot(0, 1, 98, 106), m, 0, 2, CFG, cost_mult=1).trades
    row = t.iloc[0]
    cost = 0.40 + 2 * 0.10
    assert row["risk_eur"] == pytest.approx(100.0)                      # 1% van 10.000
    assert row["units_oz"] == pytest.approx(100 * 1.10 / (2 + cost))    # risico in USD / (stopafstand + kosten)
    assert row["r"] == pytest.approx(-1.0)                              # stop incl. kosten = -1R
    assert row["pnl_eur"] == pytest.approx(-100.0)
    assert row["equity_after"] == pytest.approx(9900.0)


def test_costs_reduce_winner():
    m = make_market([(100, 100, 100, 100), (100, 100, 100, 100), (100, 105, 100, 104)])
    t0 = run_backtest(OneShot(0, 1, 98, 104), m, 0, 2, CFG, cost_mult=0).trades
    t2 = run_backtest(OneShot(0, 1, 98, 104), m, 0, 2, CFG, cost_mult=2).trades
    assert t0["r"].iloc[0] == pytest.approx(2.0)
    c = 2 * 0.6
    assert t2["r"].iloc[0] == pytest.approx((4 - c) / (2 + c))


def test_max_one_open_trade():
    rows = [(100, 100.2, 99.8, 100)] * 10
    m = make_market(rows)
    t = run_backtest(OneShot(0, 1, 90, 110, every_bar=True), m, 0, 9, CFG, cost_mult=0).trades
    assert len(t) == 1 and t["result"].iloc[0] == "einde"


def test_deflated_sharpe_penalizes_many_trials():
    rng = np.random.default_rng(0)
    r = rng.normal(0.1, 1, 300)
    trial_sr = rng.normal(0, 0.08, 500)
    few = deflated_sharpe(r, 2, trial_sr)["dsr"]
    many = deflated_sharpe(r, 500, trial_sr)["dsr"]
    assert many < few


def test_single_year_rule():
    t = pd.DataFrame({"entry_time": pd.to_datetime(["2022-03-01", "2023-03-01", "2024-03-01"], utc=True),
                      "r": [10.0, -1.0, -1.0]})
    ok, rest = not_single_year(t)
    assert not ok and rest == -2.0


def test_status_never_validated_without_holdout():
    rng = np.random.default_rng(1)
    years = pd.to_datetime(rng.choice(["2022-06-01", "2023-06-01", "2024-06-01"], 200), utc=True)
    oos = pd.DataFrame({"entry_time": years, "r": rng.normal(0.3, 1, 200)})
    vcfg = {"min_trades_research": 100, "min_trades_holdout": 30, "dsr_threshold": 0.95}
    assert decide_status(oos, vcfg, holdout=None, dsr=0.99, excess=0.5)["status"] == "candidate"
    ho = {"n": 50, "avg_r": 0.2}
    assert decide_status(oos, vcfg, holdout=ho, dsr=0.99, excess=0.5)["status"] == "validated"
    assert decide_status(oos, vcfg, holdout={"n": 10, "avg_r": 1.0}, dsr=0.99, excess=0.5)["status"] == "candidate"
    assert decide_status(oos, vcfg, holdout={**ho, "burned": True}, dsr=0.99, excess=0.5)["status"] == "candidate"
    assert decide_status(oos.head(50), vcfg)["status"] == "rejected"


def test_holdout_opened_only_once(tmp_path, monkeypatch):
    monkeypatch.setattr(holdout, "LOG_PATH", tmp_path / "log.json")
    calls = []

    def run():
        calls.append(1)
        return {"n": 40, "avg_r": 0.1}

    s = OneShot(0, 1, 99, 102)
    first = holdout.open_once("x", s, run)
    second = holdout.open_once("x", s, run)
    assert len(calls) == 1 and first["avg_r"] == second["avg_r"] and not second["burned"]
    s.params = {"changed": True}                 # strategie aangepast na openen
    assert holdout.open_once("x", s, run)["burned"] is True
    assert len(calls) == 1
