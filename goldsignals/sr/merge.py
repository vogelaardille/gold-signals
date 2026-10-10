"""Zones van alle timeframes samenvoegen tot een lijst met confluence-score.

Overlappende zones (bijv. een daily en een 1h-zone op hetzelfde niveau) worden een
zone. Waarom? Een niveau dat op meerdere timeframes zichtbaar is, wordt door meer
traders gezien en is daardoor vaak belangrijker.

Scores in de output:
- confluence: som van de gewichten van de VERSCHILLENDE timeframes in de zone
  (daily 3 + 4h 2 = 5). Zegt: op hoeveel/welke timeframes zie je dit niveau?
- score: som over alle deelzones van (gewicht timeframe x sterkte). Combineert
  confluence, aantal aanrakingen en recency. Hierop sorteren we de 'top zones'.
"""
import pandas as pd

MERGED_COLUMNS = ["low", "high", "mid", "timeframe", "timeframes", "touches", "first_touch",
                  "last_touch", "strength", "confluence", "score", "role", "distance_pct", "method"]


def zone_role(low: float, high: float, price: float) -> str:
    """Support ligt onder de huidige prijs, resistance erboven."""
    if price > high:
        return "support"
    if price < low:
        return "resistance"
    return "in_zone"


def merge_zones(zones: pd.DataFrame, weights: dict, price: float) -> pd.DataFrame:
    """Voeg zones samen rond 'ankers'.

    Werkwijze: we lopen de zones af van hoogste timeframe naar laagste (en binnen een
    timeframe van sterk naar zwak). Overlapt een zone met een bestaand anker, dan
    wordt hij daaraan toegevoegd (bij meerdere: het anker met de grootste overlap).
    Zo niet, dan wordt hij zelf een nieuw anker.

    De grenzen van de samengevoegde zone zijn die van het anker. Waarom niet de
    vereniging van alle deelzones? Dan 'ketenen' overlappende 1h/4h-zones aan elkaar
    tot een zone van $100+ breed, en daar kun je niets mee.
    """
    if zones.empty:
        return pd.DataFrame(columns=MERGED_COLUMNS)

    z = zones.assign(_w=zones["timeframe"].map(weights))
    z = z.sort_values(["_w", "strength"], ascending=False).reset_index(drop=True)

    anchors = []   # lijst van (low, high)
    groups = []    # per anker: lijst van zone-indexen
    for i in range(len(z)):
        low, high = z.loc[i, "low"], z.loc[i, "high"]
        best, best_overlap = None, 0.0
        for a, (a_low, a_high) in enumerate(anchors):
            overlap = min(high, a_high) - max(low, a_low)
            if overlap > best_overlap:
                best, best_overlap = a, overlap
        if best is None:
            anchors.append((low, high))
            groups.append([i])
        else:
            groups[best].append(i)

    records = []
    for (low, high), members in zip(anchors, groups):
        g = z.loc[members]
        w = g["_w"]
        tfs = sorted(g["timeframe"].unique(), key=lambda tf: -weights[tf])
        mid = (low + high) / 2
        records.append({
            "low": low,
            "high": high,
            "mid": mid,
            "timeframe": tfs[0],                 # belangrijkste timeframe (bepaalt de kleur)
            "timeframes": "+".join(tfs),
            "touches": int(g["touches"].sum()),
            "first_touch": g["first_touch"].min(),
            "last_touch": g["last_touch"].max(),
            "strength": float(g["strength"].sum()),
            "confluence": int(sum(weights[tf] for tf in tfs)),
            "score": float((w * g["strength"]).sum()),
            "role": zone_role(low, high, price),
            "distance_pct": float((mid - price) / price * 100),
            "method": g["method"].iloc[0],
        })
    out = pd.DataFrame(records, columns=MERGED_COLUMNS)
    return out.sort_values("score", ascending=False).reset_index(drop=True)


def top_zones(merged: pd.DataFrame, n: int, max_distance_pct: float) -> pd.DataFrame:
    """De n sterkste zones binnen max_distance_pct van de huidige prijs."""
    near = merged[merged["distance_pct"].abs() <= max_distance_pct]
    return near.sort_values("score", ascending=False).head(n).reset_index(drop=True)
