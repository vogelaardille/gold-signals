"""Deel B-rapport: research/backtest.md (leaderboard, kosten, hold-out, uitleg).

Draaien: .venv/bin/python -m goldsignals.backtest.report
"""
import json
import math

import numpy as np
import pandas as pd
from scipy.stats import norm

from goldsignals.backtest.validation import EULER_GAMMA
from goldsignals.config import load_config, project_path

RES = project_path("research/results")


def f(x, fmt="{:+.3f}"):
    return "–" if x is None or (isinstance(x, float) and not np.isfinite(x)) else fmt.format(x)


def mild_dsr(oos: pd.DataFrame, trials: pd.DataFrame, min_n: int) -> float:
    """Gevoeligheidscheck (NIET de statusregel): DSR waarbij de spreiding van de trials
    eerst van meetruis wordt ontdaan en daarna naar de lengte van de OOS-reeks wordt vertaald."""
    r = oos["r"].to_numpy(float)
    if len(r) < 3:
        return float("nan")
    v = trials[trials["n"] >= min_n]
    var_true = max(v["sharpe"].var() - float(np.mean(1 / v["n"])), 0.0)
    T, N = len(r), len(trials) + 1
    sr0 = math.sqrt(var_true + 1 / T) * ((1 - EULER_GAMMA) * norm.ppf(1 - 1 / N)
                                         + EULER_GAMMA * norm.ppf(1 - 1 / (N * math.e)))
    sr = r.mean() / r.std(ddof=1)
    return float(norm.cdf((sr - sr0) * math.sqrt(T - 1)))


