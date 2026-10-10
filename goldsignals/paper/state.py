"""Bestendige state van paper trading, als leesbare tekstbestanden.

Waarom geen SQLite? De state wordt elk uur gecommit op de branch `state`. Een
binaire database verandert dan elk uur helemaal, en git moet elke versie volledig
bewaren; tekstbestanden (CSV/JSON) worden als kleine wijzigingen opgeslagen. En je kunt
ze gewoon openen op GitHub.

Bestanden in de state-map:
- trades.csv     alle paper trades (open en gesloten)
- pending.json   signalen die op de open van de volgende candle gevuld moeten worden
- meta.json      laatst verwerkte candle, tijdstip laatste meldingen, enz.
- sent.json      sleutels van verstuurde meldingen (voorkomt dubbele meldingen)
- outbox.json    meldingen die nog verstuurd moeten worden (bij een fout: volgende run opnieuw)
- runs.csv       logboek per run (status, data-vertraging)
"""
import json
from pathlib import Path

import pandas as pd

TRADE_COLUMNS = ["id", "strategy", "status", "signal_time", "direction", "entry_time", "entry", "stop",
                 "target", "rr", "units_oz", "risk_eur", "exit_time", "exit", "result", "r", "pnl_eur",
                 "equity_after", "reason", "label"]
RUN_COLUMNS = ["run_time", "status", "last_candle", "new_candles", "latency_min", "message"]
TIME_COLS = ["signal_time", "entry_time", "exit_time"]
MAX_SENT_KEYS = 5000


class State:
    def __init__(self, folder: Path):
        self.dir = Path(folder)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.trades = self._read_csv("trades.csv", TRADE_COLUMNS, TIME_COLS)
        self.runs = self._read_csv("runs.csv", RUN_COLUMNS, ["run_time", "last_candle"])
        self.pending = self._read_json("pending.json", [])
        self.meta = self._read_json("meta.json", {})
        self.sent = self._read_json("sent.json", [])
        self.outbox = self._read_json("outbox.json", [])

    # ---------- lezen/schrijven ----------

    def _read_csv(self, name, columns, time_cols):
        p = self.dir / name
        if not p.exists():
            return pd.DataFrame(columns=columns)
        df = pd.read_csv(p)
        for c in time_cols:
            if c in df:
                df[c] = pd.to_datetime(df[c], utc=True)
        return df

    def _read_json(self, name, default):
        p = self.dir / name
        return json.loads(p.read_text()) if p.exists() else default

    def save(self):
        self.trades.to_csv(self.dir / "trades.csv", index=False)
        self.runs.tail(2000).to_csv(self.dir / "runs.csv", index=False)
        for name, obj in (("pending.json", self.pending), ("meta.json", self.meta),
                          ("sent.json", self.sent[-MAX_SENT_KEYS:]), ("outbox.json", self.outbox)):
            (self.dir / name).write_text(json.dumps(obj, indent=1, sort_keys=True, default=str))

    # ---------- trades ----------

    def open_trades(self, strategy: str = None) -> pd.DataFrame:
        t = self.trades[self.trades["status"] == "open"]
        return t if strategy is None else t[t["strategy"] == strategy]

    def closed_trades(self) -> pd.DataFrame:
        return self.trades[self.trades["status"] == "closed"]

    def add_trade(self, row: dict):
        if (self.trades["id"] == row["id"]).any():     # idempotent: nooit twee keer dezelfde trade
            return False
        new = pd.DataFrame([row], columns=TRADE_COLUMNS)
        self.trades = new if self.trades.empty else pd.concat([self.trades, new], ignore_index=True)
        return True

    def update_trade(self, trade_id: str, **fields):
        idx = self.trades.index[self.trades["id"] == trade_id]
        for k, v in fields.items():
            col = self.trades[k]
            # Een lege kolom (alleen NaN) heeft type float; dan past er geen tekst/tijd in.
            if isinstance(v, pd.Timestamp) and not pd.api.types.is_datetime64_any_dtype(col):
                self.trades[k] = pd.to_datetime(col, utc=True)
            elif isinstance(v, str) and col.dtype != object:
                self.trades[k] = col.astype(object)
            self.trades.loc[idx, k] = v

    def equity(self, strategy: str, start: float) -> float:
        closed = self.closed_trades()
        closed = closed[closed["strategy"] == strategy]
        return float(start + closed["pnl_eur"].astype(float).sum())

    # ---------- meldingen ----------

    def queue(self, key: str, kind: str, text: str, photo: str = None):
        """Zet een melding klaar. Dezelfde sleutel wordt nooit twee keer verstuurd."""
        if key in self.sent or any(m["key"] == key for m in self.outbox):
            return False
        self.outbox.append({"key": key, "kind": kind, "text": text, "photo": photo})
        return True

    def mark_sent(self, key: str):
        self.sent.append(key)
        self.outbox = [m for m in self.outbox if m["key"] != key]

    def log_run(self, **row):
        new = pd.DataFrame([row], columns=RUN_COLUMNS)
        self.runs = new if self.runs.empty else pd.concat([self.runs, new], ignore_index=True)
