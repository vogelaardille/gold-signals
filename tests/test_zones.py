import pandas as pd

from goldsignals.sr import top_zones, zones_as_of
from goldsignals.sr.common import ZONE_COLUMNS
from goldsignals.sr.merge import MERGED_COLUMNS
from goldsignals.viz.pine import export_pine

T = pd.Timestamp("2025-01-15 09:00", tz="UTC")


def test_both_methods_same_output_format(candles, cfg):
    for method in ("A", "B"):
        r = zones_as_of(candles, T, cfg, method)
        assert list(r.raw.columns) == ZONE_COLUMNS
        assert list(r.merged.columns) == MERGED_COLUMNS
        assert (r.raw["low"] < r.raw["high"]).all()
        assert (r.raw["touches"] >= cfg["zones"]["min_touches"]).all()


def test_cluster_zone_width_is_bounded(candles, cfg):
    r = zones_as_of(candles, T, cfg, "A")
    c = cfg["zones"]["cluster"]
    for tf, z in r.raw.groupby("timeframe"):
        max_width = (c["tolerance_atr"] + 2 * c["padding_atr"]) * r.atr[tf]
        assert ((z["high"] - z["low"]) <= max_width + 1e-9).all()


def test_kde_zones_do_not_overlap_within_timeframe(candles, cfg):
    r = zones_as_of(candles, T, cfg, "B")
    for _, z in r.raw.groupby("timeframe"):
        z = z.sort_values("low")
        assert (z["low"].iloc[1:].to_numpy() >= z["high"].iloc[:-1].to_numpy() - 1e-9).all()


def test_roles_relative_to_price(candles, cfg):
    r = zones_as_of(candles, T, cfg, "A")
    m = r.merged
    assert (m.loc[m["role"] == "support", "high"] < r.price).all()
    assert (m.loc[m["role"] == "resistance", "low"] > r.price).all()


def test_pine_export(candles, cfg, tmp_path):
    r = zones_as_of(candles, T, cfg, "A")
    zones = top_zones(r.merged, 5, 50)
    text = export_pine(zones, r.price, T, "A", cfg, tmp_path / "z.pine").read_text()
    assert text.startswith("//@version=6")
    assert "indicator(" in text and "box.new(" in text
    # Alle zone-arrays even lang
    for name in ("zLow", "zHigh", "zStart", "zTf", "zText", "zTransp"):
        line = next(l for l in text.splitlines() if l.startswith(f"var {name} "))
        assert line.count(",") == len(zones) - 1, name
