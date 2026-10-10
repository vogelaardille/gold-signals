"""DataProvider-interface.

Waarom een interface? Zo kan de databron later wisselen (bijv. een live-feed of
een broker-API) zonder dat de zone-detectie of de backtest hoeft te veranderen.
Elke provider levert hetzelfde formaat: 1h-candles.

Standaardformaat van het DataFrame:
- index: openingstijd van de candle, tz-aware in UTC, oplopend, uniek
- kolommen: open, high, low, close, volume (floats)
- alleen VOLLEDIG gesloten candles (geen lopende candle)
"""
from abc import ABC, abstractmethod

import pandas as pd

CANDLE_COLUMNS = ["open", "high", "low", "close", "volume"]


class DataDownloadError(RuntimeError):
    """Download van een databron mislukt. Er wordt dan bewust NIET teruggevallen
    op een andere bron, omdat koersniveaus per bron verschillen."""


class DataProvider(ABC):
    @abstractmethod
    def get_candles_1h(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """Geef 1h-candles tussen start en end (beide UTC)."""


def validate_candles(df: pd.DataFrame) -> pd.DataFrame:
    """Controleer en normaliseer het standaardformaat."""
    missing = [c for c in CANDLE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Kolommen ontbreken: {missing}")
    if df.index.tz is None:
        raise ValueError("Index moet tz-aware (UTC) zijn")
    df = df[CANDLE_COLUMNS].astype(float)
    df.index = df.index.tz_convert("UTC")
    df.index.name = "time"
    df = df[~df.index.duplicated(keep="last")].sort_index()
    return df


def get_provider(cfg: dict) -> DataProvider:
    """Kies de provider op basis van config.yaml (data.provider)."""
    name = cfg["data"]["provider"]
    if name == "dukascopy":
        from goldsignals.data.dukascopy import DukascopyProvider
        return DukascopyProvider.from_config(cfg)
    raise ValueError(f"Onbekende data-provider: {name}")
