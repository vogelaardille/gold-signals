"""Ronde 4: 1h-candles (bid en ask) van Dukascopy voor valutaparen.

- Download per paar, per kant (bid/ask) en per kalenderjaar naar data/cache/fx/ (niet in git).
- Tijden gaan altijd als UTC (tz-aware) naar de library: een tijd zonder tijdzone leest
  dukascopy_python als lokale tijd van deze computer.
- Lezen gaat ALTIJD met een einddatum (`until`, exclusief). Research-code gebruikt
  `research_data()`, die nooit iets van 2020 of later teruggeeft. H4 gaat alleen via
  `fx/open_holdout.py`.
- Geen stille fallback: lukt een download niet, dan volgt een DataDownloadError.

Downloaden + kwaliteitsrapport: .venv/bin/python -m fx.data
"""
import datetime as dt
import json
import logging
import socket
import time
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from goldsignals.data.provider import DataDownloadError, validate_candles

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["open", "high", "low", "close"]
ONE_HOUR = pd.Timedelta(hours=1)


def load_config() -> dict:
    with open(Path(__file__).with_name("config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def cache_path(cfg, pair: str, side: str) -> Path:
    return ROOT / cfg["data"]["cache_dir"] / f"{pair.replace('/', '')}_1h_{side}.parquet"


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def _fetch(pair: str, side: str, start: pd.Timestamp, stop: pd.Timestamp, retries: int = 3) -> pd.DataFrame:
    import dukascopy_python as dk
    logging.getLogger("DUKASCRIPT").propagate = False
    offer = dk.OFFER_SIDE_BID if side == "bid" else dk.OFFER_SIDE_ASK
    last = None
    for attempt in range(retries):
        old = socket.getdefaulttimeout()
        socket.setdefaulttimeout(60)
        try:
            raw = dk.fetch(pair, dk.INTERVAL_HOUR_1, offer, start.to_pydatetime(), stop.to_pydatetime())
            return validate_candles(raw) if len(raw) else raw
        except Exception as e:  # netwerkfout: even wachten en opnieuw
            last = e
            time.sleep(5 * (attempt + 1))
        finally:
            socket.setdefaulttimeout(old)
    raise DataDownloadError(f"Dukascopy {pair} {side} {start:%Y-%m-%d} mislukt na {retries} pogingen: "
                            f"{type(last).__name__}: {last}. Er is GEEN fallback naar een andere bron gebruikt.")


def download(cfg, pair: str, side: str, end: pd.Timestamp, verbose=True) -> pd.DataFrame:
    """Download (of vul aan) per jaar t/m `end` (exclusief); volledige jaren in de cache worden overgeslagen."""
    path = cache_path(cfg, pair, side)
    meta_path = path.with_suffix(".json")
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"years_done": []}
    parts = [pd.read_parquet(path)] if path.exists() else []
    for year in range(cfg["data"]["first_year"], end.year + 1):
        start = pd.Timestamp(year, 1, 1, tz="UTC")
        stop = min(pd.Timestamp(year + 1, 1, 1, tz="UTC"), end)
        if start >= stop:
            break
        complete = stop == pd.Timestamp(year + 1, 1, 1, tz="UTC")
        if year in meta["years_done"] and complete:
            continue
        if verbose:
            print(f"  Dukascopy {pair} {side} {year} ...", flush=True)
        df = _fetch(pair, side, start, stop)
        if len(df) == 0:
            raise DataDownloadError(f"Dukascopy gaf 0 candles voor {pair} {side} {year}.")
        parts.append(df[df.index < stop])
        if complete:
            meta["years_done"] = sorted(set(meta["years_done"]) | {year})
    out = validate_candles(pd.concat(parts))
    out = out[out.index + ONE_HOUR <= min(end, pd.Timestamp.now(tz="UTC"))]
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path)
    meta.update(source=f"dukascopy {pair} 1h {side}", first=str(out.index[0]), last=str(out.index[-1]))
    meta_path.write_text(json.dumps(meta, indent=1))
    return out


# ---------------------------------------------------------------------------
# Lezen (altijd met einddatum)
# ---------------------------------------------------------------------------

