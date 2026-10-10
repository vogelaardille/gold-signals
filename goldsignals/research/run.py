"""Deel A: onderzoek draaien. Schrijft research/results/results.json en figuren.

Draaien:  .venv/bin/python -m goldsignals.research.run
Daarna:   .venv/bin/python -m goldsignals.research.report   (rapport md + html)
"""
import json
import time

import numpy as np
import pandas as pd

from goldsignals.config import load_config, project_path
from goldsignals.market import load_market, period_bounds
from goldsignals.research import analysis as an
from goldsignals.research import figures as fg
from goldsignals.research.stats import bootstrap_mean, vs_null


def clean(o):
    """JSON-veilig maken (numpy-getallen, NaN -> None)."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, pd.Timestamp):
        return o.isoformat()
    return o


def main():
    cfg = load_config()
    r = cfg["research"]
    out_dir = project_path(r["output_dir"]) / "results"
    fig_dir = project_path(r["output_dir"]) / "figures"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(r["seed"])
    nb = r["bootstrap_n"]
    t0 = time.time()

    # Alleen data t/m het einde van de research-periode laden: de hold-out bestaat hier niet.
    _, research_end = period_bounds(cfg, "research")
    market = load_market(cfg, methods=("A", "B"), build=False, until=research_end)
    res = {"meta": {"research_end": research_end, "candles": len(market.candles)}}

    ctx = an.Context(market, cfg, "A")
    real = ctx.events()
    res["meta"].update({"n_events": len(real), "n_setups": int(real["r"].notna().sum()),
                        "first_event": real["time"].min(), "last_event": real["time"].max(),
                        "cost_per_oz": ctx.cost})
    print(f"Methode A: {len(real)} events, {real['r'].notna().sum()} setups ({time.time() - t0:.0f}s)")

    # ---- Nulmodel: 50 replicaties met alle opsplitsingen, daarna 150 alleen totaal ----
    split_cols = an.SPLITS + ["year", "wf_window"]
    collect_q46 = lambda ev: {"q4": an.q4_summary(an.breakout_retest(ev, ctx)),   # noqa: E731
                              "q6": {f: float(ev.loc[ev[f], "r"].mean() - ev.loc[~ev[f], "r"].mean())
                                     for f in an.FILTERS},
                              "q5": {f"{y}|{s}": g for (y, s), g in
                                     ev.groupby(["year", "side_name"])["r"].mean().items()},
                              "q5_bounce": {f"{y}|{s}": g for (y, s), g in
                                            ev.groupby(["year", "side_name"])["bounce"].mean().items()},
                              "mfe": float(ev["mfe"].median()), "mae": float(ev["mae"].median()),
                              "brk": float(ev["brk"].mean())}
    nulls, extra = an.run_null(ctx, r["null_replicates_splits"], rng, split_cols, with_repeat=True,
                               collect=collect_q46)
    print(f"  nulmodel met opsplitsingen klaar ({time.time() - t0:.0f}s)")
    more, more_extra = an.run_null(ctx, r["null_replicates"] - r["null_replicates_splits"], rng,
                                   collect=lambda ev: {"brk": float(ev["brk"].mean())})
    null_all = nulls[None] + more[None]
    print(f"  nulmodel {len(null_all)} replicaties klaar ({time.time() - t0:.0f}s)")

    # ---- V1 ----
    q1 = an.compare(real, null_all, None, rng, nb)[0]
    q1["brk"] = float(real["brk"].mean())
    q1["brk_null"] = float(np.mean([e["brk"] for e in extra + more_extra]))
    q1["mfe_med"], q1["mae_med"] = float(real["mfe"].median()), float(real["mae"].median())
    q1["mfe_med_null"] = float(np.mean([e["mfe"] for e in extra]))
    q1["mae_med_null"] = float(np.mean([e["mae"] for e in extra]))
    q1["r_gross"] = float(real["r_gross"].mean())
    q1["outcomes"] = real["outcome"].value_counts(normalize=True).to_dict()
    q1["null_bounce_values"] = [g["_all"]["bounce"] for g in null_all]
    q1["null_r_values"] = [g["_all"]["r"] for g in null_all]
    q1["null_n_mean"] = float(np.mean([g["_all"]["n"] for g in null_all]))
    res["q1"] = q1

    # ---- V2 ----
    res["q2"] = {c: an.compare(real, nulls[c], c, rng, nb) for c in an.SPLITS}

    # ---- V3: methode B ----
    ctx_b = an.Context(market, cfg, "B")
    real_b = ctx_b.events(with_repeat=False)
    nb_null, _ = an.run_null(ctx_b, r["null_replicates"], rng, ("side_name",))
    res["q3"] = {"A": q1 | {"null_bounce_values": None, "null_r_values": None},
                 "B": an.compare(real_b, nb_null[None], None, rng, nb)[0],
                 "B_side": an.compare(real_b, nb_null["side_name"], "side_name", rng, nb),
                 "A_side": res["q2"]["side_name"]}
    print(f"  methode B klaar: {len(real_b)} events ({time.time() - t0:.0f}s)")

    # ---- V4: breakout en retest ----
    b = an.breakout_retest(real, ctx)
    q4 = an.q4_summary(b)
    for key in ("retest", "retest_held", "r_retest", "r_cont"):
        q4[f"{key}_ci"] = bootstrap_mean(b[key], an.week_id(b["time"]), nb, rng)
        q4[f"{key}_null"] = vs_null(q4[key], [e["q4"][key] for e in extra])
    res["q4"] = q4

    # ---- V5: stabiliteit ----
    risk_atr = real["risk_atr"].to_numpy() if "risk_atr" in real else np.array([1.0])
    rnd = an.random_entries(ctx, risk_atr, rng)
    q5 = {"by_year": [], "bh": an.buy_and_hold_per_year(ctx)}
    for (y, s), d in real.groupby(["year", "side_name"]):
        key = f"{y}|{s}"
        bm = bootstrap_mean(d["r"], d["week"], nb, rng)
        bb = bootstrap_mean(d["bounce"], d["week"], nb, rng)
        side = 1 if s == "support" else -1
        rr = rnd[(rnd["year"] == y) & (rnd["side"] == side)]
        q5["by_year"].append({
            "year": int(y), "side": s, "n": len(d), "n_r": int(d["r"].notna().sum()),
            "r": bm, "r_null": vs_null(bm["est"], [e["q5"].get(key, np.nan) for e in extra]),
            "bounce": bb, "bounce_null": vs_null(bb["est"], [e["q5_bounce"].get(key, np.nan) for e in extra]),
            "r_random": float(rr["r"].mean()) if len(rr) else None, "n_random": len(rr)})
    q5["random_total"] = {s: bootstrap_mean(g["r"], g["week"], nb, rng) for s, g in rnd.groupby("side")}
    q5["by_wf"] = an.compare(real[real["wf_window"] > 0], nulls["wf_window"], "wf_window", rng, nb)
    q5["by_year_all"] = an.compare(real, nulls["year"], "year", rng, nb)
    # Per regime en per kant alleen echte waarden (het nulmodel is hier niet opgesplitst)
    for split in ("vol_regime", "trend_rel"):
        q5[split] = {}
        for s, d in real.groupby("side_name"):
            q5[split][s] = {g: bootstrap_mean(dd["r"], dd["week"], nb, rng) for g, dd in d.groupby(split)}
    res["q5"] = q5

    # ---- V6: bevestiging ----
    q6 = {}
    for f, label in an.FILTERS.items():
        on, off = real[real[f]], real[~real[f]]
        diff = bootstrap_mean(on["r"], on["week"], nb, rng, extra=(off["r"], off["week"]))
        null_diffs = [e["q6"][f] for e in extra]
        q6[f] = {"label": label, "n_on": int(on["r"].notna().sum()), "n_off": int(off["r"].notna().sum()),
                 "r_on": bootstrap_mean(on["r"], on["week"], nb, rng),
                 "r_off": float(off["r"].mean()), "diff": diff,
                 "diff_null": vs_null(diff["est"], null_diffs),
                 "did": diff["est"] - float(np.nanmean(null_diffs)),
                 "did_lo": diff["lo"] - float(np.nanmean(null_diffs)),
                 "did_hi": diff["hi"] - float(np.nanmean(null_diffs))}
    res["q6"] = q6

    # ---- Voorbeeld-event voor de uitleg ----
    ex = real[(real["year"] == 2024) & (real["timeframe"] == "1d") & (real["side"] == 1)
              & (real["outcome"] == "bounce") & real["r"].notna()]
    ex_row = ex.sort_values("time").iloc[0] if len(ex) else real.iloc[0]
    res["example"] = {k: ex_row[k] for k in ("time", "zlow", "zhigh", "atr_1h", "timeframe", "confluence",
                                              "touches", "outcome", "r", "mfe", "mae", "side")}
    res["example"]["entry"] = float(ctx.a.open[int(ex_row["i"]) + 1])
    fg.example_chart(market, ex_row, cfg, fig_dir / "voorbeeld.png")

    # ---- Figuren ----
    fg.null_hist(res["q1"], fig_dir / "v1_nulmodel.png")
    fg.forest(res["q2"], an.SPLIT_LABEL, fig_dir / "v2_eigenschappen.png")
    fg.per_year(q5, fig_dir / "v5_per_jaar.png")
    fg.filters(q6, fig_dir / "v6_bevestiging.png")

    (out_dir / "results.json").write_text(json.dumps(clean(res), indent=1))
    print(f"Klaar in {time.time() - t0:.0f}s -> {out_dir / 'results.json'}")


if __name__ == "__main__":
    main()
