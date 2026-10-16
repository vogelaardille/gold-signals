"""Ronde 4 (fx/): offline tests met synthetische data."""
import numpy as np
import pandas as pd

from fx import data, engine, families


def _bars(times, mid, spread=0.0002, rng_width=0.0005):
    """Synthetische candles: mid-pad met vaste spread en range."""
    mid = np.asarray(mid, dtype=float)
    df = pd.DataFrame(index=pd.DatetimeIndex(times))
    for side, sgn in (("bid", -1), ("ask", 1)):
        o = mid + sgn * spread / 2
        df[f"{side}_open"], df[f"{side}_close"] = o, o
        df[f"{side}_high"], df[f"{side}_low"] = o + rng_width, o - rng_width
    for f in ("open", "high", "low", "close"):
        df[f] = (df[f"bid_{f}"] + df[f"ask_{f}"]) / 2
    return df


def _week(start="2019-07-08 00:00"):  # ma 8 juli 2019 (zomertijd)
    return pd.date_range(start, periods=24 * 5 - 3, freq="h", tz="UTC")


def _cfg(tmp_path):
    cfg = data.load_config()
    cfg["data"] = dict(cfg["data"], cache_dir=str(tmp_path), excluded_years={"USD/JPY": [2010]})
    return cfg


def _write(cfg, pair, index, spread):
    base = pd.DataFrame({"open": 1.0, "high": 1.002, "low": 0.998, "close": 1.001, "volume": 1.0}, index=index)
    data.cache_path(cfg, pair, "bid").parent.mkdir(parents=True, exist_ok=True)
    base.to_parquet(data.cache_path(cfg, pair, "bid"))
    ask = base.copy()
    ask[["open", "high", "low", "close"]] += spread
    ask.to_parquet(data.cache_path(cfg, pair, "ask"))


def test_session_bounds_follow_new_york_dst():
    # zomer: vrijdag 17:00 NY = 21:00 UTC; winter: 22:00 UTC
    summer = pd.DatetimeIndex(["2019-07-12 20:00", "2019-07-12 21:00", "2019-07-14 20:00", "2019-07-14 21:00"], tz="UTC")
    winter = pd.DatetimeIndex(["2019-01-11 21:00", "2019-01-11 22:00", "2019-01-13 21:00", "2019-01-13 22:00"], tz="UTC")
    assert list(data.in_fx_session(summer)) == [True, False, False, True]
    assert list(data.in_fx_session(winter)) == [True, False, False, True]


def test_load_pair_respects_until_and_never_returns_open_candle(tmp_path):
    cfg = _cfg(tmp_path)
    idx = pd.date_range("2019-12-31 10:00", "2020-01-02 10:00", freq="h", tz="UTC")
    _write(cfg, "EUR/USD", idx, 0.0001)
    until = pd.Timestamp("2020-01-01", tz="UTC")
    df = data.load_pair(cfg, "EUR/USD", until=until)
    assert (df.index + pd.Timedelta(hours=1) <= until).all()
    assert df.index[-1] == pd.Timestamp("2019-12-31 23:00", tz="UTC")
    assert abs(df["open"].iloc[0] - 1.00005) < 1e-12  # mid = gemiddelde van bid en ask


def test_load_pair_drops_weekend_crossed_and_excluded_years(tmp_path):
    cfg = _cfg(tmp_path)
    idx = pd.date_range("2010-06-04 18:00", "2010-06-07 12:00", freq="h", tz="UTC")  # vr t/m ma
    _write(cfg, "EUR/USD", idx, -0.0001)  # ask < bid overal
    assert len(data.load_pair(cfg, "EUR/USD", until=pd.Timestamp("2011-01-01", tz="UTC"))) == 0
    _write(cfg, "EUR/USD", idx, 0.0001)
    df = data.load_pair(cfg, "EUR/USD", until=pd.Timestamp("2011-01-01", tz="UTC"))
    assert data.in_fx_session(df.index).all() and len(df) < len(idx)
    _write(cfg, "USD/JPY", idx, 0.01)
    assert len(data.load_pair(cfg, "USD/JPY", until=pd.Timestamp("2011-01-01", tz="UTC"))) == 0


def test_research_data_has_nothing_from_holdout():
    cfg = data.load_config()
    if not data.cache_path(cfg, "EUR/USD", "bid").exists():
        return  # cache ontbreekt (bijv. in CI): niets te controleren
    df = data.research_data(cfg, "EUR/USD")
    assert df.index.max() + pd.Timedelta(hours=1) <= pd.Timestamp(cfg["periods"]["research_end"], tz="UTC")


