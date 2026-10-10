"""Methode A: pivot-clustering.

Idee: als prijs meerdere keren op (bijna) hetzelfde niveau omdraait, is dat een
zone. We sorteren alle pivots op prijs en lopen ze van laag naar hoog af. Een
pivot hoort bij de huidige cluster zolang hij binnen k x ATR van de LAAGSTE pivot
van die cluster ligt. Daardoor is een zone nooit breder dan k x ATR (plus padding);
zonder die grens kan een lange ketting van pivots een gigantische zone worden.
"""
import pandas as pd

from goldsignals.sr.common import make_zone, zones_frame


def detect_zones_cluster(pivots: pd.DataFrame, atr_value: float, as_of: pd.Timestamp,
                         timeframe: str, zcfg: dict) -> pd.DataFrame:
    tolerance = zcfg["cluster"]["tolerance_atr"] * atr_value
    padding = zcfg["cluster"]["padding_atr"] * atr_value
    half_life = zcfg["half_life_days"][timeframe]
    min_touches = zcfg["min_touches"]

    records = []
    if len(pivots) == 0:
        return zones_frame(records)

    p = pivots.sort_values("price").reset_index(drop=True)
    clusters, current = [], [0]
    for i in range(1, len(p)):
        if p.loc[i, "price"] - p.loc[current[0], "price"] <= tolerance:
            current.append(i)
        else:
            clusters.append(current)
            current = [i]
    clusters.append(current)

    for members in clusters:
        if len(members) < min_touches:
            continue
        touched = p.loc[members]
        records.append(make_zone(touched["price"].min() - padding, touched["price"].max() + padding,
                                 touched, timeframe, as_of, half_life, "A"))
    return zones_frame(records)
