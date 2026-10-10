"""Ronde 3 (ETF): uitvoeringstiming, geen lookahead, herbalanceren, kosten, bootstrap, afscherming H3."""
import numpy as np
import pandas as pd
import pytest

from etf import data, portfolio, rules, stats


def bdays(start, n):
    return pd.bdate_range(start, periods=n)


def synthetic_prices(n=900, seed=1, assets=("A", "B", "C")):
    rng = np.random.default_rng(seed)
    idx = bdays("2010-01-01", n)
    r = rng.normal(0.0003, 0.01, (n, len(assets)))
    return pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=idx, columns=list(assets))


# ----------------------------- uitvoering ---------------------------------

def test_exec_is_next_trading_day_after_month_end():
    idx = bdays("2020-01-01", 70)
    me = portfolio.month_end_dates(idx)
    assert me[0] == pd.Timestamp("2020-01-31")
    ex = portfolio.exec_dates(me[:2], idx, lag=1)
    assert list(ex) == [pd.Timestamp("2020-02-03"), pd.Timestamp("2020-03-02")]
    assert portfolio.exec_dates(me[:1], idx, lag=0)[0] == me[0]


def test_execution_day_return_belongs_to_old_weights():
    """Signaal eind december: cash. Signaal eind januari: 100% in A. Op de uitvoeringsdag
    (3 feb) stijgt A 50%: dat mag de portefeuille NIET verdienen; de dag erna (+10%) wel."""
    idx = pd.bdate_range("2019-12-31", "2020-02-10")
    rets = pd.DataFrame(0.0, index=idx, columns=["A"])
    rets.loc["2020-02-03", "A"] = 0.5
    rets.loc["2020-02-04", "A"] = 0.1
    cash = pd.Series(0.0, index=idx)
    sim = portfolio.simulate(np.array([[0.0], [1.0]]), [pd.Timestamp("2019-12-31"), pd.Timestamp("2020-01-31")],
                             rets, cash, cost=0.0)
    v = pd.Series(sim["values"][0], index=sim["days"])
    assert sim["days"][0] == pd.Timestamp("2020-01-01")   # eerste uitvoering: eerste handelsdag na signaal
    assert v["2020-02-03"] == pytest.approx(1.0)
    assert v["2020-02-04"] == pytest.approx(1.1)


def test_drift_rebalance_and_costs_by_hand():
    """Twee assets 50/50. A verdubbelt in de eerste periode -> meegedreven 2/3 vs 1/3.
    Terug naar 50/50: verhandeld = |0,5-2/3| + |0,5-1/3| = 1/3; kosten 1% daarvan."""
    idx = pd.DatetimeIndex(["2020-01-31", "2020-02-03", "2020-02-04", "2020-02-28", "2020-03-02", "2020-03-03"])
    rets = pd.DataFrame(0.0, index=idx, columns=["A", "B"])
    rets.loc["2020-02-04", "A"] = 1.0
    cash = pd.Series(0.0, index=idx)
    w = np.array([[0.5, 0.5], [0.5, 0.5]])
    sim = portfolio.simulate(w, [pd.Timestamp("2020-01-31"), pd.Timestamp("2020-02-28")], rets, cash, cost=0.01)
    v = pd.Series(sim["values"][0], index=sim["days"])
    first = 1 - 0.01 * 1.0                               # eerste aankoop: 100% verhandeld
    assert v["2020-02-03"] == pytest.approx(first)
    assert v["2020-02-04"] == pytest.approx(first * 1.5)
    assert sim["turnover"][0, 1] == pytest.approx(1 / 3)
    assert v["2020-03-02"] == pytest.approx(first * 1.5 * (1 - 0.01 / 3))
    assert sim["trades"][0, 1] == 2


def test_cash_part_earns_cash_rate_and_is_free_to_trade():
    idx = pd.DatetimeIndex(["2020-01-31", "2020-02-03", "2020-02-04"])
    rets = pd.DataFrame(0.0, index=idx, columns=["A"])
    cash = pd.Series([0.0, 0.0, 0.01], index=idx)
    sim = portfolio.simulate(np.array([[0.0]]), [pd.Timestamp("2020-01-31")], rets, cash, cost=0.01)
    assert sim["values"][0, -1] == pytest.approx(1.01)


def test_monthly_returns_first_month_vs_start_value():
    days = pd.DatetimeIndex(["2020-01-02", "2020-01-31", "2020-02-28"])
    r = portfolio.monthly_returns(np.array([[0.99, 1.1, 1.21]]), days, "2020-01-01", "2020-03-01")
    assert r.iloc[0, 0] == pytest.approx(0.1) and r.iloc[1, 0] == pytest.approx(0.1)


# ----------------------------- geen lookahead -----------------------------

def tamper_after(prices, t):
    p = prices.copy()
    p.loc[p.index > t] *= 3.0
    return p


@pytest.mark.parametrize("which", ["f1", "f2", "f3"])
def test_signals_ignore_the_future(which):
    prices = synthetic_prices()
    cut = prices.index[600]
    def weights(p):
        me = portfolio.month_end_prices(p)
        av = rules.available(me, 13)
        if which == "f1":
            return rules.f1_trend(me, av, 10)
        if which == "f2":
            return rules.f2_dual_momentum(me, av, 2, 6, pd.Series(0.01, index=me.index))
        return rules.f3_vol_target(rules.equal_weight(av), p.pct_change(), 0.10, 20)
    a, b = weights(prices), weights(tamper_after(prices, cut))
    rows = a.index[a.index <= cut]
    pd.testing.assert_frame_equal(a.loc[rows], b.loc[rows])


