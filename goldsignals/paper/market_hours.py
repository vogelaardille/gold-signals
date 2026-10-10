"""Wanneer is de goudmarkt open, en welke 1h-candle zou er nu gesloten moeten zijn?

Goud (spot) handelt van zondag 18:00 tot vrijdag 17:00 New York-tijd, met elke dag een
pauze van 17:00 tot 18:00 NY. Feestdagen (Kerst, Nieuwjaar) kent deze functie niet;
dan meldt de run een ontbrekende candle (maximaal 1 SYSTEEM-melding per 6 uur).
"""
import pandas as pd

NY = "America/New_York"


def is_trading_hour(candle_open: pd.Timestamp) -> bool:
    """Zou er een 1h-candle moeten zijn die op dit moment (UTC) opent?"""
    t = pd.Timestamp(candle_open).tz_convert(NY)
    wd, h = t.weekday(), t.hour            # maandag = 0 ... zondag = 6
    if h == 17:                            # dagelijkse pauze
        return False
    if wd == 5:                            # zaterdag
        return False
    if wd == 4 and h >= 17:                # vrijdag na sluiting
        return False
    if wd == 6 and h < 18:                 # zondag voor opening
        return False
    return True


def expected_last_candle(now: pd.Timestamp) -> pd.Timestamp:
    """Openingstijd van de laatste candle die op `now` gesloten had moeten zijn (UTC).
    Loopt terug tot een handelsuur (max 3 dagen)."""
    t = pd.Timestamp(now).tz_convert("UTC").floor("h") - pd.Timedelta(hours=1)
    for _ in range(72):
        if is_trading_hour(t):
            return t
        t -= pd.Timedelta(hours=1)
    return t


def market_open_now(now: pd.Timestamp) -> bool:
    """Is er sinds de vorige run (een uur geleden) een candle gesloten die we verwachten?"""
    last = pd.Timestamp(now).tz_convert("UTC").floor("h") - pd.Timedelta(hours=1)
    return is_trading_hour(last)
