"""Bewaker van de hold-out: per strategie maximaal één keer openen.

Elke opening wordt vastgelegd in research/holdout_log.json (in git), met een
'vingerafdruk' van de strategie (broncode + parameters). Vraag je de hold-out opnieuw
op voor dezelfde vingerafdruk, dan krijg je het opgeslagen resultaat terug (er wordt
niet opnieuw gekeken). Is de strategie veranderd na het openen, dan is de hold-out
voor die strategie 'verbrand': hij telt niet meer als bevestiging.
"""
import hashlib
import inspect
import json
from datetime import datetime, timezone

from goldsignals.config import project_path

LOG_PATH = project_path("research/holdout_log.json")


def fingerprint(strategy) -> str:
    src = inspect.getsource(type(strategy))
    payload = src + json.dumps(strategy.params, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _load() -> dict:
    return json.loads(LOG_PATH.read_text()) if LOG_PATH.exists() else {}


def _save(log: dict) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2, sort_keys=True, default=str))


def status(strategy_id: str, strategy) -> dict:
    """Wat weten we over de hold-out van deze strategie, zonder hem te openen?"""
    entry = _load().get(strategy_id)
    if entry is None:
        return None
    burned = entry["fingerprint"] != fingerprint(strategy)
    return {**entry["result"], "burned": burned, "opened_at": entry["opened_at"]}


def open_once(strategy_id: str, strategy, run_fn) -> dict:
    """Open de hold-out voor deze strategie. run_fn() voert de hold-out-backtest uit en
    geeft een dict met minstens n en avg_r. Wordt maximaal één keer uitgevoerd."""
    log = _load()
    fp = fingerprint(strategy)
    if strategy_id in log:
        entry = log[strategy_id]
        return {**entry["result"], "burned": entry["fingerprint"] != fp, "opened_at": entry["opened_at"]}
    result = run_fn()
    log[strategy_id] = {"fingerprint": fp, "params": strategy.params,
                        "opened_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        "result": result}
    _save(log)
    return {**result, "burned": False, "opened_at": log[strategy_id]["opened_at"]}
