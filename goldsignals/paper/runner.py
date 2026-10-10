"""Paper trading: één run (elk uur via GitHub Actions, of handmatig).

Volgorde per run:
1. Markt dicht (weekend/dagpauze)? Dan stil stoppen (alleen eventueel het weekoverzicht).
2. Nieuwe gesloten 1h-candles ophalen (Dukascopy, met retries). Ontbreekt de candle die
   er had moeten zijn: SYSTEEM-melding (max 1 per 6 uur) en de run overslaan. Geen
   stille fallback naar een andere bron.
3. Per nieuwe candle, in volgorde:
   a. wachtende signalen vullen op de open (zelfde regels als de backtest);
   b. open trades afhandelen (stop/target, stop eerst bij twijfel);
   c. nieuwe signalen van strategieën met status candidate of validated (nooit rejected).
4. ZONE-ALERT voor de laatste candle, weekoverzicht op zondagavond.
5. State opslaan, meldingen versturen, state opnieuw opslaan.

Idempotent: de state onthoudt de laatst verwerkte candle; een tweede run met dezelfde
data doet niets nieuws. Meldingen hebben een unieke sleutel en gaan maar één keer weg.
"""
import importlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from goldsignals.backtest.engine import OpenTrade, anchor_to_entry, check_exit, cost_per_oz, try_fill
from goldsignals.config import project_path
from goldsignals.data import DataDownloadError, get_provider
from goldsignals.features import compute_features
from goldsignals.market import Market
from goldsignals.notify import messages as msg
from goldsignals.notify.charts import signal_chart
from goldsignals.paper.market_hours import expected_last_candle, market_open_now
from goldsignals.paper.state import State
from goldsignals.snapshots import snapshot_frame
from goldsignals.sr import zones_as_of
from goldsignals.strategies.base import MarketView, Signal

STRATEGIES_FILE = "research/results/strategies.json"


# ---------------------------------------------------------------------------
# Strategieën laden
# ---------------------------------------------------------------------------

def load_class(path: str):
    module, cls = path.split(":")
    return getattr(importlib.import_module(module), cls)


def active_strategies(cfg: dict) -> dict:
    """Alleen strategieën met status candidate of validated (uit het leaderboard van deel B)."""
    p = project_path(STRATEGIES_FILE)
    if not p.exists():
        return {}
    info = json.loads(p.read_text())
    out = {}
    for sid, s in info.items():
        if s.get("status") in ("candidate", "validated") and s.get("tradeable", True):
            out[sid] = {**s, "instance": load_class(s["class"])(s["params"])}
    return out


# ---------------------------------------------------------------------------
# Hulpfuncties
# ---------------------------------------------------------------------------

def fetch_candles(cfg, now, log):
    """Haal candles op met retries. Geeft (candles, fout)."""
    pcfg = cfg["paper"]
    provider = get_provider(cfg)
    start = pd.Timestamp(cfg["periods"]["warmup_start"], tz="UTC")
    expected = expected_last_candle(now)
    err = None
    for attempt in range(pcfg["data_retries"]):
        try:
            c = provider.get_candles_1h(start, pd.Timestamp.now(tz="UTC"))
            if len(c) and c.index[-1] >= expected:
                return c, None
            err = (f"Laatst gesloten candle {expected:%Y-%m-%d %H:%M} UTC is nog niet beschikbaar bij "
                   f"Dukascopy (laatste: {c.index[-1]:%Y-%m-%d %H:%M}).")
        except DataDownloadError as e:
            err = str(e).splitlines()[0]
        log(f"  poging {attempt + 1}: {err}")
        if attempt < pcfg["data_retries"] - 1:
            import time
            time.sleep(pcfg["data_wait_seconds"])
    return None, err


def build_live_market(candles, cfg, idx_needed, methods) -> Market:
    """Market met zones (via zones_as_of) alleen voor de candles die we nodig hebben."""
    feats = compute_features(candles, cfg)
    snaps = {}
    for m in methods:
        parts = [snapshot_frame(zones_as_of(candles, candles.index[i] + pd.Timedelta(hours=1), cfg, m))
                 for i in idx_needed]
        snaps[m] = pd.concat(parts, ignore_index=True)
    return Market(candles, feats, snaps)


def trade_to_open(row) -> OpenTrade:
    sig = Signal(row["strategy"], row["signal_time"], int(row["direction"]), float(row["stop"]),
                 float(row["target"]), row["reason"])
    return OpenTrade(sig, -1, float(row["entry"]), float(row["units_oz"]), float(row["risk_eur"]))


