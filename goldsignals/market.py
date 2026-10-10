"""Alles wat onderzoek, backtest en paper trading over de markt nodig hebben, op een plek.

- candles: 1h-candles (UTC, index = openingstijd)
- features: indicatoren per candle (zie features.py)
- zones: per methode de snapshots, met snel opzoeken via `zones_at(method, i)`

Periodes (research / hold-out) staan in config.yaml. `period_mask` geeft per candle
aan of hij in een periode valt. De hold-out wordt alleen via backtest/holdout.py geopend.
"""
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from goldsignals.data import get_provider
from goldsignals.data.timeframes import TF_DURATION
from goldsignals.features import compute_features
from goldsignals.snapshots import build_snapshots, load_snapshots


def period_bounds(cfg: dict, name: str):
    p = cfg["periods"]
    ts = lambda s: pd.Timestamp(s, tz="UTC") if s else None  # noqa: E731
    bounds = {
        "warmup": (ts(p["warmup_start"]), ts(p["research_start"])),
        "research": (ts(p["research_start"]), ts(p["holdout_start"])),
        "holdout": (ts(p["holdout_start"]), ts(p["holdout_end"])),
        "forward": (ts(p["holdout_end"]), None),
    }
    return bounds[name]


@dataclass
class Market:
    candles: pd.DataFrame
    features: pd.DataFrame
    snapshots: dict = field(default_factory=dict)   # method -> DataFrame (lang formaat)
    _offsets: dict = field(default_factory=dict)    # method -> {as_of: (start, end)}

    def __post_init__(self):
        self.close_time = self.candles.index + TF_DURATION["1h"]
        for method, snap in self.snapshots.items():
            self._index_snapshots(method, snap)

    def _index_snapshots(self, method, snap):
        # Per as_of de eerste en laatste rij; snapshots zijn gesorteerd op as_of.
        t = snap["as_of"].to_numpy()
        change = np.flatnonzero(np.r_[True, t[1:] != t[:-1], True])
        starts, ends = change[:-1], change[1:]
        self._offsets[method] = dict(zip(pd.DatetimeIndex(t[starts]), zip(starts, ends)))

    def zones_at_time(self, method: str, as_of: pd.Timestamp) -> pd.DataFrame:
        """Zones zoals ze op as_of bekend waren (uit de snapshot)."""
        start, end = self._offsets[method][as_of]
        z = self.snapshots[method].iloc[start:end]
        return z[z["low"].notna()]

    def zones_at(self, method: str, i: int) -> pd.DataFrame:
        """Zones op het sluitmoment van candle i."""
        return self.zones_at_time(method, self.close_time[i])

    def array(self, name: str) -> np.ndarray:
        """Kolom van candles of features als numpy-array (gecachet, voor snelheid)."""
        cache = self.__dict__.setdefault("_arrays", {})
        if name not in cache:
            src = self.candles if name in self.candles.columns else self.features
            cache[name] = src[name].to_numpy()
        return cache[name]

    def index_of_close(self, t: pd.Timestamp) -> int:
        """Index van de candle die op t sloot."""
        return int(self.close_time.get_loc(t))

    def period_mask(self, cfg: dict, name: str) -> np.ndarray:
        """True voor candles waarvan het SLUITmoment in de periode valt."""
        start, end = period_bounds(cfg, name)
        m = self.close_time > start
        if end is not None:
            m &= self.close_time <= end
        return np.asarray(m)


def load_candles(cfg: dict, update: bool = False) -> pd.DataFrame:
    """1h-candles vanaf warmup_start. Met update=False alleen uit de cache (geen netwerk)."""
    provider = get_provider(cfg)
    start = pd.Timestamp(cfg["periods"]["warmup_start"], tz="UTC")
    if update:
        return provider.get_candles_1h(start, pd.Timestamp.now(tz="UTC"))
    df, covered = provider._load_cache()
    if df is None:
        raise FileNotFoundError("Geen data-cache; draai eerst met update=True")
    return df[df.index >= start]


def load_market(cfg: dict, methods=("A",), update_data: bool = False,
                build: bool = True, until: pd.Timestamp = None) -> Market:
    """Laad candles, features en snapshots. Met build=True worden ontbrekende
    snapshots eerst berekend. until: candles na dit moment weglaten."""
    candles = load_candles(cfg, update_data)
    if until is not None:
        candles = candles[candles.index + TF_DURATION["1h"] <= until]
    feats = compute_features(candles, cfg)
    snaps = {}
    for m in methods:
        start = pd.Timestamp(cfg["periods"]["research_start"], tz="UTC") - pd.Timedelta(days=7)
        snaps[m] = build_snapshots(candles, cfg, m, start) if build else load_snapshots(cfg, m)
        if until is not None:
            snaps[m] = snaps[m][snaps[m]["as_of"] <= until].reset_index(drop=True)
    return Market(candles, feats, snaps)
