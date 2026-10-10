"""Eén uurlijkse run: paper trading + meldingen + dashboard.

Lokaal:   .venv/bin/python -m goldsignals.paper.run --no-send     (geen Telegram)
          .venv/bin/python -m goldsignals.paper.run --force       (ook als de markt dicht is)
In GitHub Actions draait dit elk uur (zie .github/workflows/hourly.yml).
"""
import argparse
import os
import sys
import traceback

import pandas as pd

from goldsignals.config import load_config, project_path
from goldsignals.dashboard.build import build_site
from goldsignals.paper import runner
from goldsignals.paper.state import State


def set_output(name: str, value: str):
    """Geef een waarde door aan volgende stappen in GitHub Actions."""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{name}={value}\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="ook draaien als de markt dicht is")
    ap.add_argument("--no-send", action="store_true", help="geen Telegram-berichten versturen")
    ap.add_argument("--state-dir", default=None)
    ap.add_argument("--site", action="store_true", help="dashboard altijd opnieuw bouwen")
    args = ap.parse_args()
    cfg = load_config()
    state_dir = project_path(args.state_dir or cfg["paper"]["state_dir"])
    now = pd.Timestamp.now(tz="UTC")
    try:
        res = runner.run(cfg, state_dir, now=now, send=not args.no_send, force=args.force)
    except Exception as e:  # onverwachte fout: SYSTEEM-melding (max 1 per 6 uur) en netjes stoppen
        traceback.print_exc()
        state = State(state_dir)
        runner.queue_system(state, cfg, f"Run mislukt: {type(e).__name__}: {str(e)[:200]}", now)
        state.log_run(run_time=now, status="fout", message=f"{type(e).__name__}: {str(e)[:200]}")
        state.save()
        runner.deliver(state, cfg, not args.no_send)
        state.save()
        set_output("changed", "true")
        set_output("publish", "false")
        return 1
    print(f"Run {now:%Y-%m-%d %H:%M} UTC: {res['status']}")
    publish = res["changed"] or args.site or args.force
    if publish:
        out = build_site(cfg, state_dir)
        print(f"Dashboard gebouwd in {out.name}/")
    set_output("changed", "true" if res["changed"] else "false")
    set_output("publish", "true" if publish else "false")
    return 0


if __name__ == "__main__":
    sys.exit(main())
