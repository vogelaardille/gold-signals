"""Synthetische testdata: zo draaien de tests offline en voorspelbaar.

We maken een random walk met 1h-candles die de echte goud-handelstijden volgen:
zondag 18:00 t/m vrijdag 17:00 New York-tijd, met elke dag een pauze van 17:00-18:00.
Een golfbeweging erin zorgt ervoor dat prijzen op dezelfde niveaus terugkomen,
zodat er echt zones ontstaan.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from goldsignals.config import load_config  # noqa: E402


def make_candles(start="2024-01-01", days=420, seed=0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    local = pd.date_range(start, periods=days * 24, freq="h", tz="America/New_York")
    wd, hr = local.weekday, local.hour
    closed = (hr == 17) | (wd == 5) | ((wd == 4) & (hr >= 17)) | ((wd == 6) & (hr < 18))
    idx = local[~closed].tz_convert("UTC")

    n = len(idx)
    t = np.arange(n)
    trend = 2000 + 60 * np.sin(t / 300) + np.cumsum(rng.normal(0, 1.5, n))
    close = trend + rng.normal(0, 2, n)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.exponential(2, n)
    low = np.minimum(open_, close) - rng.exponential(2, n)
    df = pd.DataFrame({"open": open_, "high": high, "low": low, "close": close,
                       "volume": rng.uniform(1, 5, n)}, index=idx)
    df.index.name = "time"
    return df


@pytest.fixture(scope="session")
def cfg():
    return load_config()


@pytest.fixture(scope="session")
def candles():
    return make_candles()
