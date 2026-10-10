"""Ronde 2, familie 5: de zone-toets (vraag 1 van ronde 1) op 15m-candles.

- Zones: snapshots per uur (methode A, via zones_as_of op de ronde-2-1h-data).
- Een 15m-candle j gebruikt de snapshot van het laatste uur dat gesloten was op de
  OPENINGSTIJD van j (dus zonder kennis van j zelf of van de rest van het lopende uur).
- Test, uitkomst, 1:2-setup en nulmodel: exact de functies van ronde 1
  (research/events.py), met ATR(14) van de 15m-candles.
Draaien: .venv/bin/python -m goldsignals.round2.zone15
"""
import json

import numpy as np
import pandas as pd

from goldsignals.config import load_config, project_path
from goldsignals.research.events import Arrays, detect_events, measure_outcomes, null_shifts, zone_setup
from goldsignals.research.stats import bootstrap_mean, vs_null, week_id
from goldsignals.round2 import data
from goldsignals.round2.run import clean
from goldsignals.round2.snapshots15 import SNAP_DIR
from goldsignals.sr.pivots import atr

MAX_DIST_ATR_1D = 8.0   # zones verder weg kunnen ook na een verschuiving (max 4 x daily ATR) niet geraakt worden


def snapshot_for_bars(snap_times: np.ndarray, bar_open: np.ndarray) -> np.ndarray:
    """Index (in snap_times, oplopend) van de laatste snapshot met as_of <= openingstijd van de bar.
    -1 = geen snapshot bekend."""
    return np.searchsorted(snap_times, bar_open, side="right") - 1


def build_zone_table(snap: pd.DataFrame, c15: pd.DataFrame, i_from: int, i_to: int) -> pd.DataFrame:
    """(15m-candle, zone)-rijen voor candles i_from..i_to (globale indexen in c15)."""
    snap = snap[snap["low"].notna()]
    t = snap["as_of"].to_numpy()
    change = np.flatnonzero(np.r_[True, t[1:] != t[:-1], True])
    starts, ends = change[:-1], change[1:]
    times = t[starts]
    opens = c15.index.to_numpy()[i_from:i_to + 1]
    k = snapshot_for_bars(times, opens)
    ok = k >= 0
    bars_i = np.arange(i_from, i_to + 1)[ok]
    k = k[ok]
    counts = ends[k] - starts[k]
    row_bar = np.repeat(bars_i, counts)
    row_snap = np.concatenate([np.arange(starts[kk], ends[kk]) for kk in k]) if len(k) else np.array([], int)
    z = snap.iloc[row_snap][["as_of", "low", "high", "atr_1d", "timeframe", "confluence", "touches",
                             "first_touch", "last_touch", "score"]].reset_index(drop=True)
    z.insert(0, "i", row_bar)
    return z


