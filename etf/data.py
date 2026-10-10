"""Ronde 3: dagkoersen van ETF's (yfinance) en rentes/wisselkoers (FRED).

- Download één keer per ticker naar data/cache/etf/ (parquet, niet in git).
- Koers = 'Adj Close' van Yahoo: gecorrigeerd voor dividend en splitsing, dus het
  totaalrendement. De ETF-kosten (TER) zitten al in de koers.
- Lezen gaat ALTIJD met een einddatum (`until`, exclusief). Research-code gebruikt
  `research_prices()`, die nooit iets na 2020-12 teruggeeft. H3 en P kunnen alleen via
  `etf/holdout.py` worden geopend (eenmalig, gelogd).
- Er is geen stille fallback: lukt een download niet, dan volgt een fout.

Downloaden + kwaliteitsrapport: .venv/bin/python -m etf.data
"""
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import yaml

ROOT = Path(__file__).resolve().parent.parent
FRED_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}"


def load_config() -> dict:
    with open(Path(__file__).with_name("config.yaml"), encoding="utf-8") as f:
        return yaml.safe_load(f)


def cache_dir(cfg) -> Path:
    return ROOT / cfg["data"]["cache_dir"]


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def download_ticker(ticker: str, cfg) -> Path:
    """Volledige dagelijkse historie van Yahoo (incl. dividenden, splitsingen, uitkeringen)."""
    import yfinance as yf
    h = yf.Ticker(ticker).history(period="max", auto_adjust=False, actions=True)
    if h.empty:
        raise RuntimeError(f"yfinance gaf geen data voor {ticker}")
    h.index = pd.DatetimeIndex(h.index.tz_localize(None).normalize(), name="date")
    path = cache_dir(cfg) / f"{ticker}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    h.to_parquet(path)
    return path


def download_fred(series: str, cfg) -> Path:
    r = requests.get(FRED_URL.format(series=series), timeout=60)
    r.raise_for_status()
    path = cache_dir(cfg) / f"fred_{series}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(r.text)
    return path


# ---------------------------------------------------------------------------
# Lezen (altijd met einddatum)
# ---------------------------------------------------------------------------

def read_ticker(ticker: str, cfg, until) -> pd.DataFrame:
    path = cache_dir(cfg) / f"{ticker}.parquet"
    if not path.exists():
        raise FileNotFoundError(f"{path} ontbreekt: draai eerst `python -m etf.data`")
    h = pd.read_parquet(path)
    return h[h.index < pd.Timestamp(until)]


def read_fred(series: str, cfg, until) -> pd.Series:
    path = cache_dir(cfg) / f"fred_{series}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} ontbreekt: draai eerst `python -m etf.data`")
    df = pd.read_csv(path)
    s = pd.to_numeric(df.iloc[:, 1], errors="coerce")
    s.index = pd.to_datetime(df.iloc[:, 0])
    s = s.dropna()
    return s[s.index < pd.Timestamp(until)]


def price_table(tickers, cfg, until) -> pd.DataFrame:
    """Adjusted close per ticker op de handelsdagen van de kalender-ticker (SPY).
    Een ontbrekende dag binnen de historie van een ticker krijgt de vorige koers
    (rendement 0); vóór de eerste noteringsdag blijft het NaN."""
    col = cfg["data"]["price_column"]
    cal = read_ticker(cfg["data"]["calendar_ticker"], cfg, until).index
    out = {}
    for t in tickers:
        s = read_ticker(t, cfg, until)[col]
        s = s.reindex(cal.union(s.index)).ffill().reindex(cal)
        s[cal < read_ticker(t, cfg, until).index[0]] = np.nan
        out[t] = s
    return pd.DataFrame(out, index=cal)


def cash_daily(cfg, index: pd.DatetimeIndex, series=None, until=None) -> pd.Series:
    """Dagrendement van cash uit een maandrente in % per jaar (TB3MS): (1 + y)^(1/252) - 1.
    Elke dag krijgt de rente van zijn eigen maand. Dat is een uitkomst, geen
    beslisinformatie; voor beslissingen zie `cash_known_at`."""
    series = series or cfg["data"]["fred_cash"]
    m = read_fred(series, cfg, until or index[-1] + pd.Timedelta(days=1))
    m.index = m.index.to_period("M")
    rate = pd.Series(index.to_period("M"), index=index).map(m)
    if rate.isna().any():
        rate = rate.ffill()       # laatste maand nog niet gepubliceerd: vorige waarde
    return (1 + rate / 100) ** (1 / 252) - 1