def queue_system(state: State, cfg, text: str, now):
    """SYSTEEM-melding, maximaal 1 per cooldown (6 uur)."""
    scfg = cfg["notify"]["system"]
    if not scfg["enabled"]:
        return
    last = state.meta.get("last_system_alert")
    if last and now - pd.Timestamp(last) < pd.Timedelta(hours=scfg["cooldown_hours"]):
        return
    state.meta["last_system_alert"] = now.isoformat()
    state.queue(f"system|{now:%Y-%m-%dT%H}", "system", msg.system(text, cfg))


def deviation_warning(strategy_info: dict, live: pd.DataFrame, pcfg: dict) -> str:
    """Waarschuwing als het live paper-resultaat sterk slechter is dan de backtest."""
    bt = strategy_info.get("backtest", {})
    n = len(live)
    if n < pcfg["deviation_min_trades"] or not bt.get("std_r"):
        return ""
    z = (live["r"].astype(float).mean() - bt["avg_r"]) / (bt["std_r"] / np.sqrt(n))
    if z < -pcfg["deviation_z"]:
        return (f"live gem. {live['r'].astype(float).mean():+.2f}R vs backtest {bt['avg_r']:+.2f}R "
                f"over {n} trades (z = {z:.1f}): wijkt sterk af")
    return ""


# ---------------------------------------------------------------------------
# De run
# ---------------------------------------------------------------------------

