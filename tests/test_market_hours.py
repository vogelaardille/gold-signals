import pandas as pd

from goldsignals.paper.market_hours import expected_last_candle, is_trading_hour, market_open_now


def ts(s):
    return pd.Timestamp(s, tz="UTC")


def test_weekend_closed():
    assert not is_trading_hour(ts("2026-10-10 12:00"))      # zaterdag
    assert not is_trading_hour(ts("2026-10-11 20:00"))      # zondag 16:00 NY
    assert is_trading_hour(ts("2026-10-11 22:00"))          # zondag 18:00 NY (EDT) = opening
    assert not is_trading_hour(ts("2026-10-09 21:00"))      # vrijdag 17:00 NY = dicht


def test_daily_break_and_winter_time():
    assert not is_trading_hour(ts("2026-10-07 21:00"))      # woensdag 17:00 NY (zomertijd)
    assert is_trading_hour(ts("2026-10-07 22:00"))
    assert not is_trading_hour(ts("2026-12-09 22:00"))      # winter: 17:00 NY = 22:00 UTC


def test_expected_last_candle_on_saturday_is_friday_last():
    assert expected_last_candle(ts("2026-10-10 14:05")) == ts("2026-10-09 20:00")
    assert not market_open_now(ts("2026-10-10 14:05"))
    assert market_open_now(ts("2026-10-12 10:05"))
