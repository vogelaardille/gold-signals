"""Fase 1: data ophalen, zones detecten (methode A en B), charts en Pine-export.

Draaien met:  python -m goldsignals.phase1
"""
import sys

import pandas as pd

from goldsignals.config import load_config, project_path
from goldsignals.data import DataDownloadError, build_timeframes, get_provider
from goldsignals.sr import top_zones, zones_as_of
from goldsignals.viz import export_pine, plot_zones


def date_range(cfg: dict):
    d = cfg["data"]
    end = pd.Timestamp(d["end_date"], tz="UTC") if d.get("end_date") else pd.Timestamp.now(tz="UTC")
    if d.get("start_date"):
        start = pd.Timestamp(d["start_date"], tz="UTC")
    else:
        start = end - pd.DateOffset(years=d["years"])
    return start, end


def main() -> int:
    cfg = load_config()
    out_dir = project_path(cfg["output"]["dir"])
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Data
    start, end = date_range(cfg)
    print(f"Data ophalen ({cfg['data']['provider']}) ...")
    try:
        candles_1h = get_provider(cfg).get_candles_1h(start, end)
    except DataDownloadError as e:
        print(f"\nFOUT: {e}", file=sys.stderr)
        return 1

    # 'Nu' = sluitmoment van de laatste gesloten 1h-candle
    as_of = candles_1h.index[-1] + pd.Timedelta(hours=1)
    frames = build_timeframes(candles_1h, cfg, as_of)

    # 2. Zones per methode, charts en CSV's
    results = {}
    for method in ("A", "B"):
        r = zones_as_of(candles_1h, as_of, cfg, method)
        results[method] = r
        r.merged.to_csv(out_dir / f"zones_{method}.csv", index=False, float_format="%.3f")
        r.raw.to_csv(out_dir / f"zones_{method}_per_timeframe.csv", index=False, float_format="%.3f")
        plot_zones(frames[cfg["output"]["chart_timeframe"]], r.merged, r.price, method, cfg,
                   out_dir / f"chart_zones_{method}.html")

    # 3. Pine Script
    pm = cfg["output"]["pine_method"]
    pine_zones = top_zones(results[pm].merged, cfg["output"]["pine_top_n"], cfg["output"]["max_distance_pct"])
    pine_path = export_pine(pine_zones, results[pm].price, as_of, pm, cfg, out_dir / "tradingview_zones.pine")

    # 4. Samenvatting
    print("\n=== Samenvatting fase 1 ===")
    print(f"Periode: {candles_1h.index[0]:%Y-%m-%d %H:%M} -> {as_of:%Y-%m-%d %H:%M} UTC")
    print(f"Laatste prijs: {results['A'].price:.2f}")
    print("Gesloten candles per timeframe:")
    for tf, f in frames.items():
        print(f"  {tf:>3}: {len(f):>6}")
    for method, r in results.items():
        per_tf = r.raw.groupby("timeframe").size().to_dict()
        per_tf_txt = ", ".join(f"{tf} {per_tf.get(tf, 0)}" for tf in cfg["timeframes"])
        print(f"\nMethode {method}: {len(r.raw)} zones per timeframe ({per_tf_txt}) "
              f"-> {len(r.merged)} na samenvoegen")
        top = top_zones(r.merged, 5, cfg["output"]["max_distance_pct"])
        print(f"  Top 5 (binnen {cfg['output']['max_distance_pct']}% van de prijs):")
        for i, z in enumerate(top.itertuples(), 1):
            print(f"  {i}. {z.low:8.2f} - {z.high:8.2f}  {z.role:<10}  {z.timeframes:<9}  "
                  f"aanrakingen {z.touches:>3}  score {z.score:6.2f}  ({z.distance_pct:+.1f}%)")

    print("\nBestanden in output/:")
    for p in sorted(out_dir.iterdir()):
        print(f"  {p.name}")
    print(f"\nPine Script (methode {pm}, top {len(pine_zones)}): {pine_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
