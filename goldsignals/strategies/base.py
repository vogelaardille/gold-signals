"""Plugin-interface voor strategieën.

Een strategie is een klasse met een methode `generate_signals(view)`. De `view` bevat
ALLEEN wat op het sluitmoment van de laatste 1h-candle bekend was: candles en
indicatoren t/m die candle, en de zones zoals zones_as_of ze op dat moment gaf.
Daardoor kan een strategie per constructie niet in de toekomst kijken, en draait
precies dezelfde code in de backtest en in paper trading.

Nieuwe strategie toevoegen: zie README ("Een strategie toevoegen").
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Signal:
    strategy: str
    time: pd.Timestamp        # sluitmoment van de candle waarop het signaal ontstond
    direction: int            # +1 long, -1 short
    stop: float
    target: float
    reason: str               # korte uitleg in gewone taal (voor de melding)
    min_rr: float = 0.0       # minimale R:R; wordt bij de echte entry opnieuw gecontroleerd
    max_hold_bars: int = None  # optioneel: na zoveel candles sluiten op de slotkoers
    zone: dict = None         # de zone waarop het signaal is gebaseerd (voor de chart)
    meta: dict = field(default_factory=dict)


class MarketView:
    """Wat een strategie op tijd t mag zien. Slicen gebeurt pas als het nodig is."""

    def __init__(self, market, i: int):
        self._m, self.i = market, i
        self.t = market.close_time[i]

    @property
    def bar(self):
        """De laatste gesloten candle (open/high/low/close)."""
        return self._m.candles.iloc[self.i]

    @property
    def feat(self):
        """Indicatoren op de laatste candle (atr, rsi, ema_fast, ema_slow, d_trend, ...)."""
        return self._m.features.iloc[self.i]

    def candles(self, n: int = None) -> pd.DataFrame:
        """De laatste n candles (of alle) t/m de huidige."""
        start = 0 if n is None else max(0, self.i + 1 - n)
        return self._m.candles.iloc[start:self.i + 1]

    def features(self, n: int = None) -> pd.DataFrame:
        start = 0 if n is None else max(0, self.i + 1 - n)
        return self._m.features.iloc[start:self.i + 1]

    def zones(self, method: str = "A") -> pd.DataFrame:
        """Samengevoegde zones op tijd t (zones_as_of via de snapshot)."""
        return self._m.zones_at(method, self.i)

    def array(self, name: str, n: int) -> np.ndarray:
        """Snelle toegang: de laatste n waarden van een candle- of indicatorkolom."""
        return self._m.array(name)[max(0, self.i + 1 - n):self.i + 1]


class Strategy:
    """Basisklasse. Subklassen zetten `name`, `description` en implementeren generate_signals."""
    name = "base"
    description = ""
    zone_method = None        # "A"/"B" als de strategie zones nodig heeft, anders None

    def __init__(self, params: dict = None):
        self.params = dict(params or {})

    def generate_signals(self, view: MarketView) -> list:
        raise NotImplementedError

    def label(self) -> str:
        return self.name
