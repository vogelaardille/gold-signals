"""Backtest-engine: speelt een strategie candle voor candle af met fictief geld.

Regels (dezelfde als in paper trading, zie paper/):
1. Een strategie kijkt op het SLUITmoment van een 1h-candle (generate_signals).
2. Entry op de OPEN van de volgende candle. Klopt het signaal dan niet meer (open al
   voorbij stop of target, of R:R onder het minimum), dan geen trade.
3. Stop en target worden per candle gecontroleerd, vanaf de entry-candle. Raakt een
   candle beide, dan telt de STOP eerst (we weten niet wat binnen het uur eerst kwam,
   dus we nemen het slechtste). Opent een candle al voorbij de stop (gat), dan is de
   exit die open.
4. Kosten per ounce per round trip = spread + 2 x slippage (x kosten-multiplier).
5. Positiegrootte: risico = risk_pct van de equity bij entry. Aantal oz =
   risico / (afstand tot stop + kosten), zodat een stop (incl. kosten) precies -1R is.
   Winst/verlies in euro = R x risico. De EUR/USD-koers in config wordt alleen gebruikt
   om het aantal ounces te tonen.
6. Max aantal open trades per strategie (config account.max_open_per_strategy).
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

from goldsignals.strategies.base import MarketView, Signal

TRADE_COLUMNS = ["strategy", "signal_time", "direction", "entry_time", "entry", "stop", "target",
                 "rr", "units_oz", "risk_eur", "exit_time", "exit", "result", "r", "r_gross",
                 "pnl_eur", "equity_after", "reason"]


def cost_per_oz(cfg: dict, mult: float = 1.0) -> float:
    c = cfg["costs"]
    return mult * (c["spread_usd"] + 2 * c["slippage_usd"])


@dataclass
class OpenTrade:
    signal: Signal
    entry_i: int
    entry: float
    units_oz: float
    risk_eur: float

    @property
    def risk_oz(self):
        return self.signal.direction * (self.entry - self.signal.stop)


def try_fill(sig: Signal, open_px: float) -> bool:
    """Is het signaal op deze open-prijs nog geldig?"""
    d = sig.direction
    risk = d * (open_px - sig.stop)
    reward = d * (sig.target - open_px)
    if risk <= 0 or reward <= 0:
        return False
    return reward / risk >= sig.min_rr - 1e-9


def check_exit(tr: OpenTrade, o: float, h: float, l: float, c: float, bars_held: int):
    """Exit op deze candle? Geeft (exitprijs, reden) of None. SL gaat voor TP."""
    s, d = tr.signal, tr.signal.direction
    stop_hit = l <= s.stop if d == 1 else h >= s.stop
    tp_hit = h >= s.target if d == 1 else l <= s.target
    if stop_hit:
        # Gat voorbij de stop: exit op de open (slechter dan de stop)
        px = min(o, s.stop) if d == 1 else max(o, s.stop)
        return px, "sl"
    if tp_hit:
        return s.target, "tp"
    if s.max_hold_bars is not None and bars_held >= s.max_hold_bars:
        return c, "tijd"
    return None


def close_trade(tr: OpenTrade, exit_i: int, exit_px: float, result: str, market, cost: float,
                equity: float) -> dict:
    s, d = tr.signal, tr.signal.direction
    pnl_oz = d * (exit_px - tr.entry)
    r = (pnl_oz - cost) / (tr.risk_oz + cost)
    pnl_eur = r * tr.risk_eur
    return {
        "strategy": s.strategy, "signal_time": s.time, "direction": d,
        "entry_time": market.candles.index[tr.entry_i], "entry": tr.entry, "stop": s.stop,
        "target": s.target, "rr": d * (s.target - tr.entry) / tr.risk_oz,
        "units_oz": tr.units_oz, "risk_eur": tr.risk_eur,
        "exit_time": market.close_time[exit_i], "exit": exit_px, "result": result,
        "r": r, "r_gross": pnl_oz / tr.risk_oz, "pnl_eur": pnl_eur,
        "equity_after": equity + pnl_eur, "reason": s.reason,
    }


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    signals: int


def run_backtest(strategy, market, i_start: int, i_end: int, cfg: dict, cost_mult: float = 1.0,
                 i_hard_end: int = None, equity: float = None) -> BacktestResult:
    """Speel candles i_start..i_end af. Na i_end geen nieuwe entries meer, maar open trades
    lopen door tot hun exit of uiterlijk i_hard_end (default: i_end; daar sluiten op de slotkoers)."""
    acc = cfg["account"]
    equity = acc["start_equity_eur"] if equity is None else equity
    max_open = acc["max_open_per_strategy"]
    cost = cost_per_oz(cfg, cost_mult)
    i_hard_end = i_end if i_hard_end is None else i_hard_end
    O, H, L, C = (market.array(k) for k in ("open", "high", "low", "close"))

    trades, open_trades, pending = [], [], []
    n_signals = 0
    for i in range(i_start, i_hard_end + 1):
        # 1. Openstaande signalen vullen op de open van deze candle
        for sig in pending:
            if len(open_trades) < max_open and try_fill(sig, O[i]):
                risk_eur = equity * acc["risk_pct"] / 100
                risk_oz = sig.direction * (O[i] - sig.stop)
                units = risk_eur * acc["eurusd"] / (risk_oz + cost)
                open_trades.append(OpenTrade(sig, i, O[i], units, risk_eur))
        pending = []

        # 2. Open trades afhandelen op deze candle
        still_open = []
        for tr in open_trades:
            ex = check_exit(tr, O[i], H[i], L[i], C[i], i - tr.entry_i + 1)
            if ex is None and i == i_hard_end:
                ex = (C[i], "einde")
            if ex is None:
                still_open.append(tr)
            else:
                row = close_trade(tr, i, ex[0], ex[1], market, cost, equity)
                equity = row["equity_after"]
                trades.append(row)
        open_trades = still_open

        # 3. Nieuwe signalen op de slotkoers
        if i <= i_end and i < i_hard_end and len(open_trades) < max_open:
            sigs = strategy.generate_signals(MarketView(market, i))
            n_signals += len(sigs)
            pending = sigs[: max_open - len(open_trades)]

    return BacktestResult(pd.DataFrame(trades, columns=TRADE_COLUMNS), n_signals)
