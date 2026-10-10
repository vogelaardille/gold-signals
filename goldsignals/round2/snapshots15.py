"""Ronde 2, familie 5: zone-snapshots per uur op de lange historie (alleen research R2).

Zelfde functie als ronde 1 (zones_as_of via build_snapshots), andere data en map.
Data na het begin van H2 wordt niet eens geladen.
Draaien: .venv/bin/python -m goldsignals.round2.snapshots15
"""
import copy

import pandas as pd

from goldsignals.config import load_config
from goldsignals.round2 import data
from goldsignals.snapshots import build_snapshots

SNAP_DIR = "data/snapshots/round2"


def r2_cfg(cfg):
    c = copy.deepcopy(cfg)
    c["snapshots"]["dir"] = SNAP_DIR
    return c


def main():
    cfg = load_config()
    end = pd.Timestamp(cfg["round2"]["periods"]["holdout_start"], tz="UTC")
    candles = data.load("1h", until=end)
    start = pd.Timestamp(cfg["round2"]["zone15"]["start"], tz="UTC") - pd.Timedelta(days=3)
    snap = build_snapshots(candles, r2_cfg(cfg), "A", start)
    print("klaar", len(snap), snap["as_of"].min(), snap["as_of"].max())


if __name__ == "__main__":
    main()