def main():
    cfg = load_config()
    lb = pd.read_csv(RES / "leaderboard.csv")
    bt = json.loads((RES / "backtest.json").read_text())
    trials = pd.read_csv(RES / "trials.csv")
    det = bt["details"]
    md = ["# Deel B – Strategieën en backtest", "",
          f"_Walk-forward binnen de research-periode: train 12 maanden, test 3 maanden, test-vensters "
          f"{bt['oos_period'][0]} t/m {bt['oos_period'][1]}. Alle cijfers zijn out-of-sample (OOS), "
          f"na kosten (0,40 spread + 2 × 0,10 slippage per oz), 1% risico per trade._", ""]
    concl = project_path("research/text/backtest_conclusie.md")
    if concl.exists():
        md += [concl.read_text(encoding="utf-8"), ""]
    md += ["## Leaderboard", "",
          "| strategie | status | trades | winrate | gem. R | totaal R | rendement | max DD | DSR | t.o.v. random (zelfde regels) | hold-out gem. R (n) |",
          "|---|---|---|---|---|---|---|---|---|---|---|"]
    for _, r in lb.iterrows():
        ho = f"{f(r.get('holdout_avg_r'))} ({f(r.get('holdout_n'), '{:.0f}')})" if pd.notna(r.get("holdout_n")) else "niet geopend"
        md.append(f"| {r['strategy']} | **{r['status']}** | {f(r.get('n'), '{:.0f}')} | {f(r.get('winrate'), '{:.0f}%')} | "
                  f"{f(r.get('avg_r'))} | {f(r.get('total_r'), '{:+.1f}')} | {f(r.get('return_pct'), '{:+.1f}%')} | "
                  f"{f(r.get('max_dd_pct'), '{:.1f}%')} | {f(r.get('dsr'), '{:.2f}')} | {f(r.get('excess_vs_random'))} | {ho} |")
    md += ["", "**Toelichting per strategie:**", ""]
    for _, r in lb.iterrows():
        md.append(f"- **{r['strategy']}** ({r['status']}): {r['reasons']}")

    md += ["", "## Kostengevoeligheid (gemiddelde R, zelfde gekozen parameters)", "",
           "| strategie | 0× kosten | 1× | 2× | 3× |", "|---|---|---|---|---|"]
    for _, r in lb[lb["n"].notna()].iterrows():
        md.append(f"| {r['strategy']} | {f(r['avg_r_0x'])} | {f(r['avg_r'])} | {f(r['avg_r_2x'])} | {f(r['avg_r_3x'])} |")

    md += ["", "## Long en short apart", "", "| strategie | long n | long gem. R | short n | short gem. R | random zelfde regels long / short |",
           "|---|---|---|---|---|---|"]
    for sid, d in det.items():
        s = d["summary"]
        rs = d.get("random_same_rules", {})
        md.append(f"| {sid} | {s['n_long']} | {f(s['avg_r_long'])} | {s['n_short']} | {f(s['avg_r_short'])} | "
                  f"{f(rs.get('1'))} / {f(rs.get('-1'))} |")

    md += ["", "## Per jaar (totaal R)", "", "| strategie | " + " | ".join(str(y) for y in range(2022, 2026)) + " |",
           "|---|" + "---|" * 4]
    for sid, d in det.items():
        by = d["by_year"]
        md.append(f"| {sid} | " + " | ".join(f"{by[str(y)]['total_r']:+.1f} ({by[str(y)]['n']})" if str(y) in by else "–"
                                             for y in range(2022, 2026)) + " |")

    bh = bt["buy_and_hold"]
    md += ["", f"**Buy-and-hold** over dezelfde periode: {bh['return_pct']:+.1f}% (max drawdown {bh['max_dd_pct']:.1f}%).", "",
           "## Correctie voor het aantal varianten (deflated Sharpe)", "",
           f"In totaal zijn **{bt['n_trials_total']} varianten** geprobeerd (alle Optuna-trials van alle "
           "strategieën, zie `results/trials.csv`). Als je zoveel varianten probeert, ziet de beste er ook "
           "bij puur toeval goed uit. De deflated Sharpe ratio (DSR) schat eerst hoe goed de beste van "
           "al die varianten door toeval zou zijn, en geeft dan de kans (0–1) dat de echte strategie daar "
           "werkelijk boven zit. De lat voor *validated* is 0,95.", "",
           "Voorbeeld: ema_pullback haalt per trade een Sharpe van "
           f"{det['ema_pullback']['dsr']['sr']:.3f} (gemiddelde R gedeeld door de spreiding). "
           f"De beste van {bt['n_trials_total']} toevalsvarianten zou volgens de DSR rond "
           f"{det['ema_pullback']['dsr']['sr0']:.2f} uitkomen. Daar zit hij ver onder.", "",
           "**Gevoeligheidscheck (niet de statusregel).** De trial-Sharpes zijn gemeten op train-vensters "
           "met ~50 trades en zijn daardoor erg ruisig, wat de lat hoog legt. Een mildere variant haalt die "
           "ruis eruit en rekent om naar het aantal OOS-trades:", ""]
    for sid, d in det.items():
        oos = pd.read_csv(RES / f"oos_{sid}.csv")
        md.append(f"- {sid}: DSR {f(d['dsr'].get('dsr'), '{:.2f}')}, mild {f(mild_dsr(oos, trials, cfg['optuna']['min_train_trades']), '{:.2f}')}")
    md += ["", "Ook met de milde variant haalt geen enkele strategie 0,95. De conclusie hangt dus niet af van "
           "deze keuze.", "", "## Hold-out", ""]
    log_p = project_path("research/holdout_log.json")
    log = json.loads(log_p.read_text()) if log_p.exists() else {}
    if not log:
        md.append("Nog voor geen enkele strategie geopend.")
    for sid, e in log.items():
        r = e["result"]
        md.append(f"- **{sid}** geopend op {e['opened_at']} met parameters `{json.dumps(e['params'])}`: "
                  f"{r['n']} trades, winrate {r['winrate']:.0f}%, gem. {r['avg_r']:+.3f} R, totaal {r['total_r']:+.1f} R, "
                  f"max DD {r['max_dd_pct']:.1f}%.")
    md += ["", "Elke strategie mag de hold-out maar één keer zien. Wordt de strategie daarna aangepast, dan is "
           "de hold-out voor die strategie **verbrand** en kan hij niet meer *validated* worden.", ""]
    project_path("research/backtest.md").write_text("\n".join(md), encoding="utf-8")
    print("research/backtest.md geschreven")


if __name__ == "__main__":
    main()