def load_pair(cfg, pair: str, until: pd.Timestamp, since: pd.Timestamp = None, clean: bool = True) -> pd.DataFrame:
    """Bid- en ask-candles naast elkaar, plus mid (gemiddelde per veld).
    Alleen candles die vóór `until` gesloten zijn. Uren met maar één kant vallen weg.
    clean: candles buiten de sessie (in 2010-2014 vult de feed weekenden met vlakke candles)
    en uren met ask < bid weglaten, en paar-jaren met te veel ontbrekende uren (PLAN4 §1)."""
    until = pd.Timestamp(until)
    sides = {}
    for side in ("bid", "ask"):
        path = cache_path(cfg, pair, side)
        if not path.exists():
            raise FileNotFoundError(f"{path} ontbreekt; draai eerst: python -m fx.data")
        sides[side] = pd.read_parquet(path)[FIELDS].add_prefix(f"{side}_")
    df = sides["bid"].join(sides["ask"], how="inner")
    for f in FIELDS:
        df[f] = (df[f"bid_{f}"] + df[f"ask_{f}"]) / 2
    df = df[df.index + ONE_HOUR <= until]
    if since is not None:
        df = df[df.index >= pd.Timestamp(since)]
    if clean:
        crossed = np.zeros(len(df), dtype=bool)
        for f in FIELDS:
            crossed |= (df[f"ask_{f}"] < df[f"bid_{f}"]).to_numpy()
        excluded = cfg["data"].get("excluded_years", {}).get(pair, [])
        df = df[in_fx_session(df.index) & ~crossed & ~df.index.year.isin(excluded)]
    return df


def research_data(cfg, pair: str) -> pd.DataFrame:
    """Warm-up + research: alles vóór research_end. Nooit data van H4."""
    p = cfg["periods"]
    return load_pair(cfg, pair, until=pd.Timestamp(p["research_end"], tz="UTC"),
                     since=pd.Timestamp(p["warmup_start"], tz="UTC"))


# ---------------------------------------------------------------------------
# Kwaliteit
# ---------------------------------------------------------------------------

def in_fx_session(index: pd.DatetimeIndex) -> np.ndarray:
    """Valuta handelt van zondag 17:00 tot vrijdag 17:00 New York-tijd."""
    ny = index.tz_convert("America/New_York")
    wd, h = ny.weekday, ny.hour
    closed = (wd == 5) | ((wd == 4) & (h >= 17)) | ((wd == 6) & (h < 17))
    return ~np.asarray(closed)


def quality_by_year(df: pd.DataFrame, pip: float, with_spread: bool = True) -> pd.DataFrame:
    """Per jaar: candles, ontbrekende handelsuren, candles buiten de sessie, vlakke candles,
    sprongen > 8x de mediane range, ask < bid, en (optioneel) de spread in pips."""
    rows = []
    for year, d in df.groupby(df.index.year):
        hours = pd.date_range(pd.Timestamp(year, 1, 1, tz="UTC"),
                              min(pd.Timestamp(year + 1, 1, 1, tz="UTC"), d.index[-1] + ONE_HOUR),
                              freq="h", inclusive="left")
        hours = hours[hours >= d.index[0].floor("D")]
        expected = hours[in_fx_session(hours)]
        missing = len(expected.difference(d.index))
        rng = d["high"] - d["low"]
        jump = (d["open"] - d["close"].shift()).abs()
        bad = sum(int((d[f"ask_{f}"] < d[f"bid_{f}"]).sum()) for f in FIELDS)
        row = {"year": year, "candles": len(d), "missing_trading_hours": missing,
               "missing_pct": round(100 * missing / max(len(expected), 1), 2),
               "outside_session": int((~in_fx_session(d.index)).sum()),
               "flat_candles": int((rng == 0).sum()),
               "jumps_gt_8x_median_range": int((jump > 8 * rng.median()).sum()),
               "ask_below_bid": bad}
        if with_spread:
            s = (d["ask_open"] - d["bid_open"]) / pip
            row.update(spread_median_pips=round(s.median(), 2), spread_p95_pips=round(s.quantile(0.95), 2))
        rows.append(row)
    return pd.DataFrame(rows)


def spread_by_ny_hour(df: pd.DataFrame, pip: float) -> pd.Series:
    """Mediane spread (pips, bij de open) per uur New York-tijd. Kosteninformatie."""
    s = (df["ask_open"] - df["bid_open"]) / pip
    return s.groupby(df.index.tz_convert("America/New_York").hour).median().round(2)


def first_fridays(start: pd.Timestamp, end: pd.Timestamp) -> list:
    """Eerste vrijdag van elke maand: benadering van de releasedag van het Amerikaanse
    banenrapport (8:30 NY). Een paar maanden wijken af; de toets is een gemiddelde."""
    out = []
    for m in pd.date_range(start.tz_convert(None).normalize(), end.tz_convert(None), freq="MS"):
        d = m + pd.Timedelta(days=(4 - m.weekday()) % 7)
        out.append(d.date())
    return out


