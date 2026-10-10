"""Gedeelde stukjes voor beide zone-methodes: het zone-formaat en de sterkte-score."""
import numpy as np
import pandas as pd

# Beide methodes leveren exact deze kolommen, zodat ze uitwisselbaar zijn.
ZONE_COLUMNS = ["low", "high", "mid", "timeframe", "touches",
                "first_touch", "last_touch", "strength", "method"]


def strength_score(touch_times: pd.Series, as_of: pd.Timestamp, half_life_days: float) -> float:
    """Sterkte = som van alle aanrakingen, elk gewogen naar hoe recent hij is.

    Een aanraking van vandaag telt als 1, een van een halfwaardetijd geleden als 0.5,
    van twee halfwaardetijden geleden als 0.25, enz. Zo combineert een getal
    'hoe vaak' en 'hoe recent'.
    """
    age_days = (as_of - pd.to_datetime(touch_times)).dt.total_seconds() / 86400
    return float(np.sum(0.5 ** (age_days.to_numpy() / half_life_days)))


def make_zone(low, high, touched: pd.DataFrame, timeframe, as_of, half_life_days, method) -> dict:
    return {
        "low": float(low),
        "high": float(high),
        "mid": float((low + high) / 2),
        "timeframe": timeframe,
        "touches": int(len(touched)),
        "first_touch": touched["time"].min(),
        "last_touch": touched["time"].max(),
        "strength": strength_score(touched["time"], as_of, half_life_days),
        "method": method,
    }


def zones_frame(records: list) -> pd.DataFrame:
    df = pd.DataFrame(records, columns=ZONE_COLUMNS)
    return df.sort_values("mid").reset_index(drop=True)
