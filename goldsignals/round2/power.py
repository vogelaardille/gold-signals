"""Toetskracht: hoeveel trades verwacht je in H2 / forward, en welk effect kun je dan aantonen?

Alleen research-data (2010-2018) van de variant F2 | 4h | squeeze 20 | target 2R wordt
gebruikt; hold-out H2 wordt NIET geladen.
- Verwacht aantal trades = trades per jaar in de research x lengte van het blok.
- Kleinste aantoonbare effect (MDE) bij eenzijdige toets, alfa 5%, power 80%:
  (z_0,95 + z_0,80) x sd / wortel(n). Ook via simulatie met de echte R-verdeling
  (verschoven naar het gewenste gemiddelde), want R is niet normaal verdeeld (-1 of ~+1,7).
- Stopregel (FORWARD.md): kans dat hij afgaat bij verschillende ware gemiddelden.
Draaien: .venv/bin/python -m goldsignals.round2.power
"""
import json

import numpy as np
import pandas as pd
from scipy.stats import norm

from goldsignals.config import load_config, project_path
from goldsignals.round2 import run
from goldsignals.round2.indicators import bars

VARIANT = {"family": "F2", "timeframe": "4h", "squeeze_pct": 20, "exit": "target_2R"}


def sim_power(r: np.ndarray, n: int, true_mean: float, rng, reps=20000, alpha=0.05) -> float:
    """Kans dat de ondergrens van een eenzijdig 95%-interval (t-benadering) boven 0 ligt."""
    x = rng.choice(r - r.mean() + true_mean, size=(reps, n))
    m, s = x.mean(1), x.std(1, ddof=1)
    return float((m - norm.ppf(1 - alpha) * s / np.sqrt(n) > 0).mean())


def stop_rule_prob(r, true_mean, rng, first=40, last=100, limit=-0.25, reps=20000) -> float:
    """Kans dat het lopende gemiddelde ergens tussen trade 40 en 100 onder -0,25 R zakt."""
    x = rng.choice(r - r.mean() + true_mean, size=(reps, last))
    run_mean = np.cumsum(x, 1) / np.arange(1, last + 1)
    return float((run_mean[:, first - 1:] < limit).any(1).mean())


def main():
    cfg = load_config()
    r2 = cfg["round2"]
    rng = np.random.default_rng(7)
    end = pd.Timestamp(r2["periods"]["holdout_start"], tz="UTC")
    run._init({"4h": bars("4h", end, cfg)})
    _, t = run.run_variant((VARIANT, cfg))
    w = r2["walkforward"]
    t = t[(t["year"] >= w["first_test_year"]) & (t["year"] <= w["last_test_year"])]
    r = t["r1x"].to_numpy()
    years = w["last_test_year"] - w["first_test_year"] + 1
    per_year = len(r) / years
    by_year = t.groupby("year").size()
    sd = float(r.std(ddof=1))
    h2_years = (pd.Timestamp(r2["periods"]["holdout_end"]) - pd.Timestamp(r2["periods"]["holdout_start"])).days / 365.25
    z = norm.ppf(0.95) + norm.ppf(0.80)
    out = {"research_trades": len(r), "trades_per_year": per_year, "trades_per_year_min": int(by_year.min()),
           "trades_per_year_max": int(by_year.max()), "sd_r": sd, "mean_r_research": float(r.mean()),
           "h2_years": h2_years}
    for name, n in (("h2", int(round(per_year * h2_years))), ("forward100", 100), ("stop40", 40)):
        se = sd / np.sqrt(n)
        out[name] = {"n": n, "se": se, "ci95_halfwidth": 1.96 * se, "mde_normal": z * se,
                     "power_at_research_mean": sim_power(r, n, r.mean(), rng),
                     "power_at_0.10": sim_power(r, n, 0.10, rng)}
        # MDE via simulatie: kleinste gemiddelde met >= 80% power (raster van 0,01 R)
        for m in np.arange(0.0, 1.5, 0.01):
            if sim_power(r, n, m, rng, reps=6000) >= 0.80:
                out[name]["mde_sim"] = float(m)
                break
    out["h2_n_range"] = [int(round(by_year.min() * h2_years)), int(round(by_year.max() * h2_years))]
    out["years_to_100"] = 100 / per_year
    out["stop_rule"] = {f"{m:+.2f}": stop_rule_prob(r, m, rng) for m in (0.22, 0.10, 0.0, -0.15, -0.30)}
    p = project_path("research/round2/results/power.json")
    p.write_text(json.dumps(run.clean(out), indent=1))
    print(json.dumps(run.clean(out), indent=1))


if __name__ == "__main__":
    main()
