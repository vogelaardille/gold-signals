"""H4 openen voor één candidate (PLAN4 §2 en §9). EENMALIG per primaire configuratie.

Volgorde:
1. status uit research/round4/results/results.json moet 'candidate' zijn;
2. de opening wordt gelogd (fx/holdout.py), vóórdat er data geladen wordt;
3. exact dezelfde regel en meting als in research.

Alleen F1 is uitgewerkt: F2 en F3 hadden in research geen candidate.
Draaien: .venv/bin/python -m fx.open_holdout F1-EU
Uitvoer: research/round4/results/holdout_H4_<config>.json
"""
import json
import sys

import pandas as pd

from fx import data, engine, families, holdout, stats
from fx.run import OUT


def main(config_id: str):
    cfg = data.load_config()
    res = json.loads((OUT / "results/results.json").read_text())["primaries"]
    status = res.get(config_id, {}).get("status")
    holdout.open_h4(config_id, status)  # weigert als geen candidate of al geopend
    trial = res[config_id]["trial"]
    fam, pair, combo = trial.split("|")
    if fam != "F1":
        raise NotImplementedError("alleen F1 heeft een candidate")
    p, ex, s = cfg["periods"], cfg["execution"], cfg["stats"]
    start, end = pd.Timestamp(p["h4_start"], tz="UTC"), pd.Timestamp(p["h4_end"], tz="UTC")
    px = engine.prices(data.load_pair(cfg, pair, until=end, since=start))
    legs = cfg["f1"]["combos"][combo]

    def run(slip):
        parts = [families.f1_leg(px, pair, cfg["f1"]["legs"][leg], cfg["pairs"][pair], slip).assign(leg=leg)
                 for leg in legs]
        return pd.concat(parts, ignore_index=True)

    tr = run(ex["slippage_pips"])
    days = stats.research_days(p["h4_start"], p["h4_end"])
    idx = stats.bootstrap_index(len(days), s["bootstrap_n"], s["block_days"], s["seed"])
    sm = stats.summarize(tr, days, idx)
    net2 = float(run(2 * ex["slippage_pips"])["net_bp"].mean())
    retail = float(run(ex["slippage_pips"] + ex["retail_extra_pips"])["net_bp"].mean())
    checks = {"min_trades": sm["n_trades"] >= s["min_trades"], "net_positive": sm["net_bp"] > 0,
              "net_positive_2x_slippage": net2 > 0,
              "reality_check_research": res[config_id]["reality_check_p"] < s["reality_check_p"]}
    out = {"config": config_id, "trial": trial, "block": "H4", "period": [p["h4_start"], p["h4_end"]],
           **sm, "net_bp_2x_slippage": net2, "net_bp_retail": retail,
           "by_leg_net_bp": tr.groupby("leg")["net_bp"].mean().to_dict(),
           "by_leg_gross_bp": tr.groupby("leg")["gross_bp"].mean().to_dict(),
           "checks": checks, "status": "validated" if all(checks.values()) else "candidate (H4 niet gehaald)"}
    (OUT / f"results/holdout_H4_{config_id}.json").write_text(json.dumps(out, indent=1, default=float))
    tr.to_csv(OUT / f"results/trades_H4_{config_id}.csv", index=False)
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1])
