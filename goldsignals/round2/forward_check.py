"""Controle vóór de forward-test (alleen research-data 2010-2018, H2 niet geladen):
1. Geeft de live-plugin VolSqueeze4h exact dezelfde signalen als de onderzoekscode (F2)?
2. Wat is het effect van exits per 1h-candle (live-motor) i.p.v. per 4h-candle (onderzoek)?
Draaien: .venv/bin/python -m goldsignals.round2.forward_check
"""
import json

import numpy as np
import pandas as pd

from goldsignals.backtest.engine import run_backtest
from goldsignals.backtest.walkforward import index_range
from goldsignals.config import load_config, project_path
from goldsignals.features import compute_features
from goldsignals.market import Market
from goldsignals.round2 import data, run
from goldsignals.round2.indicators import bars
from goldsignals.strategies.base import MarketView
from goldsignals.strategies.vol_squeeze_4h import VolSqueeze4h

VARIANT = {"family": "F2", "timeframe": "4h", "squeeze_pct": 20, "exit": "target_2R"}


def main():
    cfg = load_config()
    r2 = cfg["round2"]
    end = pd.Timestamp(r2["periods"]["holdout_start"], tz="UTC")
    c1 = data.load("1h", until=end)
    m = Market(c1, compute_features(c1, cfg))
    t0, t1 = pd.Timestamp("2010-01-01", tz="UTC"), pd.Timestamp("2019-01-01", tz="UTC")
    i0, i1 = index_range(m, t0, t1)

    # 1. Signalen vergelijken
    strat = VolSqueeze4h()
    plugin = {}
    for i in range(i0, i1 + 1):
        for s in strat.generate_signals(MarketView(m, i)):
            plugin[s.time] = (s.direction, round(s.meta["stop_dist"], 9))
    b4 = bars("4h", end, cfg)
    from goldsignals.round2 import families as fam
    s = fam.signals(b4, VARIANT, cfg)
    ct = b4["close_time"].to_numpy()
    research = {pd.Timestamp(ct[k]): (int(s.entry[k]), round(float(s.stop_dist[k]), 9))
                for k in np.flatnonzero(s.entry) if t0 < pd.Timestamp(ct[k]) <= t1}
    same = sum(1 for k, v in research.items() if plugin.get(k) == v)
    only_r = [str(k) for k in research if k not in plugin]
    only_p = [str(k) for k in plugin if k not in research]
    diff_val = [str(k) for k in research if k in plugin and plugin[k] != research[k]]
    print(f"signalen: onderzoek {len(research)}, plugin {len(plugin)}, identiek {same}, "
          f"alleen onderzoek {len(only_r)}, alleen plugin {len(only_p)}, andere waarde {len(diff_val)}")

    # 2. Resultaat met exits per 1h (live-motor) vs per 4h (onderzoek)
    live = run_backtest(VolSqueeze4h(), m, i0, i1, cfg).trades
    run._init({"4h": b4})
    _, rt = run.run_variant((VARIANT, cfg))
    rt = rt[(rt["year"] >= 2010) & (rt["year"] <= 2018)]
    out = {"signals_research": len(research), "signals_plugin": len(plugin), "identical": same,
           "only_research": only_r[:20], "only_plugin": only_p[:20], "different_value": diff_val[:20],
           "live_engine_1h_exits": {"n": len(live), "avg_r": float(live["r"].mean()),
                                    "results": live["result"].value_counts().to_dict()},
           "research_4h_exits": {"n": len(rt), "avg_r": float(rt["r1x"].mean()),
                                 "results": rt["result"].value_counts().to_dict()}}
    print(json.dumps(out, indent=1, default=str))
    project_path("research/round2/results/forward_check.json").write_text(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
