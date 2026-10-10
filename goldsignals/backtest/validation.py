"""Statusregels: rejected / candidate / validated (zie research/PLAN.md, deel B).

candidate:
- minstens 100 trades in de walk-forward TEST-vensters samen (out-of-sample);
- gemiddelde R na kosten > 0 over die test-vensters samen;
- niet gedragen door één jaar: zonder het beste kalenderjaar is de totale R nog > 0.

validated (bovenop candidate):
- hold-out één keer geopend: >= 30 trades en gemiddelde R > 0 (minder trades: blijft candidate);
- deflated Sharpe ratio >= drempel (correctie voor het aantal geprobeerde varianten);
- niet afhankelijk van long-only bias: gemiddeld beter dan willekeurige entries met
  dezelfde richting (zie excess_vs_random).
"""
import math

import numpy as np
import pandas as pd
from scipy.stats import kurtosis, norm, skew

from goldsignals.backtest.metrics import r_by_year

EULER_GAMMA = 0.5772156649


def deflated_sharpe(r: np.ndarray, n_trials: int, trial_sharpes: np.ndarray) -> dict:
    """Deflated Sharpe Ratio (Bailey & López de Prado, 2014), per trade.

    In gewone taal: als je 400 varianten probeert, ziet de beste er ook bij puur toeval
    goed uit. We schatten eerst hoe hoog de Sharpe van de beste van N toevalsvarianten
    zou zijn (SR0, uit het aantal trials en hoe sterk hun Sharpes uiteenlopen). Daarna:
    hoe zeker is het dat de echte Sharpe boven die SR0 ligt, rekening houdend met het
    aantal trades en scheve/dikstaartige uitkomsten? DSR = die zekerheid (0-1).
    """
    r = np.asarray(r, float)
    n = len(r)
    if n < 3 or r.std(ddof=1) == 0:
        return {"dsr": np.nan, "sr": np.nan, "sr0": np.nan}
    sr = r.mean() / r.std(ddof=1)
    ts = np.asarray(trial_sharpes, float)
    ts = ts[np.isfinite(ts)]
    var = ts.var(ddof=1) if len(ts) > 1 else 0.0
    N = max(int(n_trials), 2)
    sr0 = math.sqrt(var) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / N) + EULER_GAMMA * norm.ppf(1 - 1 / (N * math.e)))
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    denom = math.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))
    z = (sr - sr0) * math.sqrt(n - 1) / denom
    return {"dsr": float(norm.cdf(z)), "sr": float(sr), "sr0": float(sr0)}


def not_single_year(trades: pd.DataFrame) -> tuple:
    """Totale R zonder het beste jaar. > 0 betekent: niet gedragen door één jaar."""
    by = r_by_year(trades)
    if not by:
        return False, np.nan
    best = max(by, key=lambda y: by[y]["total_r"])
    rest = sum(v["total_r"] for y, v in by.items() if y != best)
    return rest > 0, float(rest)


def excess_vs_random(trades: pd.DataFrame, random_trades: pd.DataFrame) -> float:
    """Gemiddelde R boven willekeurige entries in DEZELFDE richting en periode.
    Goud steeg in deze jaren sterk; een long-strategie wint dan al 'gratis'. Dit haalt
    dat effect eruit: excess = gemiddelde van (R_trade - gemiddelde random-R voor die richting)."""
    if trades.empty or random_trades.empty:
        return np.nan
    base = random_trades.groupby("direction")["r"].mean().to_dict()
    b = trades["direction"].map(base)
    return float((trades["r"] - b).mean())


def decide_status(oos: pd.DataFrame, vcfg: dict, holdout: dict = None, dsr: float = np.nan,
                  excess: float = np.nan) -> dict:
    """Bepaal de status en geef de redenen erbij (voor het leaderboard)."""
    reasons = []
    n, avg = len(oos), (oos["r"].mean() if len(oos) else np.nan)
    single_ok, rest_r = not_single_year(oos)
    cand = True
    if n < vcfg["min_trades_research"]:
        cand = False
        reasons.append(f"te weinig trades ({n} < {vcfg['min_trades_research']})")
    if not (avg > 0):
        cand = False
        reasons.append(f"gemiddelde R na kosten niet positief ({avg:+.3f})")
    if not single_ok:
        cand = False
        reasons.append(f"zonder beste jaar niet positief ({rest_r:+.1f}R)")
    if not cand:
        return {"status": "rejected", "reasons": reasons}

    status, reasons = "candidate", ["voldoet aan candidate-eisen"]
    if holdout is None:
        reasons.append("hold-out nog niet geopend")
        return {"status": status, "reasons": reasons}
    if holdout.get("burned"):
        reasons.append("hold-out verbrand (strategie aangepast na openen)")
        return {"status": status, "reasons": reasons}
    ok = True
    if holdout["n"] < vcfg["min_trades_holdout"]:
        ok = False
        reasons.append(f"hold-out te weinig trades ({holdout['n']} < {vcfg['min_trades_holdout']})")
    elif not (holdout["avg_r"] > 0):
        ok = False
        reasons.append(f"hold-out niet positief ({holdout['avg_r']:+.3f}R)")
    if not (dsr >= vcfg["dsr_threshold"]):
        ok = False
        reasons.append(f"deflated Sharpe te laag ({dsr:.2f} < {vcfg['dsr_threshold']})")
    if not (excess > 0):
        ok = False
        reasons.append(f"niet beter dan willekeurige entries in dezelfde richting ({excess:+.3f}R)")
    if ok:
        return {"status": "validated", "reasons": ["alle eisen gehaald, incl. hold-out"]}
    return {"status": status, "reasons": reasons}
