"""Ronde 5: bevestigingsparen (AUD/USD, USD/CAD, USD/CHF) downloaden en ALLEEN de beschikbaarheid
controleren (PLAN5 §1): ontbrekende uren, tijdstempels, ask < bid. Geen spreads, geen rendementen.

Draaien: .venv/bin/python -m fx.data5
"""
import json

import pandas as pd

from fx import data

COLS = ["year", "candles", "missing_trading_hours", "missing_pct", "outside_session", "ask_below_bid"]


def main():
    cfg = data.load_config()
    p, r5 = cfg["periods"], cfg["round5"]
    end = pd.Timestamp(p["h4_end"], tz="UTC")
    research_end = pd.Timestamp(p["research_end"], tz="UTC")
    out = ["# Ronde 5 – beschikbaarheid bevestigingsparen (C5)", "",
           "Alleen beschikbaarheid en tijdstempels (PLAN5 §1). Geen spreads en geen rendementen bekeken.", ""]
    summary = {}
    for pair in r5["confirm_pairs"]:
        for side in ("bid", "ask"):
            data.download(cfg, pair, side, end, verbose=False)
        raw = data.load_pair(cfg, pair, until=research_end, clean=False)
        q = data.quality_by_year(raw, r5["confirm_pairs"][pair], with_spread=False)[COLS]
        ts = data.timestamp_check(raw[raw.index >= pd.Timestamp(p["research_start"], tz="UTC")])
        excluded = [int(y) for y in q.loc[(q["missing_pct"] > cfg["data"]["max_missing_pct"])
                                          & (q["year"] >= 2005), "year"]]
        summary[pair] = {"first": str(raw.index[0]), "timestamp_ok": ts["ok"], "peak_ny_hour": ts["peak_ny_hour"],
                         "excluded_years": excluded}
        out += [f"## {pair}", "", f"- eerste candle: {raw.index[0]}",
                f"- tijdstempelcontrole 2005–2019: piek in NY-uur {ts['peak_ny_hour']} → {'OK' if ts['ok'] else 'FOUT'}",
                f"- jaren (2005–2019) met > {cfg['data']['max_missing_pct']}% ontbrekende handelsuren: {excluded or 'geen'}",
                "", q.to_markdown(index=False), ""]
    res = data.ROOT / "research/round5"
    (res / "results").mkdir(parents=True, exist_ok=True)
    (res / "data_quality.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    (res / "results/data_quality.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