def test_available_needs_13_month_ends():
    prices = synthetic_prices(n=400)
    prices.loc[prices.index < "2010-07-15", "C"] = np.nan
    me = portfolio.month_end_prices(prices)
    av = rules.available(me, 13)
    first = av.index[av["C"]][0]
    assert me.loc[:first, "C"].notna().sum() == 13


def test_f1_rule_by_hand():
    me = pd.DataFrame({"A": [1, 2, 3, 2.1], "B": [3, 2, 1, 2.1]}, index=pd.date_range("2020-01-31", periods=4, freq="ME"))
    av = pd.DataFrame(True, index=me.index, columns=me.columns)
    w = rules.f1_trend(me, av, 3)
    assert list(w.iloc[2]) == [0.5, 0.0]             # A boven gemiddelde 2, B eronder
    assert list(w.iloc[3]) == [0.0, 0.5]             # A 2,1 < 2,37; B 2,1 > 1,70


def test_f2_absolute_momentum_goes_to_cash():
    me = pd.DataFrame({"A": [1, 1.1], "B": [1, 1.01], "C": [1, 0.9]}, index=pd.date_range("2020-01-31", periods=2, freq="ME"))
    av = pd.DataFrame(True, index=me.index, columns=me.columns)
    w = rules.f2_dual_momentum(me, av, 2, 1, pd.Series(0.02, index=me.index))
    assert list(w.iloc[1]) == [0.5, 0.0, 0.0]        # B (1%) is top-2 maar onder cash (2%)


def test_f3_no_leverage():
    prices = synthetic_prices()
    me = portfolio.month_end_prices(prices)
    av = rules.available(me, 13)
    w = rules.f3_vol_target(rules.equal_weight(av), prices.pct_change(), 0.50, 20)
    assert (w.sum(axis=1) <= 1 + 1e-12).all()


def test_cash_known_at_uses_previous_months_only(tmp_path):
    cfg = {"data": {"cache_dir": str(tmp_path), "fred_cash": "X"}}
    months = pd.date_range("2019-01-01", periods=24, freq="MS")
    vals = np.full(24, 1.0)
    vals[-1] = 99.0                                  # waarde van de laatste maand (nog niet gepubliceerd)
    (tmp_path / "fred_X.csv").write_text("date,X\n" + "\n".join(f"{d.date()},{v}" for d, v in zip(months, vals)))
    c = data.cash_known_at(cfg, pd.DatetimeIndex([pd.Timestamp("2020-12-31")]), 3, "2100-01-01")
    assert c.iloc[0] == pytest.approx((1.01 ** (1 / 12)) ** 3 - 1)


def test_research_data_never_contains_holdout(tmp_path):
    cfg = {"data": {"cache_dir": str(tmp_path), "price_column": "Adj Close", "calendar_ticker": "SPY"},
           "universe": ["SPY"], "periods": {"research_end": "2021-01-01"}}
    idx = pd.bdate_range("2020-06-01", "2021-06-30", name="date")
    pd.DataFrame({"Adj Close": 1.0, "Close": 1.0}, index=idx).to_parquet(tmp_path / "SPY.parquet")
    p = data.research_prices(cfg)
    assert p.index.max() < pd.Timestamp("2021-01-01")


# ----------------------------- statistiek ---------------------------------

def test_max_drawdown_and_sharpe_by_hand():
    r = np.array([0.1, -0.5, 0.2])
    assert stats.max_drawdown(r) == pytest.approx(-50.0)
    r2 = np.array([0.02, 0.0, 0.02, 0.0])
    assert stats.sharpe(r2, np.zeros(4)) == pytest.approx(0.01 / np.std(r2, ddof=1) * np.sqrt(12))


def test_stationary_bootstrap_block_length():
    idx = stats.stationary_indices(500, 200, 12, np.random.default_rng(0))
    continues = (np.diff(idx, axis=1) == 1) | ((idx[:, :-1] == 499) & (idx[:, 1:] == 0))
    mean_block = 1 / (1 - continues.mean())
    assert 10 < mean_block < 14


def test_circular_shift_keeps_time_in_market():
    rng = np.random.default_rng(0)
    ind = pd.DataFrame({"A": [1.0] * 30 + [0.0] * 30}, index=range(60))
    av = pd.DataFrame(True, index=ind.index, columns=["A"])
    out = rules.random_timing_assets(ind, av, pd.DataFrame(1.0, index=ind.index, columns=["A"]), 50, rng, 12)
    assert np.allclose(out.sum(axis=1)[:, 0], 30)
    switches = np.abs(np.diff(out[:, :, 0], axis=1)).sum(axis=1)
    assert switches.max() <= 2                       # circulair: hooguit één extra wissel


def test_reality_check_not_significant_for_pure_noise():
    rng = np.random.default_rng(5)
    rf = np.zeros(192)
    base = rng.normal(0.005, 0.03, 192)
    pairs = [(base + rng.normal(0, 0.01, 192), base) for _ in range(25)]
    idx = stats.stationary_indices(192, 500, 12, rng)
    d0 = stats.metric_diff("sharpe", pairs[0][0], base, rf)
    assert stats.reality_check("sharpe", d0, pairs, rf, idx)["p"] > 0.05