def timestamp_check(df: pd.DataFrame) -> dict:
    """Op banenrapport-vrijdagen moet de grootste gemiddelde absolute uurbeweging in de bar
    van 08:00 NY vallen (die bevat 8:30). Kijkt alleen naar volatiliteit, niet naar richting."""
    ny = df.index.tz_convert("America/New_York")
    move = (df["close"] - df["open"]).abs() / df["open"] * 1e4
    nfp = pd.Index(ny.date).isin(first_fridays(df.index[0], df.index[-1]))
    by_hour = move[nfp].groupby(ny.hour[nfp]).mean()
    other = move[(ny.weekday == 4) & ~nfp].groupby(ny.hour[(ny.weekday == 4) & ~nfp]).mean()
    peak = int(by_hour.idxmax())
    return {"peak_ny_hour": peak, "ok": peak == 8,
            "nfp_bp_by_ny_hour": by_hour.round(1).to_dict(),
            "other_fridays_bp_by_ny_hour": other.round(1).to_dict()}


def main():
    cfg = load_config()
    p = cfg["periods"]
    research_end = pd.Timestamp(p["research_end"], tz="UTC")
    h4_start, h4_end = pd.Timestamp(p["h4_start"], tz="UTC"), pd.Timestamp(p["h4_end"], tz="UTC")
    for pair in cfg["pairs"]:
        for side in ("bid", "ask"):
            download(cfg, pair, side, h4_end)

    out = ["# Ronde 4 – datakwaliteit", "",
           "Dukascopy 1h, bid en ask. Research = warm-up + R4 (t/m 2019). Voor H4 alleen "
           "ontbrekende uren en de tijdstempelcontrole (PLAN4 §1), geen spreads of rendementen.", ""]
    summary = {}
    for pair, pip in cfg["pairs"].items():
        warmup = pd.Timestamp(p["warmup_start"], tz="UTC")
        r = load_pair(cfg, pair, until=research_end, since=warmup, clean=False)
        h = load_pair(cfg, pair, until=h4_end, since=h4_start, clean=False)
        rc = research_data(cfg, pair)
        hc = load_pair(cfg, pair, until=h4_end, since=h4_start)
        out_clean = (f"- na opschonen (sessie, ask ≥ bid, uitgesloten jaren): research {len(rc)} uren "
                     f"(−{len(r) - len(rc)}), waarvan vlak {int((rc['high'] == rc['low']).sum())}; "
                     f"H4 {len(hc)} uren (−{len(h) - len(hc)})")
        q_r = quality_by_year(r, pip)
        q_h = quality_by_year(h, pip, with_spread=False)[["year", "candles", "missing_trading_hours",
                                                           "missing_pct", "outside_session"]]
        ts_r, ts_h = timestamp_check(r), timestamp_check(h)
        excluded = [int(y) for y in q_r.loc[q_r["missing_pct"] > cfg["data"]["max_missing_pct"], "year"]]
        summary[pair] = {"research_first": str(r.index[0]), "research_last": str(r.index[-1]),
                         "timestamp_ok_research": ts_r["ok"], "timestamp_ok_h4": ts_h["ok"],
                         "excluded_years": excluded}
        out += [f"## {pair}", "",
                f"- research: {len(r)} uren, {r.index[0]} t/m {r.index[-1]} (UTC)",
                f"- H4: {len(h)} uren, {h.index[0]} t/m {h.index[-1]}",
                f"- tijdstempelcontrole research: piek in NY-uur {ts_r['peak_ny_hour']} "
                f"→ {'OK' if ts_r['ok'] else 'FOUT'}; H4: piek {ts_h['peak_ny_hour']} "
                f"→ {'OK' if ts_h['ok'] else 'FOUT'}",
                f"- jaren met > {cfg['data']['max_missing_pct']}% ontbrekende handelsuren (vallen weg): "
                f"{excluded or 'geen'}", out_clean, "",
                "### Research per jaar", "", q_r.to_markdown(index=False), "",
                "### H4 per jaar (alleen beschikbaarheid)", "", q_h.to_markdown(index=False), "",
                "### Mediane spread per NY-uur (research, pips)", "",
                spread_by_ny_hour(r[r.index >= pd.Timestamp(p["research_start"], tz="UTC")], pip)
                .rename("spread").to_frame().T.to_markdown(index=False), "",
                "### Gemiddelde |uurbeweging| op banenrapport-vrijdagen per NY-uur (research, bp)", "",
                pd.DataFrame([ts_r["nfp_bp_by_ny_hour"], ts_r["other_fridays_bp_by_ny_hour"]],
                             index=["banenrapport", "andere vrijdagen"]).round(1).to_markdown(), ""]
    res = ROOT / "research/round4"
    res.mkdir(parents=True, exist_ok=True)
    (res / "data_quality.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    (res / "results").mkdir(exist_ok=True)
    (res / "results/data_quality.json").write_text(json.dumps(summary, indent=1))
    print("\n".join(out))


if __name__ == "__main__":
    main()
