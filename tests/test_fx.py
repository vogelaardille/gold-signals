"""Ronde 4 (fx/): offline tests met synthetische data."""
import pandas as pd

from fx import data


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
