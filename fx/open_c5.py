"""Ronde 5: bevestiging C5 (AUD/USD, USD/CAD, USD/CHF, 2005–2019) openen voor één candidate.
EENMALIG per primaire configuratie (PLAN5 §2 en §8).

Volgorde: status 'candidate' uit research/round5/results/results.json → opening loggen in
research/round5/holdout_log.json (vóór het laden van data) → exact dezelfde meting als in research.

Draaien: .venv/bin/python -m fx.open_c5 G1|G2
"""
import datetime as dt
import json
import sys

from fx import data
from fx.run5 import OUT, Ctx, evaluate_primary, run_trial, trial_defs

LOG = OUT / "holdout_log.json"


def log() -> list:
    return json.loads(LOG.read_text()) if LOG.exists() else []


def open_c5(config_id: str, status: str) -> None:
    if status != "candidate":
        raise PermissionError(f"{config_id} is '{status}': C5 mag alleen voor candidates open")
    if any(e["config"] == config_id for e in log()):
        raise PermissionError(f"C5 is al geopend voor {config_id}")
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(log() + [{"block": "C5", "config": config_id, "status_before": status,
                                        "opened_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}],
                              indent=1))


def main(config_id: str):
    cfg = data.load_config()
    res = json.loads((OUT / "results/results.json").read_text())["primaries"]
    r = res.get(config_id, {})
    open_c5(config_id, r.get("status"))
    p, s = cfg["periods"], cfg["stats"]
    C = Ctx(cfg, cfg["round5"]["confirm_pairs"], p["research_start"], p["research_end"], p["warmup_start"])
    defs = trial_defs(cfg)
    trial = r["trial"]
    out = evaluate_primary(C, {trial: run_trial(C, *defs[trial])}, defs, trial)
    checks = {
        "min_trades": out["n_trades"] >= s["min_trades"],
        "net_positive": out["net_bp"] > 0,
        "boot_pos_ge_80pct": out["boot_pos"] >= s["pct_positive"],
        "net_positive_2x_slippage": out["net_bp_by_slippage_multiplier"][2] > 0,
        "positive_2_of_3_pairs": sum(v > 0 for v in out["net_by_pair"].values()) >= 2,
        "above_null_p95": out["net_bp"] > out["null_p95"],
        "reality_check_research": r["reality_check_p"] < s["reality_check_p"],
    }
    out.update(config=config_id, block="C5", pairs=list(cfg["round5"]["confirm_pairs"]), checks=checks,
               status="validated" if all(checks.values()) else "candidate (C5 niet gehaald)")
    (OUT / f"results/holdout_C5_{config_id}.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    main(sys.argv[1])
