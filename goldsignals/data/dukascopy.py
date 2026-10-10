"""Historische XAUUSD-data van Dukascopy (via de pip-library dukascopy-python).

De data wordt lokaal gecachet als parquet, zodat we niet elke run opnieuw 5 jaar
downloaden. Naast het parquet-bestand staat een klein json-bestand dat bijhoudt
welke periode al is opgehaald (een weekend levert geen candles op, dus aan de data
zelf zie je niet of een periode al is geprobeerd).

Let op: als de download mislukt, krijg je een DataDownloadError. Er is GEEN
stille fallback naar yfinance: dat is een andere bron (GC=F futures) met andere
koersniveaus.
"""
import json
import logging
import socket
from pathlib import Path

import pandas as pd

from goldsignals.config import project_path
from goldsignals.data.provider import DataDownloadError, DataProvider, validate_candles

ONE_HOUR = pd.Timedelta(hours=1)
# Bij elke update halen we de laatste dag opnieuw op, voor het geval Dukascopy
# de meest recente candles nog heeft gecorrigeerd.
REFRESH_OVERLAP = pd.Timedelta(days=1)


class DukascopyProvider(DataProvider):
    def __init__(self, instrument: str, offer_side: str, cache_dir: Path):
        self.instrument = instrument
        self.offer_side = offer_side.lower()
        self.cache_dir = Path(cache_dir)
        safe_name = instrument.replace("/", "")
        self.cache_file = self.cache_dir / f"{safe_name}_1h_{self.offer_side}.parquet"
        self.meta_file = self.cache_file.with_suffix(".json")

    @classmethod
    def from_config(cls, cfg: dict) -> "DukascopyProvider":
        d = cfg["data"]
        return cls(d["instrument"], d["offer_side"], project_path(d["cache_dir"]))

    # ---------- publieke functie ----------

    def get_candles_1h(self, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        start = pd.Timestamp(start).tz_convert("UTC")
        end = pd.Timestamp(end).tz_convert("UTC")
        now = pd.Timestamp.now(tz="UTC")
        end = min(end, now)

        cached, covered = self._load_cache()
        pieces = [cached] if cached is not None else []

        if covered is None:
            pieces.append(self._download(start, end, now))
            covered = (start, end)
        else:
            cov_start, cov_end = covered
            if start < cov_start:  # oudere data nodig
                pieces.append(self._download(start, cov_start, now))
                cov_start = start
            if end > cov_end:  # nieuwere data nodig
                pieces.append(self._download(cov_end - REFRESH_OVERLAP, end, now))
                cov_end = end
            covered = (cov_start, cov_end)

        df = validate_candles(pd.concat(pieces))
        self._save_cache(df, covered)
        return df[(df.index >= start) & (df.index < end)]

    # ---------- intern ----------

    def _download(self, start: pd.Timestamp, end: pd.Timestamp, now: pd.Timestamp) -> pd.DataFrame:
        import dukascopy_python as dk

        side = dk.OFFER_SIDE_BID if self.offer_side == "bid" else dk.OFFER_SIDE_ASK
        print(f"  Dukascopy: download {self.instrument} 1h {start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} UTC ...")

        # De library zet zelf geen timeout op zijn HTTP-requests; zonder deze regel
        # kan een hangende verbinding het programma eeuwig laten wachten.
        # De library logt elke tussenstap; dat willen we niet in onze output.
        logging.getLogger("DUKASCRIPT").propagate = False
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(60)
        try:
            raw = dk.fetch(self.instrument, dk.INTERVAL_HOUR_1, side,
                           start.to_pydatetime(), end.to_pydatetime())
        except Exception as e:
            raise DataDownloadError(
                f"Dukascopy-download mislukt voor {self.instrument} "
                f"({start:%Y-%m-%d} -> {end:%Y-%m-%d}): {type(e).__name__}: {e}\n"
                "Er is GEEN fallback naar yfinance gebruikt. Controleer je internetverbinding "
                "en probeer het opnieuw, of geef expliciet toestemming voor een andere bron."
            ) from e
        finally:
            socket.setdefaulttimeout(old_timeout)

        if raw.empty and (end - start) > pd.Timedelta(days=4):
            # Meer dan een weekend zonder data = vrijwel zeker een probleem bij de bron.
            raise DataDownloadError(
                f"Dukascopy gaf 0 candles terug voor {start:%Y-%m-%d} -> {end:%Y-%m-%d}. "
                "Er is GEEN fallback naar yfinance gebruikt."
            )
        if raw.empty:
            return raw

        df = validate_candles(raw)
        # Lopende (nog niet gesloten) candle weggooien: alleen afgeronde uren cachen.
        return df[df.index + ONE_HOUR <= now]

    def _load_cache(self):
        if not self.cache_file.exists() or not self.meta_file.exists():
            return None, None
        df = pd.read_parquet(self.cache_file)
        meta = json.loads(self.meta_file.read_text())
        covered = (pd.Timestamp(meta["covered_start"]), pd.Timestamp(meta["covered_end"]))
        return df, covered

    def _save_cache(self, df: pd.DataFrame, covered) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        df.to_parquet(self.cache_file)
        self.meta_file.write_text(json.dumps({
            "covered_start": covered[0].isoformat(),
            "covered_end": covered[1].isoformat(),
            "source": f"dukascopy {self.instrument} 1h {self.offer_side}",
        }, indent=2))
