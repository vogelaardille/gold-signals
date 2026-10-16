"""Bewaker van H4 (2020-01 – 2026-10). PLAN4 §2 en §9.

H4 mag per primaire configuratie maar één keer geopend worden, en alleen als die
configuratie 'candidate' is. Elke opening wordt vastgelegd in
research/round4/holdout_log.json, vóórdat er data wordt geladen. Daarna mag er aan de
configuratie niets meer veranderen.
"""
import datetime as dt
import json

from fx.data import ROOT

LOG = ROOT / "research/round4/holdout_log.json"


def log() -> list:
    return json.loads(LOG.read_text()) if LOG.exists() else []


def times_opened(config_id: str) -> int:
    return sum(1 for e in log() if e["config"] == config_id)


def open_h4(config_id: str, status: str) -> None:
    """Registreer een opening. Weigert als de configuratie geen candidate is of H4 al open was."""
    if status != "candidate":
        raise PermissionError(f"{config_id} is '{status}': H4 mag alleen voor candidates open")
    if times_opened(config_id):
        raise PermissionError(f"H4 is al geopend voor {config_id}")
    entries = log() + [{"block": "H4", "config": config_id, "status_before": status,
                        "opened_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(entries, indent=1))