def test_first_fridays_are_fridays():
    days = data.first_fridays(pd.Timestamp("2019-01-01", tz="UTC"), pd.Timestamp("2019-12-31", tz="UTC"))
    assert len(days) == 12 and all(d.weekday() == 4 and d.day <= 7 for d in days)


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

def test_long_buys_ask_sells_bid_with_slippage():
    t = _week()
    px = engine.prices(_bars(t, np.full(len(t), 1.1000)))
    tr = engine.simulate(px, [2], [1], pip=0.0001, slip_pips=0.1, base_is_usd=False, exit_idx=[5])
    assert abs(tr.entry_px[0] - (1.1001 + 0.00001)) < 1e-12
    assert abs(tr.exit_px[0] - (1.0999 - 0.00001)) < 1e-12
    # vlakke markt: netto = −(spread + 2× slippage), bruto = 0
    assert abs(tr.net_bp[0] - (1.09989 / 1.10011 - 1) * 1e4) < 1e-9
    assert abs(tr.gross_bp[0]) < 1e-9


def test_usd_base_return_uses_exit_rate():
    r = engine.returns_bp(True, np.array([1]), np.array([100.0]), np.array([101.0]))
    assert abs(r[0] - (1 - 100 / 101) * 1e4) < 1e-9


def test_stop_before_target_in_same_bar_and_gap_through_stop():
    t = _week()
    df = _bars(t, np.full(len(t), 1.1000), rng_width=0.0001)
    df.iloc[4, df.columns.get_loc("bid_low")] = 1.0900   # raakt stop
    df.iloc[4, df.columns.get_loc("bid_high")] = 1.1100  # raakt ook target
    tr = engine.simulate(engine.prices(df), [2], [1], 0.0001, 0.0, False,
                         exit_idx=[10], stop_dist=[0.0050], target_r=1)
    assert tr.reason[0] == "stop" and tr.exit_time[0] == t[4]
    df2 = _bars(t, np.r_[np.full(5, 1.1000), np.full(len(t) - 5, 1.0800)], rng_width=0.0001)
    tr2 = engine.simulate(engine.prices(df2), [2], [1], 0.0001, 0.0, False,
                          exit_idx=[10], stop_dist=[0.0050])
    assert tr2.reason[0] == "stop" and abs(tr2.exit_px[0] - df2.bid_open.iloc[5]) < 1e-12  # exit op de open


def test_max_one_open_trade():
    t = _week()
    px = engine.prices(_bars(t, np.full(len(t), 1.1000)))
    tr = engine.simulate(px, [2, 3, 6], [1, 1, 1], 0.0001, 0.0, False, exit_idx=[6, 7, 8])
    assert list(tr.entry_time) == [t[2], t[6]]


def test_force_exit_at_16_ny():
    t = _week()
    px = engine.prices(_bars(t, np.full(len(t), 1.1000)))
    tr = engine.simulate(px, [2], [1], 0.0001, 0.0, False, force_ny_hour=16)
    assert tr.exit_time[0].tz_convert("America/New_York").hour == 16


# ---------------------------------------------------------------------------
# F1-vensters (zomertijd) en lookahead van F2/F3
# ---------------------------------------------------------------------------

def test_f1_windows_follow_local_time():
    cfg = data.load_config()
    for start, entry_utc in (("2019-07-08 00:00", 6), ("2019-01-07 00:00", 7)):
        t = _week(start)
        ei, xi = families.f1_windows(t, cfg["f1"]["legs"]["E_pre"])
        assert (t[ei].hour == entry_utc).all() and (t[xi].hour == entry_utc + 6).all()
    t = _week()
    ei, xi = families.f1_windows(t, cfg["f1"]["legs"]["T_pre"])
    assert (t[xi].hour == 1).all()  # 10:00 Tokio = 01:00 UTC, het hele jaar
    assert (t[ei].tz_convert("America/New_York").hour == 18).all()


def _random_walk(n, seed=1):
    rng = np.random.default_rng(seed)
    return 1.1 + np.cumsum(rng.normal(0, 0.0015, n))


def test_f2_f3_signals_do_not_use_future_bars():
    cfg = data.load_config()
    t = pd.date_range("2019-07-08", periods=24 * 7 * 8, freq="h", tz="UTC")
    t = t[data.in_fx_session(t)]
    mid = _random_walk(len(t))
    cut = len(t) // 2
    mid2 = mid.copy()
    mid2[cut + 1:] += np.random.default_rng(9).normal(0, 0.01, len(t) - cut - 1)
    px, px2 = engine.prices(_bars(t, mid)), engine.prices(_bars(t, mid2))
    for variant in ("bounce", "breakout"):
        s1, d1 = families.f2_signals(px, 0.002, 0.0, variant, 24)
        s2, d2 = families.f2_signals(px2, 0.002, 0.0, variant, 24)
        assert (s1 <= cut).sum() > 0  # anders toetst de test niets
        assert list(s1[s1 <= cut]) == list(s2[s2 <= cut]) and list(d1[s1 <= cut]) == list(d2[s2 <= cut])
    a1, a2 = families.f3_setups(px, cfg)[0], families.f3_setups(px2, cfg)[0]
    assert (a1.i <= cut).sum() > 0
    assert a1[a1.i <= cut].equals(a2[a2.i <= cut])


