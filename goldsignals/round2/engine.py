"""Ronde 2: uitvoering van signalen (zelfde regels als ronde 1, plus trailing en tijdstop).

- Signaal op het slot van candle i -> entry op de open van candle i+1.
- Initiële stop = entry -/+ stop_dist[i]. Target: vast niveau (target_level[i], moet aan de
  goede kant van de entry liggen, anders geen trade) of entry +/- target_r x risico.
- Vanaf de entry-candle: raakt een candle stop en target, dan telt de STOP. Opent een
  candle voorbij de stop, dan exit op die open.
- Trailing (chandelier): na het slot van elke candle wordt de stop
  max(stop, hoogste slot sinds entry - k x ATR) (short gespiegeld); geldt vanaf de
  volgende candle.
- Tijdstop: na `time_stop` candles exit op het slot.
- Max. 1 open positie. Trades die aan het einde van de data nog open zijn, sluiten op het
  laatste slot (result 'einde').
Per trade bewaren we winst en risico per ounce, zodat R bij 1x/2x/3x kosten zonder
nieuwe simulatie te berekenen is.
"""
import numpy as np
import pandas as pd

from goldsignals.round2.families import Signals

COLUMNS = ["entry_i", "exit_i", "direction", "entry", "stop0", "exit", "result", "pnl_oz", "risk_oz"]


def simulate(b: pd.DataFrame, s: Signals, entries: np.ndarray = None, last_entry_i: int = None) -> pd.DataFrame:
    """entries: optioneel een eigen entry-array (random baseline) in plaats van s.entry.
    last_entry_i: geen nieuwe entries meer na deze candle (open trades lopen door)."""
    O, H, L, C = (b[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    n = len(C)
    ent = s.entry if entries is None else entries
    last_entry_i = n - 2 if last_entry_i is None else min(last_entry_i, n - 2)
    trades = []
    pos = 0
    i = 0
    while i < n:
        if pos == 0:
            # zoek het volgende signaal (snel, zonder per-candle Python-werk als er niets is)
            nz = np.flatnonzero(ent[i:last_entry_i + 1])
            if len(nz) == 0:
                break
            i = i + int(nz[0])
            d = int(ent[i])
            sd = s.stop_dist[i]
            j = i + 1                                     # entry-candle
            entry = O[j]
            if not np.isfinite(sd) or sd <= 0:
                i += 1
                continue
            stop = entry - d * sd
            target = np.nan
            if s.target_level is not None:
                target = s.target_level[i]
                if not np.isfinite(target) or d * (target - entry) <= 0:
                    i += 1                                # target al voorbij: exit-regel bestaat niet
                    continue
            elif s.target_r is not None:
                target = entry + d * s.target_r * sd
            pos, entry_i, stop0, best = d, j, stop, entry   # trailing: "hoogste slot sinds entry", minimaal de entry
            i = j
            continue
        # positie open: candle i afhandelen
        d = pos
        stop_hit = L[i] <= stop if d == 1 else H[i] >= stop
        tp_hit = np.isfinite(target) and (H[i] >= target if d == 1 else L[i] <= target)
        exit_px, result = None, None
        if stop_hit:
            exit_px = min(O[i], stop) if d == 1 else max(O[i], stop)
            result = "sl" if not s.trail_k else "trail"
        elif tp_hit:
            exit_px, result = target, "tp"
        elif s.time_stop is not None and i - entry_i + 1 >= s.time_stop:
            exit_px, result = C[i], "tijd"
        elif i == n - 1:
            exit_px, result = C[i], "einde"
        if exit_px is not None:
            trades.append((entry_i, i, d, entry, stop0, exit_px, result, d * (exit_px - entry), d * (entry - stop0)))
            pos = 0
            continue        # zoals ronde 1: op het slot van de exit-candle mag al een nieuw signaal komen
        if s.trail_k:
            best = max(best, C[i]) if d == 1 else min(best, C[i])
            new = best - d * s.trail_k * s.trail_atr[i]
            if np.isfinite(new):
                stop = max(stop, new) if d == 1 else min(stop, new)
        i += 1
    return pd.DataFrame(trades, columns=COLUMNS)


def with_costs(t: pd.DataFrame, cost: float) -> np.ndarray:
    """R netto bij kosten `cost` USD/oz per round trip. Een stop (zonder gat) = precies -1R."""
    return ((t["pnl_oz"] - cost) / (t["risk_oz"] + cost)).to_numpy()