def main():
    cfg = load_config()
    r2, rcfg = cfg["round2"], cfg["research"]
    rng = np.random.default_rng(r2["seed"] + 5)
    end = pd.Timestamp(r2["periods"]["holdout_start"], tz="UTC")
    start = pd.Timestamp(r2["zone15"]["start"], tz="UTC")
    c15 = data.load("15m", until=end)
    a = Arrays.from_candles(c15)
    atr15 = atr(c15, cfg["features"]["atr_period"]).to_numpy()
    snap = pd.read_parquet(project_path(SNAP_DIR) / "zones_A.parquet")
    assert pd.Timestamp(snap["as_of"].max()) <= end, "snapshots lopen de hold-out in!"
    cost = rcfg_cost(cfg)
    need = max(rcfg["horizon_bars"], rcfg["setup_max_bars"]) + 1
    max_i = len(c15) - 1 - need

    # Per jaar een blok (geheugen); maanden vallen altijd binnen één blok (nulmodel per maand)
    years = range(start.year, end.year)
    chunks = []
    for y in years:
        idx = np.flatnonzero(c15.index.year == y)
        i0, i1 = max(int(idx[0]), 1), min(int(idx[-1]), max_i)
        zt = build_zone_table(snap, c15, i0, i1)
        prev_close = a.close[zt["i"].to_numpy() - 1]
        mid = (zt["low"] + zt["high"]).to_numpy() / 2
        zt = zt[np.abs(mid - prev_close) <= MAX_DIST_ATR_1D * zt["atr_1d"].to_numpy()].reset_index(drop=True)
        zt["atr_1h"] = atr15[zt["i"].to_numpy() - 1]      # ATR van de 15m-candle ervoor (kolomnaam uit ronde 1)
        chunks.append((y, zt))
        print(f"  {y}: {len(zt)} (candle, zone)-rijen", flush=True)

    def evaluate(shifts=None):
        parts = []
        for k, (y, zt) in enumerate(chunks):
            sh = None if shifts is None else shifts[k]
            ev = detect_events(zt, a, sh, max_i)
            ev = measure_outcomes(ev, a, rcfg)
            ev = zone_setup(ev, a, rcfg, cost)
            ev["year"] = y
            parts.append(ev)
        return pd.concat(parts, ignore_index=True)

    real = evaluate()
    real["week"] = week_id(real["time"])
    print(f"Echt: {len(real)} tests, bounce {real['bounce'].mean():.3f}, R {real['r'].mean():+.3f}", flush=True)
    null_b, null_r, null_year = [], [], []
    for rep in range(r2["zone15"]["null_replicates"]):
        shifts = [null_shifts(zt, rcfg, rng) for _, zt in chunks]
        ev = evaluate(shifts)
        null_b.append(ev["bounce"].mean())
        null_r.append(ev["r"].mean())
        null_year.append(ev.groupby("year")[["bounce", "r"]].mean())
        if (rep + 1) % 50 == 0:
            print(f"  nulmodel {rep + 1}", flush=True)
    nb = r2["bootstrap_n"]
    res = {"n_events": len(real), "n_setups": int(real["r"].notna().sum()),
           "bounce": bootstrap_mean(real["bounce"], real["week"], nb, rng),
           "r": bootstrap_mean(real["r"], real["week"], nb, rng),
           "r_gross": float(real["r_gross"].mean()),
           "bounce_null": vs_null(real["bounce"].mean(), null_b),
           "r_null": vs_null(real["r"].mean(), null_r)}
    ny = pd.concat(null_year).groupby(level=0).mean()
    ry = real.groupby("year")[["bounce", "r"]].mean()
    res["by_year"] = {int(y): {"bounce": float(ry.loc[y, "bounce"]), "bounce_null": float(ny.loc[y, "bounce"]),
                               "r": float(ry.loc[y, "r"]), "r_null": float(ny.loc[y, "r"]),
                               "n": int((real["year"] == y).sum())} for y in ry.index}
    years_b = np.mean([v["bounce"] > v["bounce_null"] for v in res["by_year"].values()])
    years_r = np.mean([v["r"] > v["r_null"] for v in res["by_year"].values()])
    res["share_years_better_bounce"], res["share_years_better_r"] = float(years_b), float(years_r)
    passes = ((res["bounce_null"]["pct"] > 95 and years_b >= 0.75) or (res["r_null"]["pct"] > 95 and years_r >= 0.75))
    res["decision"] = ("verschil gevonden: 15m-zonestrategie mag (alleen met akkoord)" if passes
                       else "geen verschil: geen 15m-zonestrategie bouwen")
    res["null_bounce_values"], res["null_r_values"] = null_b, null_r
    p = project_path("research/round2/results/zone15.json")
    p.write_text(json.dumps(clean(res), indent=1))
    print(json.dumps(clean({k: v for k, v in res.items() if not k.startswith("null_") and k != "by_year"}), indent=1))


def rcfg_cost(cfg):
    c = cfg["round2"]["costs"]
    return c["spread_usd"] + 2 * c["slippage_usd"]


if __name__ == "__main__":
    main()
