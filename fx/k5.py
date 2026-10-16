"""Ronde 5: besmet blok K5 (alle 6 paren, 2020-01 – 2026-10), ALLEEN beschrijvend (PLAN5 §9).

Draait pas als de research-status gecommit is en C5 voor elke candidate geopend is.
Verandert nooit iets aan de status.
Draaien: .venv/bin/python -m fx.k5
"""
import json
import subprocess

from fx import data
from fx.open_c5 import log as c5_log
from fx.run5 import OUT, Ctx, evaluate_primary, run_trial, trial_defs


def main():
    cfg = data.load_config()
    res_path = OUT / "results/results.json"
    dirty = subprocess.run(["git", "status", "--porcelain", str(res_path)], capture_output=True, text=True,
                           cwd=data.ROOT).stdout.strip()
    if not res_path.exists() or dirty:
        raise PermissionError("Commit eerst de research-uitkomsten van ronde 5 (PLAN5 §9).")
    res = json.loads(res_path.read_text())["primaries"]
    opened = {e["config"] for e in c5_log()}
    missing = [k for k, r in res.items() if r["status"] == "candidate" and k not in opened]
    if missing:
        raise PermissionError(f"Open eerst C5 voor de candidates {missing} (PLAN5 §9).")
    start, end = cfg["round5"]["k5"]
    pairs = {**cfg["round5"]["research_pairs"], **cfg["round5"]["confirm_pairs"]}
    C = Ctx(cfg, pairs, start, end, since="2019-10-01")  # 3 maanden terug voor σ van G2
    defs = trial_defs(cfg)
    out = {}
    for fam, r in res.items():
        trial = r["trial"]
        e = evaluate_primary(C, {trial: run_trial(C, *defs[trial])}, defs, trial)
        out[fam] = {"status_research": r["status"], "label": "BESMET, alleen beschrijvend", **e}
    (OUT / "results/k5_descriptive.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: {x: v[x] for x in ("trial", "n_trades", "net_bp", "gross_bp", "sharpe", "boot_pos",
                                            "net_by_pair")} for k, v in out.items()}, indent=1, default=float))


if __name__ == "__main__":
    main()
