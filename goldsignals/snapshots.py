"""Zone-snapshots: de zones zoals ze op elk uur bekend waren, opgeslagen op schijf.

Waarom? zones_as_of kost ~0.1 s. Het onderzoek en de backtest hebben de zones voor
~35.000 uren nodig, en dat steeds opnieuw. Daarom berekenen we ze een keer (parallel),
via precies dezelfde functie zones_as_of, en slaan ze op. Er komt dus geen andere
zone-logica bij: een snapshot op tijd t = zones_as_of(candles, t).

Formaat: een lang DataFrame met per rij een samengevoegde zone, plus kolommen
as_of (sluitmoment van het uur), price, atr_1h, atr_4h, atr_1d.
"""
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd

from goldsignals.config import project_path
from goldsignals.sr import zones_as_of

_WORKER = {}


def _init_worker(candles, cfg, method):
    _WORKER.update(candles=candles, cfg=cfg, method=method)


def _compute_chunk(times):
    candles, cfg, method = _WORKER["candles"], _WORKER["cfg"], _WORKER["method"]
    parts = []
    for t in times:
        parts.append(snapshot_frame(zones_as_of(candles, t, cfg, method)))
    return pd.concat(parts, ignore_index=True) if parts else None


def snapshot_frame(r) -> pd.DataFrame:
    """Zet een ZoneResult om naar snapshot-rijen."""
    z = r.merged.copy()
    z.insert(0, "as_of", r.as_of)
    z["price"] = r.price
    for tf in ("1h", "4h", "1d"):
        z[f"atr_{tf}"] = r.atr.get(tf, np.nan)
    if z.empty:  # ook een uur zonder zones vastleggen, zodat we weten dat hij berekend is
        z = pd.DataFrame([{"as_of": r.as_of, "price": r.price,
                           **{f"atr_{tf}": r.atr.get(tf, np.nan) for tf in ("1h", "4h", "1d")}}])
    return z


def snapshot_path(cfg: dict, method: str):
    return project_path(cfg["snapshots"]["dir"]) / f"zones_{method}.parquet"


def build_snapshots(candles: pd.DataFrame, cfg: dict, method: str, start: pd.Timestamp,
                    workers: int = None, verbose: bool = True) -> pd.DataFrame:
    """Zorg dat er een snapshot is voor elk 1h-sluitmoment vanaf start. Incrementeel:
    alleen ontbrekende uren worden berekend."""
    path = snapshot_path(cfg, method)
    existing = pd.read_parquet(path) if path.exists() else None

    close_times = candles.index + pd.Timedelta(hours=1)
    wanted = close_times[close_times >= start]
    if existing is not None:
        done = pd.DatetimeIndex(existing["as_of"].unique())
        wanted = wanted[~wanted.isin(done)]
    if len(wanted) == 0:
        return existing

    workers = workers or cfg["snapshots"]["workers"] or os.cpu_count()
    if verbose:
        print(f"  Snapshots methode {method}: {len(wanted)} uren berekenen met {workers} processen ...")
    chunks = [wanted[i:i + 200] for i in range(0, len(wanted), 200)]
    parts = [] if existing is None else [existing]
    if workers > 1 and len(chunks) > 1:
        with ProcessPoolExecutor(workers, initializer=_init_worker,
                                 initargs=(candles, cfg, method)) as ex:
            for k, part in enumerate(ex.map(_compute_chunk, chunks)):
                parts.append(part)
                if verbose and (k + 1) % 20 == 0:
                    print(f"    {k + 1}/{len(chunks)} blokken klaar")
    else:
        _init_worker(candles, cfg, method)
        parts += [_compute_chunk(c) for c in chunks]

    out = pd.concat([p for p in parts if p is not None], ignore_index=True)
    out = out.sort_values(["as_of", "score"], ascending=[True, False], kind="stable").reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path)
    return out


def load_snapshots(cfg: dict, method: str) -> pd.DataFrame:
    path = snapshot_path(cfg, method)
    if not path.exists():
        raise FileNotFoundError(f"{path} bestaat niet; draai eerst build_snapshots")
    return pd.read_parquet(path)