def test_time_units_ms_index_still_finds_windows_and_force_exit():
    # de parquet-cache geeft tijden in milliseconden; berekende tijden zijn in microseconden
    t = _week().as_unit("ms")
    cfg = data.load_config()
    ei, xi = families.f1_windows(t, cfg["f1"]["legs"]["E_pre"])
    assert len(ei) == 5 and (t[xi].hour == 12).all()
    px = engine.prices(_bars(t, np.full(len(t), 1.1)))
    tr = engine.simulate(px, [2], [1], 0.0001, 0.0, False, force_ny_hour=16)
    assert tr.exit_time[0].tz_convert("America/New_York").hour == 16


def test_h4_guard_only_candidates_and_only_once(tmp_path, monkeypatch):
    import pytest
    from fx import holdout
    monkeypatch.setattr(holdout, "LOG", tmp_path / "holdout_log.json")
    with pytest.raises(PermissionError):
        holdout.open_h4("F2-B", "rejected")
    holdout.open_h4("F1-EU", "candidate")
    with pytest.raises(PermissionError):
        holdout.open_h4("F1-EU", "candidate")
    assert holdout.times_opened("F1-EU") == 1


# ---------------------------------------------------------------------------
# Ronde 5: intraday momentum (G1, G2)
# ---------------------------------------------------------------------------

def _session_walk(weeks=6, seed=3):
    t = pd.date_range("2019-07-07 21:00", periods=24 * 7 * weeks, freq="h", tz="UTC")
    t = t[data.in_fx_session(t)]
    return t, _random_walk(len(t), seed)


def test_g1_signal_uses_only_bars_before_entry():
    from fx import momentum
    t, mid = _session_walk()
    px = engine.prices(_bars(t, mid))
    st = momentum.g1_setups(t, px["close"], px["open"], 17, 12, 16)
    assert len(st) > 10
    assert (t[st.entry].tz_convert("America/New_York").hour == 12).all()
    assert (t[st.exit].tz_convert("America/New_York").hour == 16).all()
    mid2 = mid.copy()
    for e in st.entry:  # alles vanaf de entry-bar veranderen mag het teken niet raken
        mid2[e:e + 4] += 0.05
    px2 = engine.prices(_bars(t, mid2))
    st2 = momentum.g1_setups(t, px2["close"], px2["open"], 17, 12, 16)
    assert (st.dir.to_numpy() == st2.dir.to_numpy()).all()


def test_g2_bands_and_signals_do_not_use_future():
    from fx import momentum
    t, mid = _session_walk(weeks=8)
    cut = len(t) * 3 // 4
    mid2 = mid.copy()
    mid2[cut + 1:] += np.random.default_rng(5).normal(0, 0.01, len(t) - cut - 1)
    px, px2 = engine.prices(_bars(t, mid)), engine.prices(_bars(t, mid2))
    b1 = momentum.g2_bands(px, "Europe/London", 8, 14, 10, 16)
    b2 = momentum.g2_bands(px2, "Europe/London", 8, 14, 10, 16)
    early = b1.i <= cut
    assert b1.sigma[early].notna().sum() > 0
    assert np.allclose(b1.sigma[early].fillna(-1), b2.sigma[early].fillna(-1))  # σ alleen uit eerdere dagen
    s1 = momentum.g2_trades(px, b1, 1.0, [14, 15, 16, 17])
    s2 = momentum.g2_trades(px2, b2, 1.0, [14, 15, 16, 17])
    assert len(s1[s1.entry <= cut]) > 0
    cols = ["entry", "dir"]  # de exit van een trade die vóór de knip begint, mag erna anders zijn
    assert s1.loc[s1.entry <= cut, cols].reset_index(drop=True).equals(
        s2.loc[s2.entry <= cut, cols].reset_index(drop=True))


def test_c5_guard_only_candidates_and_only_once(tmp_path, monkeypatch):
    import pytest
    from fx import open_c5
    monkeypatch.setattr(open_c5, "LOG", tmp_path / "holdout_log.json")
    with pytest.raises(PermissionError):
        open_c5.open_c5("G2", "rejected")
    open_c5.open_c5("G1", "candidate")
    with pytest.raises(PermissionError):
        open_c5.open_c5("G1", "candidate")