def run(cfg: dict, state_dir: Path, now: pd.Timestamp = None, send: bool = True, force: bool = False,
        candles: pd.DataFrame = None, log=print) -> dict:
    """Voer één run uit. Geeft {'changed': bool, 'status': str}.
    candles: alleen voor tests (dan wordt er niets gedownload)."""
    now = now or pd.Timestamp.now(tz="UTC")
    pcfg, ncfg = cfg["paper"], cfg["notify"]
    state = State(state_dir)
    strategies = active_strategies(cfg) if "strategies_override" not in cfg else cfg["strategies_override"]
    changed = False

    if not force and not market_open_now(now) and candles is None:
        changed |= maybe_weekly(state, cfg, now, strategies, None)
        if changed:
            state.save()
            deliver(state, cfg, send, log)
            state.save()
        return {"changed": changed, "status": "markt dicht"}

    # ---- data ----
    if candles is None:
        candles, err = fetch_candles(cfg, now, log)
        if candles is None:
            queue_system(state, cfg, f"Run overgeslagen: {err}", now)
            state.log_run(run_time=now, status="data-fout", message=err[:200])
            state.save()
            deliver(state, cfg, send, log)
            state.save()
            return {"changed": True, "status": "data-fout"}

    last_open = candles.index[-1]
    latency = None
    if state.meta.get("first_seen_candle") != last_open.isoformat():
        state.meta["first_seen_candle"] = last_open.isoformat()
        # Data-vertraging: hoe lang na het sluiten hadden we de candle? Alleen zinvol voor
        # de candle die we nu verwachtten (niet in het weekend of na een gemiste run).
        if last_open == expected_last_candle(now) and market_open_now(now):
            latency = (now - (last_open + pd.Timedelta(hours=1))).total_seconds() / 60
            state.meta["last_latency_min"] = round(latency, 1)

    # ---- welke candles zijn nieuw? ----
    last_done = state.meta.get("last_processed")
    if last_done is None:
        # Eerste run ooit: niets uit het verleden naspelen, alleen vanaf de laatste candle.
        new_idx = [len(candles) - 1]
    else:
        new_idx = list(np.flatnonzero(candles.index > pd.Timestamp(last_done)))
    new_idx = new_idx[-pcfg["max_catchup_candles"]:]
    if not new_idx:
        state.log_run(run_time=now, status="geen nieuwe candle", last_candle=last_open, new_candles=0,
                      latency_min=latency, message="")
        state.save()
        return {"changed": False, "status": "geen nieuwe candle"}

    methods = sorted({s["instance"].zone_method for s in strategies.values() if s["instance"].zone_method}
                     | {ncfg["zone_alert"]["method"]})
    market = build_live_market(candles, cfg, new_idx, methods)
    cost = cost_per_oz(cfg)
    acc = cfg["account"]
    O, H, L, C = (market.array(k) for k in ("open", "high", "low", "close"))

    for i in new_idx:
        t_close = market.close_time[i]
        late = now - t_close > pd.Timedelta(hours=pcfg["late_after_hours"])

        # a. wachtende signalen vullen op de open van deze candle
        still_pending = []
        for p in state.pending:
            if pd.Timestamp(p["signal_time"]) > candles.index[i]:
                still_pending.append(p)
                continue
            sig = Signal(p["strategy"], pd.Timestamp(p["signal_time"]), p["direction"], p["stop"], p["target"],
                         p["reason"], min_rr=p["min_rr"],
                         meta={"stop_dist": p["stop_dist"], "rr": p["rr"]} if p.get("stop_dist") else {})
            sig = anchor_to_entry(sig, O[i])
            tid = f"{p['strategy']}|{p['signal_time']}"
            if try_fill(sig, O[i]):
                eq = state.equity(p["strategy"], acc["start_equity_eur"])
                risk_eur = eq * acc["risk_pct"] / 100
                risk_oz = sig.direction * (O[i] - sig.stop)
                state.add_trade({"id": tid, "strategy": p["strategy"], "status": "open",
                                 "signal_time": sig.time, "direction": sig.direction,
                                 "entry_time": candles.index[i], "entry": O[i], "stop": sig.stop,
                                 "target": sig.target, "rr": sig.direction * (sig.target - O[i]) / risk_oz,
                                 "units_oz": risk_eur * acc["eurusd"] / (risk_oz + cost),
                                 "risk_eur": risk_eur, "reason": sig.reason, "label": p.get("label")})
            elif ncfg["trade_update"]["enabled"]:
                state.queue(f"trade|{tid}|niet_gevuld", "trade",
                            msg.trade_update({"strategy": p["strategy"], "result": "niet_gevuld"}, cfg))
            changed = True
        state.pending = still_pending

        # b. open trades afhandelen
        for _, row in state.open_trades().iterrows():
            tr = trade_to_open(row)
            ex = check_exit(tr, O[i], H[i], L[i], C[i], 0)
            if ex is None:
                continue
            exit_px, result = ex
            d = tr.signal.direction
            r = (d * (exit_px - tr.entry) - cost) / (tr.risk_oz + cost)
            pnl = r * tr.risk_eur
            eq_after = state.equity(row["strategy"], acc["start_equity_eur"]) + pnl
            state.update_trade(row["id"], status="closed", exit_time=t_close, exit=exit_px, result=result,
                               r=r, pnl_eur=pnl, equity_after=eq_after)
            if ncfg["trade_update"]["enabled"]:
                state.queue(f"trade|{row['id']}|{result}", "trade",
                            msg.trade_update({**row.to_dict(), "exit": exit_px, "result": result, "r": r,
                                              "pnl_eur": pnl, "equity_after": eq_after, "exit_time": t_close}, cfg))
            changed = True

        # c. nieuwe signalen
        view = MarketView(market, i)
        for sid, s in strategies.items():
            busy = len(state.open_trades(sid)) + sum(1 for p in state.pending if p["strategy"] == sid)
            if busy >= acc["max_open_per_strategy"]:
                continue
            sigs = s["instance"].generate_signals(view)
            if not sigs:
                continue
            sig = sigs[0]
            sig.strategy = sid
            state.pending.append({"strategy": sid, "signal_time": t_close.isoformat(), "direction": sig.direction,
                                  "stop": sig.stop, "target": sig.target, "reason": sig.reason,
                                  "min_rr": sig.min_rr, "label": s.get("label", s["status"]),
                                  "stop_dist": sig.meta.get("stop_dist"), "rr": sig.meta.get("rr")})
            if ncfg["signal"]["enabled"]:
                eq = state.equity(sid, acc["start_equity_eur"])
                risk_eur = eq * acc["risk_pct"] / 100
                risk_oz = sig.direction * (C[i] - sig.stop)
                units = risk_eur * acc["eurusd"] / (risk_oz + cost) if risk_oz > 0 else 0
                chart = None
                try:
                    if not ncfg["signal"].get("chart", True):
                        raise RuntimeError("charts uit in config")
                    chart_dir = project_path("output/charts")
                    chart_dir.mkdir(parents=True, exist_ok=True)
                    zones = market.zones_at(s["instance"].zone_method or ncfg["zone_alert"]["method"], i)
                    chart = str(signal_chart(candles.iloc[:i + 1], zones, sig, C[i],
                                             chart_dir / f"{sid}_{t_close:%Y%m%d%H}.png"))
                except Exception as e:  # een chart mag de melding niet tegenhouden
                    if ncfg["signal"].get("chart", True):
                        log(f"  chart mislukt: {type(e).__name__}: {e}")
                state.queue(f"signal|{sid}|{t_close.isoformat()}", "signal",
                            msg.signal(sig, s, C[i], units, risk_eur, cfg, late=late), photo=chart)
            changed = True

        state.meta["last_processed"] = candles.index[i].isoformat()

    # ---- zone-alert (alleen op de laatste candle) ----
    zcfg = ncfg["zone_alert"]
    if zcfg["enabled"] and new_idx[-1] == len(candles) - 1:
        i = new_idx[-1]
        zones = market.zones_at(zcfg["method"], i)
        price, atr = C[i], market.features["atr"].iloc[i]
        history = [h for h in state.meta.get("zone_alerts", [])
                   if now - pd.Timestamp(h["time"]) < pd.Timedelta(hours=zcfg["cooldown_hours"])]
        for _, z in zones[zones["score"] >= zcfg["min_score"]].iterrows():
            dist = max(z["low"] - price, price - z["high"], 0) / atr
            if dist > zcfg["max_distance_atr"]:
                continue
            if any(h["low"] <= z["high"] and h["high"] >= z["low"] for h in history):
                continue   # deze zone (of een overlappende) kreeg al een melding binnen de cooldown
            history.append({"time": now.isoformat(), "low": z["low"], "high": z["high"]})
            state.queue(f"zone|{z['low']:.1f}|{market.close_time[i].isoformat()}", "zone",
                        msg.zone_alert(z, price, dist, market.close_time[i], cfg))
            changed = True
        state.meta["zone_alerts"] = history

    maybe_weekly(state, cfg, now, strategies, market)
    state.meta["last_run"] = now.isoformat()
    state.meta["last_price"] = float(C[-1])
    state.log_run(run_time=now, status="ok", last_candle=last_open, new_candles=len(new_idx),
                  latency_min=latency, message="")
    state.save()
    deliver(state, cfg, send, log)
    state.save()
    return {"changed": True, "status": "ok", "market": market}


