"""Ronde 2: lange XAUUSD-historie (1h en 15m) en macroreeksen (FRED).

Aparte cache (data/cache/round2/), zodat de live-cache van ronde 1 niet verandert.
Download per kalenderjaar: als één jaar mislukt, krijg je een duidelijke fout
(DataDownloadError). Er is GEEN fallback naar een andere bron.

Kwaliteitscontrole (`quality_report`): per jaar het aantal candles, het aantal gaten
binnen handelstijd, weekend-candles, candles zonder beweging en extreme sprongen.
"""
import datetime as dt
import io
import json
import logging
import socket
import time

import numpy as np
import pandas as pd
import requests

from goldsignals.config import project_path
from goldsignals.data.provider import DataDownloadError, validate_candles
from goldsignals.paper.market_hours import is_trading_hour

CACHE = "data/cache/round2"
INTERVALS = {"1h": "INTERVAL_HOUR_1", "15m": "INTERVAL_MIN_15"}
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"


def cache_path(tf: str):
    return project_path(CACHE) / f"XAUUSD_{tf}_bid.parquet"


def _fetch_year(tf: str, year: int, end: pd.Timestamp, retries: int = 3) -> pd.DataFrame:
    import dukascopy_python as dk
    logging.getLogger("DUKASCRIPT").propagate = False
    start = dt.datetime(year, 1, 1)
    stop = min(dt.datetime(year + 1, 1, 1), end.tz_convert("UTC").tz_localize(None).to_pydatetime())
    last = None
    for attempt in range(retries):
        old = socket.getdefaulttimeout()
        socket.setdefaulttimeout(60)
        try:
            raw = dk.fetch("XAU/USD", getattr(dk, INTERVALS[tf]), dk.OFFER_SIDE_BID, start, stop)
            return validate_candles(raw) if len(raw) else raw
        except Exception as e:  # netwerkfout: even wachten en opnieuw
            last = e
            time.sleep(5 * (attempt + 1))
        finally:
            socket.setdefaulttimeout(old)
    raise DataDownloadError(f"Dukascopy {tf} {year} mislukt na {retries} pogingen: {type(last).__name__}: {last}. "
                            "Er is GEEN fallback naar een andere bron gebruikt.")


def download(tf: str, first_year: int, end: pd.Timestamp, verbose=True) -> pd.DataFrame:
    """Download (of vul aan) per jaar; jaren die al in de cache zitten worden overgeslagen."""
    path = cache_path(tf)
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"years_done": []}
    parts = [pd.read_parquet(path)] if path.exists() else []
    end = pd.Timestamp(end)
    for year in range(first_year, end.year + 1):
        complete_year = pd.Timestamp(year + 1, 1, 1, tz="UTC") <= end
        if year in meta["years_done"] and complete_year:
            continue
        if verbose:
            print(f"  Dukascopy {tf} {year} ...", flush=True)
        df = _fetch_year(tf, year, end)
        if len(df) == 0:
            raise DataDownloadError(f"Dukascopy gaf 0 candles voor {tf} {year}.")
        parts.append(df)
        if complete_year:
            meta["years_done"] = sorted(set(meta["years_done"]) | {year})
    out = validate_candles(pd.concat(parts))
    # alleen gesloten candles
    dur = pd.Timedelta(hours=1) if tf == "1h" else pd.Timedelta(minutes=15)
    out = out[out.index + dur <= pd.Timestamp.now(tz="UTC")]
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path)
    meta.update(source=f"dukascopy XAU/USD {tf} bid", first=str(out.index[0]), last=str(out.index[-1]))
    meta_path.write_text(json.dumps(meta, indent=1))
    return out


def in_session(index: pd.DatetimeIndex) -> np.ndarray:
    """Gevectoriseerde versie van market_hours.is_trading_hour (op het uur van de candle)."""
    ny = index.tz_convert("America/New_York")
    wd, h = ny.weekday, ny.hour
    closed = (h == 17) | (wd == 5) | ((wd == 4) & (h >= 17)) | ((wd == 6) & (h < 18))
    return ~np.asarray(closed)


def load(tf: str, until: pd.Timestamp = None, session_only: bool = True) -> pd.DataFrame:
    """Candles uit de cache. session_only: candles buiten de huidige goud-sessie weglaten
    (vóór 2013 leverde de feed ook candles in de dagpauze en op zondagmiddag; zie PLAN2 §1).
    until: alleen candles die vóór dit moment gesloten zijn."""
    path = cache_path(tf)
    if not path.exists():
        raise FileNotFoundError(f"{path} ontbreekt; draai eerst goldsignals.round2.fetch")
    c = pd.read_parquet(path)
    c = c[c.index >= pd.Timestamp("2004-01-01", tz="UTC")]
    if session_only:
        c = c[in_session(c.index)]
    if until is not None:
        dur = pd.Timedelta(hours=1) if tf == "1h" else pd.Timedelta(minutes=15)
        c = c[c.index + dur <= until]
    return c


def quality_report(c: pd.DataFrame, tf: str) -> pd.DataFrame:
    """Per jaar: candles, verwachte handelsuren zonder candle, weekend-candles,
    candles zonder beweging (high == low) en sprongen > 8 x de mediane range."""
    dur = pd.Timedelta(hours=1) if tf == "1h" else pd.Timedelta(minutes=15)
    rows = []
    for year, d in c.groupby(c.index.year):
        hours = pd.date_range(d.index[0].floor("h"), d.index[-1], freq="h")
        expected = [h for h in hours if is_trading_hour(h)]
        have = set(d.index.floor("h"))
        missing = [h for h in expected if h not in have]
        weekend = sum(1 for t in d.index if not is_trading_hour(t.floor("h")))
        rng = (d["high"] - d["low"])
        jump = (d["open"] - d["close"].shift()).abs()
        big = int((jump > 8 * rng.median()).sum())
        rows.append({"year": year, "candles": len(d), "missing_trading_hours": len(missing),
                     "missing_pct": round(100 * len(missing) / max(len(expected), 1), 2),
                     "outside_trading_hours": weekend, "flat_candles": int((rng == 0).sum()),
                     "gaps_gt_8x_median_range": big})
    return pd.DataFrame(rows)


def fred(series: str) -> pd.Series:
    """Dagreeks van FRED (gratis, zonder API-sleutel). Gecachet als CSV."""
    path = project_path(CACHE) / f"fred_{series}.csv"
    if not path.exists():
        r = requests.get(FRED_URL.format(series=series), timeout=60)
        r.raise_for_status()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(r.text)
    df = pd.read_csv(path)
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    return s.dropna()
