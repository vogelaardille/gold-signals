"""Methode B: kernel density estimation (KDE).

Idee: leg over elke pivotprijs een klein 'bergje' (een normale verdeling met
breedte = bandbreedte) en tel ze op. Waar veel pivots dicht bij elkaar liggen
ontstaat een hoge piek: dat is een zone. De zone loopt van piek - b tot piek + b
(b = halfwidth_bw x bandbreedte), maar nooit voorbij het dal naar de volgende
piek, zodat zones van dezelfde timeframe niet overlappen.

Verschil met methode A: KDE kijkt naar de 'massa' van pivots en is minder
gevoelig voor de volgorde/grenzen van het clusteren, maar heeft een extra
parameter (de bandbreedte).
"""
import numpy as np
import pandas as pd
from scipy.signal import find_peaks
from scipy.stats import gaussian_kde

from goldsignals.sr.common import make_zone, zones_frame

MAX_GRID_POINTS = 50_000


def detect_zones_kde(pivots: pd.DataFrame, atr_value: float, as_of: pd.Timestamp,
                     timeframe: str, zcfg: dict) -> pd.DataFrame:
    kcfg = zcfg["kde"]
    half_life = zcfg["half_life_days"][timeframe]
    min_touches = zcfg["min_touches"]
    records = []

    prices = pivots["price"].to_numpy(dtype=float)
    if len(prices) < 2 or prices.std(ddof=1) == 0:
        return zones_frame(records)

    bandwidth = kcfg["bandwidth_atr"] * atr_value
    # scipy wil de bandbreedte als factor t.o.v. de standaarddeviatie van de data
    kde = gaussian_kde(prices, bw_method=bandwidth / prices.std(ddof=1))

    step = max(kcfg["grid_step_atr"] * atr_value,
               (prices.max() - prices.min() + 6 * bandwidth) / MAX_GRID_POINTS)
    grid = np.arange(prices.min() - 3 * bandwidth, prices.max() + 3 * bandwidth, step)
    density = kde(grid)

    peaks, _ = find_peaks(density, prominence=kcfg["min_prominence"] * density.max())
    if len(peaks) == 0:
        return zones_frame(records)

    # Dalen tussen opeenvolgende pieken = harde grens tussen zones
    valleys = [p1 + int(np.argmin(density[p1:p2 + 1])) for p1, p2 in zip(peaks[:-1], peaks[1:])]
    half_width = kcfg["halfwidth_bw"] * bandwidth

    for k, peak in enumerate(peaks):
        mid = grid[peak]
        low, high = mid - half_width, mid + half_width
        if k > 0:
            low = max(low, grid[valleys[k - 1]])
        if k < len(peaks) - 1:
            high = min(high, grid[valleys[k]])
        touched = pivots[(pivots["price"] >= low) & (pivots["price"] <= high)]
        if len(touched) < min_touches:
            continue
        records.append(make_zone(low, high, touched, timeframe, as_of, half_life, "B"))
    return zones_frame(records)
