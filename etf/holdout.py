"""Bewaker van H3 (2021-01 – 2026-09) en P (1996–2004, fondsen als proxy). PLAN3 §2 en §9.

Een blok mag per eindconfiguratie maar één keer geopend worden, en alleen als die
configuratie 'candidate' is. Elke opening wordt vastgelegd in
research/round3/holdout_log.json, vóórdat er data wordt geladen. Daarna mag er aan de
configuratie niets meer veranderen.
"""
import datetime as dt
import json

from etf.data import ROOT

LOG = ROOT / "research/round3/holdout_log.json"


def log() -> list:
    return json.loads(LOG.read_text()) if LOG.exists() else []


def times_opened(block: str, config_id: str) -> int:
    return sum(1 for e in log() if e["block"] == block and e["config"] == config_id)


def open_block(block: str, config_id: str, status: str) -> None:
    """Registreer een opening. Weigert als de configuratie geen candidate is of het blok al open was."""
    if block not in ("H3", "P"):
        raise ValueError("blok moet H3 of P zijn")
    if status != "candidate":
        raise PermissionError(f"{config_id} is '{status}': {block} mag alleen voor candidates open")
    if times_opened(block, config_id):
        raise PermissionError(f"{block} is al geopend voor {config_id}")
    entries = log() + [{"block": block, "config": config_id, "status_before": status,
                        "opened_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}]
    LOG.write_text(json.dumps(entries, indent=1))
