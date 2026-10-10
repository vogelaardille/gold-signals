import pandas as pd

from goldsignals.data.timeframes import build_timeframes, resample


def test_daily_closes_at_17_new_york_winter_and_summer(candles):
    daily = resample(candles, "1d")
    close_ny = daily["close_time"].dt.tz_convert("America/New_York")
    assert (close_ny.dt.hour == 17).all() and (close_ny.dt.minute == 0).all()
    # Winter (EST, UTC-5): 17:00 NY = 22:00 UTC. Zomer (EDT, UTC-4): 21:00 UTC.
    winter = daily[daily["close_time"].dt.month == 1]["close_time"].dt.hour
    summer = daily[daily["close_time"].dt.month == 7]["close_time"].dt.hour
    assert set(winter) == {22}
    assert set(summer) == {21}


def test_resampled_values_match_1h(candles):
    daily = resample(candles, "1d")
    day = daily.iloc[50]
    inside = candles[(candles.index >= day.name) & (candles.index < day["close_time"])]
    assert day["high"] == inside["high"].max()
    assert day["low"] == inside["low"].min()
    assert day["open"] == inside["open"].iloc[0]
    assert day["close"] == inside["close"].iloc[-1]


def test_4h_candles_nest_inside_daily(candles, cfg):
    frames = build_timeframes(candles, cfg)   # alleen gesloten candles
    daily, h4 = frames["1d"], frames["4h"]
    # Elke 4h-grens valt op 17, 21, 01, 05, 09 of 13 uur New York-tijd
    assert set(h4.index.tz_convert("America/New_York").hour) <= {17, 21, 1, 5, 9, 13}
    # Elke daily-sluiting is ook een 4h-sluiting
    assert set(daily["close_time"]) <= set(h4["close_time"])


def test_running_candle_is_excluded(candles, cfg):
    # as_of op woensdag 14:00 UTC: de daily en de 4h-candle lopen dan nog
    as_of = pd.Timestamp("2024-06-12 14:00", tz="UTC")
    frames = build_timeframes(candles, cfg, as_of)
    for tf, f in frames.items():
        assert (f["close_time"] <= as_of).all(), tf
    assert frames["1h"]["close_time"].iloc[-1] == as_of
    assert frames["1d"]["close_time"].iloc[-1] < as_of