def maybe_weekly(state: State, cfg, now, strategies, market) -> bool:
    """Weekoverzicht op zondagavond (Amsterdam-tijd), één keer per week."""
    wcfg = cfg["notify"]["weekly"]
    local = now.tz_convert(cfg["notify"]["timezone"])
    if not wcfg["enabled"] or local.weekday() != wcfg["weekday"] or local.hour < wcfg["hour_local"]:
        return False
    week = f"{local.isocalendar().year}-W{local.isocalendar().week:02d}"
    key = f"weekly|{week}"
    if key in state.sent or any(m["key"] == key for m in state.outbox):
        return False
    closed = state.closed_trades()
    week_ago = now - pd.Timedelta(days=7)
    wk = closed[pd.to_datetime(closed["exit_time"], utc=True) >= week_ago]
    per = []
    for sid, s in strategies.items():
        mine = closed[closed["strategy"] == sid]
        per.append({"strategy": sid, "status": s["status"], "n": len(mine),
                    "avg_r": float(mine["r"].astype(float).mean()) if len(mine) else 0.0,
                    "warning": deviation_warning(s, mine, cfg["paper"])})
    zones, price = [], state.meta.get("last_price", float("nan"))
    try:
        from goldsignals.market import load_candles
        c = load_candles(cfg)
        r = zones_as_of(c, c.index[-1] + pd.Timedelta(hours=1), cfg, cfg["notify"]["zone_alert"]["method"])
        price = r.price
        near = r.merged[r.merged["distance_pct"].abs() <= 3].sort_values("score", ascending=False).head(4)
        zones = near.to_dict("records")
    except Exception:
        pass
    summary = {"week": week, "n_closed": len(wk), "total_r": float(wk["r"].astype(float).sum()) if len(wk) else 0.0,
               "pnl_eur": float(wk["pnl_eur"].astype(float).sum()) if len(wk) else 0.0,
               "n_open": len(state.open_trades()), "per_strategy": per, "price": price, "zones": zones}
    state.queue(key, "weekly", msg.weekly(summary, cfg))
    return True


def deliver(state: State, cfg, send: bool, log=print):
    """Verstuur de outbox. Mislukt er iets, dan blijft de melding staan voor de volgende run."""
    if not send:
        return
    from goldsignals.notify.telegram import TelegramError, send_message, send_photo
    for m in list(state.outbox):
        try:
            if m.get("photo") and Path(m["photo"]).exists():
                send_photo(m["photo"], m["text"])
            else:
                send_message(m["text"])
            state.mark_sent(m["key"])
        except TelegramError as e:
            log(f"  melding niet verstuurd ({m['kind']}): {e}")
            break