def cash_known_at(cfg, month_ends: pd.DatetimeIndex, lookback: int, until) -> pd.Series:
    """Cashrendement over `lookback` maanden zoals bekend op elke maandsluiting.
    TB3MS van maand m wordt pas begin maand m+1 gepubliceerd. Op het slot van maand m
    gebruiken we daarom de maanden m-lookback .. m-1 (één maand vertraging)."""
    m = read_fred(cfg["data"]["fred_cash"], cfg, until)
    monthly = (1 + m / 100) ** (1 / 12) - 1
    monthly.index = monthly.index.to_period("M")
    out = {}
    for d in month_ends:
        p = d.to_period("M")
        window = monthly.reindex(pd.period_range(p - lookback, p - 1, freq="M"))
        out[d] = float((1 + window).prod() - 1) if window.notna().all() else np.nan
    return pd.Series(out)


def research_prices(cfg) -> pd.DataFrame:
    """Alle ETF-koersen tot het einde van het research-blok (nooit H3)."""
    return price_table(cfg["universe"], cfg, cfg["periods"]["research_end"])


# ---------------------------------------------------------------------------
# Kwaliteitsrapport (alleen beschikbaarheid, gaten en de dividendcorrectie)
# ---------------------------------------------------------------------------

def quality(ticker: str, cfg, until, check_returns: bool) -> dict:
    h = read_ticker(ticker, cfg, until)
    cal = read_ticker(cfg["data"]["calendar_ticker"], cfg, until).index
    cal = cal[cal >= h.index[0]]
    missing = cal.difference(h.index)
    out = {"ticker": ticker, "first": str(h.index[0].date()), "last": str(h.index[-1].date()),
           "days": len(h), "missing_days": len(missing),
           "missing_examples": [str(d.date()) for d in missing[:5]],
           "extra_days": len(h.index.difference(cal))}
    if check_returns:
        adj = h["Adj Close"]
        out["nan_or_zero"] = int((adj.isna() | (adj <= 0)).sum())
        r = adj.pct_change().dropna()
        out["days_abs_return_gt_15pct"] = int((r.abs() > 0.15).sum())
        out["big_moves"] = [f"{d.date()} {v:+.1%}" for d, v in r[r.abs() > 0.15].items()][:5]
        # Dividendcorrectie: de verhouding Adj Close / Close mag alleen veranderen rond een
        # dag met een uitkering of splitsing. Anders klopt de correctie niet.
        ratio = (h["Adj Close"] / h["Close"])
        jump = ratio.pct_change().abs() > 1e-4
        events = (h["Dividends"] != 0) | (h["Stock Splits"] != 0)
        if "Capital Gains" in h:
            events |= h["Capital Gains"].fillna(0) != 0
        near_event = events | events.shift(1, fill_value=False) | events.shift(-1, fill_value=False)
        out["ratio_jumps"] = int(jump.sum())
        out["ratio_jumps_without_event"] = int((jump & ~near_event).sum())
        out["dividends"] = int((h["Dividends"] != 0).sum())
        out["capital_gains"] = int((h.get("Capital Gains", pd.Series(0, index=h.index)).fillna(0) != 0).sum())
        out["splits"] = int((h["Stock Splits"] != 0).sum())
    return out


def main():
    cfg = load_config()
    tickers = list(cfg["universe"]) + [p for p in cfg["proxies"].values() if p]
    for t in tickers:
        download_ticker(t, cfg)
        print("gedownload", t)
    for s in (cfg["data"]["fred_cash"], cfg["data"]["fred_eurusd"], cfg["data"]["fred_eur_cash"]):
        download_fred(s, cfg)
        print("gedownload FRED", s)
    # Research-tickers: volledige controle tot einde research. H3 en proxies (P): alleen
    # beschikbaarheid en gaten, geen rendementen (die blokken blijven dicht).
    rows = [quality(t, cfg, cfg["periods"]["research_end"], True) for t in cfg["universe"]]
    rows_h3 = [quality(t, cfg, "2100-01-01", False) for t in cfg["universe"]]
    rows_p = [quality(p, cfg, cfg["periods"]["p_end"], False) for p in cfg["proxies"].values() if p]
    fred = {}
    for s in (cfg["data"]["fred_cash"], cfg["data"]["fred_eurusd"], cfg["data"]["fred_eur_cash"]):
        x = read_fred(s, cfg, "2100-01-01")
        fred[s] = {"first": str(x.index[0].date()), "last": str(x.index[-1].date()), "n": len(x)}
    out = ROOT / "research/round3/results/data_quality.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    import json
    out.write_text(json.dumps({"research": rows, "full_history_availability": rows_h3,
                               "proxies_until_2005": rows_p, "fred": fred}, indent=1))
    print(json.dumps({"research": rows, "proxies": rows_p, "fred": fred}, indent=1))


if __name__ == "__main__":
    main()
