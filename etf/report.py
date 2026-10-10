"""Rapport ronde 3: research/round3/report.md en report.html (+ figuren).

Leest alleen de uitkomsten in research/round3/results/ (de berekening zelf staat in etf/run.py
en etf/open_holdout.py). De uitleg staat hier als tekst met getallen uit die bestanden.
Draaien: .venv/bin/python -m etf.report
"""
import base64
import json
import re

import numpy as np
import pandas as pd

from etf import figures as fg
from etf import rules
from etf.data import ROOT, load_config, research_prices
from etf.portfolio import month_end_prices
from goldsignals.research.report import CSS, fix_lists

R3 = ROOT / "research/round3"
RES = R3 / "results"
FIG = R3 / "figures"
GH = "https://github.com/vogelaardille/gold-signals/blob/main/research/round3/"

NAMES = {"F1_N10": "F1 trendfilter (N=10)", "F2_k3_L12": "F2 dual momentum (k=3, L=12)",
         "F3_equal_weight_v10_w20": "F3 vol-target op EW (10%, 20 dagen)",
         "F3_sixty_forty_v10_w20": "F3 vol-target op 60/40 (10%, 20 dagen)"}
SHORT = {"F1_N10": "F1", "F2_k3_L12": "F2", "F3_equal_weight_v10_w20": "F3-EW", "F3_sixty_forty_v10_w20": "F3-60/40"}


# ----------------------------- opmaak -------------------------------------

def nl(x, d=1, sign=False):
    """Getal met decimale komma; '–' bij ontbrekend."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)):
        return "–"
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return s.replace(".", ",").replace("-", "−")


def pct(x, d=1, sign=False):
    return nl(x, d, sign) + "%"


def ci(c, d=2, unit=""):
    return f"{nl(c['est'], d, True)}{unit} [{nl(c['lo'], d, True)}; {nl(c['hi'], d, True)}]"


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] +
                     ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def mdd_dates(r: pd.Series) -> tuple:
    eq = (1 + r).cumprod()
    eq = pd.concat([pd.Series([1.0], index=[r.index[0] - pd.offsets.MonthBegin(1)]), eq])
    dd = eq / eq.cummax() - 1
    t = dd.idxmin()
    pk = eq[:t].idxmax()
    rec = eq[t:][eq[t:] >= eq[pk]]
    month = lambda d: ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"][d.month - 1] + f" {d.year}"
    return month(pk), month(t), (month(rec.index[0]) if len(rec) else "niet hersteld")


def yes(b):
    return "ja" if b else ("n.v.t." if b is None else "**nee**")


# ----------------------------- figuren ------------------------------------

def make_figures(res, cfg):
    FIG.mkdir(parents=True, exist_ok=True)
    m = pd.read_csv(RES / "monthly_returns.csv", index_col=0, parse_dates=True)
    fg.equity_and_drawdown(m, ["EW", "F1_N10", "F2_k3_L12", "F3_equal_weight_v10_w20"], FIG / "equity_ew.png",
                           "Gelijk-gewicht-universum, 2005–2020 (na 0,10% kosten)")
    fg.equity_and_drawdown(m, ["60/40", "F3_sixty_forty_v10_w20|matched", "F3_sixty_forty_v10_w20"], FIG / "equity_6040.png",
                           "60/40 SPY/IEF, 2005–2020 (na 0,10% kosten)")
    grid = pd.read_csv(RES / "grid.csv")
    fg.grid_heatmaps(grid, res["primary"], FIG / "grid.png")
    rolls = {pid: pd.read_csv(RES / f"rolling_{pid}.csv") for pid in res["primary"]}
    fg.rolling(rolls, FIG / "rolling.png")
    fg.random_timing(res["results"], FIG / "random_timing.png")
    fg.per_asset(res["per_asset_F1"], res["results"]["F3_equal_weight_v10_w20"]["per_asset"], FIG / "per_asset.png")
    w1 = pd.read_csv(RES / "weights_F1_N10.csv", index_col=0, parse_dates=True)
    me = month_end_prices(research_prices(cfg))
    av = rules.available(me, cfg["min_month_ends"])
    fg.f1_onoff(w1, av, "2007-06-01", "2009-12-31", FIG / "f1_2007_2009.png")
    series = {}
    for blk, name in (("P", "P (fondsen)"), ("research", "research"), ("H3", "H3")):
        if blk == "research":
            w3 = pd.read_csv(RES / "weights_F3_sixty_forty_v10_w20.csv", index_col=0, parse_dates=True).sum(axis=1)
            s = w3
        else:
            f = RES / f"holdout_{blk}_F3_sixty_forty_v10_w20.json"
            if not f.exists():
                continue
            e = json.loads(f.read_text())["cost_0.001"]["exposure_by_month"]
            s = pd.Series(e)
            s.index = pd.to_datetime(s.index)
        s.index = s.index + pd.offsets.MonthBegin(1)        # gehouden in de maand ná het signaal
        series[name] = s
    lo = {"P (fondsen)": ("1996-01-01", "2005-01-01"), "research": ("2005-01-01", "2021-01-01"), "H3": ("2021-01-01", "2026-10-01")}
    series = {k: v[(v.index >= lo[k][0]) & (v.index < lo[k][1])] for k, v in series.items()}
    fg.exposure_timeline(series, FIG / "exposure_6040.png")


# ----------------------------- tekst --------------------------------------

def build(res, cfg) -> str:
    P = res["results"]
    m = pd.read_csv(RES / "monthly_returns.csv", index_col=0, parse_dates=True)
    b = res["baselines"]
    f1, f2, f3e, f3s = (P[k] for k in ("F1_N10", "F2_k3_L12", "F3_equal_weight_v10_w20", "F3_sixty_forty_v10_w20"))
    h3 = json.loads((RES / "holdout_H3_F3_sixty_forty_v10_w20.json").read_text())
    pp = json.loads((RES / "holdout_P_F3_sixty_forty_v10_w20.json").read_text())
    log = json.loads((R3 / "holdout_log.json").read_text())
    h3c, ppc = h3["cost_0.001"], pp["cost_0.001"]
    w1 = pd.read_csv(RES / "weights_F1_N10.csv", index_col=0, parse_dates=True)
    w3 = pd.read_csv(RES / "weights_F3_sixty_forty_v10_w20.csv", index_col=0, parse_dates=True)
    on_sep08 = [a for a in w1.columns if w1.loc["2008-09-30", a] > 0]
    me = month_end_prices(research_prices(cfg))
    oct08 = (me.pct_change().loc["2008-10"].iloc[0] * 100)
    dist_sep08 = ((me / me.rolling(10).mean() - 1) * 100).loc["2008-09"].iloc[0]
    e_sep08 = float(w3.loc["2008-09-30"].sum())
    ew_dd, sf_dd, f1_dd, f3s_dd = (mdd_dates(m[c]) for c in ("EW", "60/40", "F1_N10", "F3_sixty_forty_v10_w20"))
    mo = lambda c, ym: float(m[c][ym].iloc[0] * 100)
    yr = lambda c, y: float(((1 + m[c][str(y)]).prod() - 1) * 100)
    n_h3 = sum(1 for e in log if e["block"] == "H3")
    n_p = sum(1 for e in log if e["block"] == "P")
    e22 = {k: v for k, v in h3c["exposure_by_month"].items() if k.startswith("2022")}
    mon22 = {k: v for k, v in h3c["monthly"].items() if k.startswith("2022")}
    y22 = (np.prod([1 + v[0] for v in mon22.values()]) - 1) * 100, (np.prod([1 + v[1] for v in mon22.values()]) - 1) * 100
    p_years = ppc["strat"]["years"], ppc["base"]["years"]
    ep = pd.Series(ppc["exposure_by_month"])
    share_p = float((ep.iloc[:-1] < 0.999).mean())
    share_r = float((w3.sum(axis=1).iloc[:-1] < 0.999).mean())
    md = []
    A = md.append

    A("# Ronde 3: lage-frequentie regels op een gespreid ETF-universum")
    A("")
    A(f"_Research 2005-01 – 2020-12 (192 maanden), 9 US-ETF's, signaal op het maandslot en uitvoering op het slot van de eerste "
      f"handelsdag daarna, kosten 0,10% van het verhandelde bedrag. Opzet vooraf vastgelegd in [PLAN3.md](PLAN3.md). "
      f"25 trials. Hold-out H3 (2021-01 – 2026-09) {n_h3}× geopend, pre-sample P (1996–2004) {n_p}× geopend, beide alleen voor "
      f"de enige candidate. Alleen onderzoek: geen paper trading, geen Telegram, geen echt geld._")
    A("")
    A("## Oordeel in gewone taal")
    A("")
    A("**Kort: geen van de regels is aantoonbaar beter dan gewoon gespreid beleggen. Eén regel geeft een zwakke, "
      "onbevestigde aanwijzing.**")
    A("")
    A(f"- **Volgens de vooraf vastgelegde regels (PLAN3 §9):** (c) *beter* voor één regel, volatility targeting op 60/40 "
      f"(F3-60/40), en (a) *geen verbetering* voor de andere drie. **Niets is validated.**")
    A(f"- **Hoe zeker: laag.** F3-60/40 verbeterde in research de Sharpe met {nl(f3s['ci']['sharpe']['est'], 2, True)} en "
      f"verkleinde de maximale daling van {pct(f3s['summary']['base']['mdd'])} naar {pct(f3s['summary']['strat']['mdd'])}, "
      f"bij een rendement dat {nl(f3s['summary']['base']['cagr'] - f3s['summary']['strat']['cagr'], 1)} procentpunt per jaar "
      f"lager lag. In de praktijk is dat dus vooral (b): bijna hetzelfde rendement met een kleinere daling.")
    A("  - Maar:")
    A(f"    - in H3 (2021–2026) was het voordeel klein: {nl(h3c['sharpe'], 2, True)} Sharpe;")
    A(f"    - in de pre-sample 1996–2004 was het er niet: {nl(ppc['sharpe'], 2, True)} Sharpe, en de daling was "
      f"{nl(-ppc['mdd'], 1)} procentpunt groter dan bij een vaste mix met evenveel cash;")
    A(f"    - na correctie voor 25 geprobeerde regels is het verschil niet significant (p = "
      f"{nl(f3s['reality_check']['sharpe']['p'], 2)} voor Sharpe, {nl(f3s['reality_check']['mdd']['p'], 2)} voor de daling);")
    A(f"    - voor een belegger in euro's verdwijnt het voordeel grotendeels (Sharpe {nl(f3s['eur']['usd_cash_converted']['sharpe'], 2, True)} "
      f"tot {nl(f3s['eur']['cash_in_eur']['sharpe'], 2, True)}).")
    A("")
    A("**Wat werkt (een beetje, onzeker)**")
    A(f"- **Volatility targeting op 60/40:** minder beleggen als de markt onrustig is. Dat hielp in 2008 duidelijk (oktober 2008: "
      f"{pct(mo('F3_sixty_forty_v10_w20', '2008-10'), 1, True)} tegen {pct(mo('60/40', '2008-10'), 1, True)} voor 60/40) en in "
      f"2022. Het effect komt vrijwel helemaal uit het aandelendeel.")
    A(f"  - Keerzijde: in 2020 schaalde hij pas ná de crash terug (op het slot van maart maar 19% belegd, dus in april vooral cash) en miste een deel van het "
      f"herstel: 2020 {pct(yr('F3_sixty_forty_v10_w20', 2020), 1, True)} tegen {pct(yr('60/40', 2020), 1, True)}.")
    A("")
    A("**Wat niet werkt**")
    A(f"- **Dual momentum (F2):** slechter dan gelijk gewicht (Sharpe {nl(f2['ci']['sharpe']['est'], 2, True)}), met veel meer "
      f"handel ({pct(f2['summary']['strat']['turnover_py'] * 100, 0)} van de portefeuille per jaar).")
    A(f"- **Volatility targeting op gelijk gewicht (F3-EW):** een kleinere daling, maar te onzeker "
      f"(Sharpe {ci(f3e['ci']['sharpe'])}).")
    A("")
    A("**Wat opvallend maar niet stabiel is**")
    A(f"- **Trendfilter (F1, N = 10):** de grootste daling zakte van {pct(b['EW']['mdd'])} (gelijk gewicht) naar "
      f"{pct(f1['summary']['strat']['mdd'])}. Dat is ook {nl(f1['ci']['mdd']['est'], 1)} procentpunt beter dan een vaste mix met "
      f"dezelfde tijd in de markt, en het overleeft zelfs de correctie voor 25 trials (p = "
      f"{nl(f1['reality_check']['mdd']['p'], 3)}).")
    A(f"  - **Maar dat komt vrijwel helemaal uit één crisis (2008).** In 2010–2014 en 2015–2020 was het voordeel er niet, en het "
      f"rendement lag {nl(b['EW']['cagr'] - f1['summary']['strat']['cagr'], 1)} procentpunt per jaar lager.")
    A("  - Volgens de vooraf vastgelegde regel (stabiel in ≥ 2 van 3 subperiodes) is F1 daarom **rejected**.")
    A("  - Eerlijk gezegd: een trendfilter is in de eerste plaats een verzekering tegen lange crashes, en die komen zelden voor. "
      "Met 16 jaar data, waarin maar één echte crash zat, is dat niet te bewijzen en ook niet uit te sluiten.")
    A("")
    A("**Wat onzeker blijft**")
    A(f"- Met 16 jaar maanddata kun je alleen grote verschillen aantonen. Een Sharpe-verbetering kleiner dan ongeveer "
      f"{nl(f3s['power']['sharpe']['mde'], 2)} (F3-60/40) tot {nl(f2['power']['sharpe']['mde'], 2)} (F2) blijft onzichtbaar. "
      f"In de literatuur gaat het om +0,1 tot +0,3.")
    A("- De resultaten hangen sterk af van twee crises (2008 en 2020). Een volgende crisis kan heel anders verlopen, "
      "bijvoorbeeld als aandelen en obligaties samen dalen, zoals in 2022.")
    A("")

    # ---------------- begrippen ----------------
    A("## Begrippen, uitgelegd met de data")
    A("")
    A(f"- **Maximale daling (MDD):** het grootste verlies vanaf een top, gemeten op maandsloten.")
    A(f"  - *Voorbeeld:* gelijk gewicht over de ETF's stond eind {ew_dd[0]} op een top, zakte tot eind {ew_dd[1]} "
      f"{pct(-b['EW']['mdd'])}, en was pas in {ew_dd[2]} weer terug.")
    A(f"  - Gemeten per dag was de daling nog groter: {pct(b['EW']['mdd_daily'])}.")
    A(f"- **Sharpe:** rendement *boven cash* (T-bills) per eenheid beweeglijkheid, per jaar.")
    A(f"  - *Voorbeeld:* 60/40 had {pct(b['60/40']['cagr'])} per jaar, met een beweeglijkheid (volatiliteit) van "
      f"{pct(b['60/40']['vol'])}. Na aftrek van het cashrendement levert dat een Sharpe van {nl(b['60/40']['sharpe'], 2)} op.")
    A("  - Een Sharpe-verschil van +0,10 betekent: bij dezelfde volatiliteit van bijvoorbeeld 8% per jaar levert de regel "
      "0,8 procentpunt per jaar meer op (0,10 × 8%).")
    A(f"- **Tijd in de markt:** het gemiddelde deel van het geld dat belegd is.")
    A(f"  - *Voorbeeld:* de trendregel F1 was gemiddeld voor {pct(f1['summary']['strat']['exposure'] * 100, 0)} belegd; de rest "
      f"stond in cash.")
    A(f"- **Mix met dezelfde tijd in de markt:** de eerlijke vergelijking voor een kleinere daling.")
    A(f"  - Wie altijd {pct(f1['summary']['strat']['exposure'] * 100, 0)} in gelijk gewicht en de rest in cash houdt, heeft "
      f"zonder enige regel al een daling van {pct(f1['summary']['matched']['mdd'])} in plaats van {pct(b['EW']['mdd'])}.")
    A(f"  - F1 ({pct(f1['summary']['strat']['mdd'])}) is dus {nl(f1['ci']['mdd']['est'], 1)} procentpunt beter dan zo'n vaste "
      f"mix. Alleen dát deel komt door de timing.")
    A(f"- **Trendfilter, concreet (oktober 2008):** op het slot van 30 september 2008 lagen alleen "
      f"{', '.join(on_sep08)} boven hun 10-maandsgemiddelde. Er was {pct(len(on_sep08) / 9 * 100, 0)} belegd (1/9 per asset) en "
      f"{pct(100 - len(on_sep08) / 9 * 100, 0)} stond in cash.")
    A(f"  - SPY lag {nl(-dist_sep08['SPY'], 1)}% en EEM {nl(-dist_sep08['EEM'], 1)}% onder het gemiddelde, dus die waren "
      f"uitgestapt.")
    A(f"  - In oktober zakten SPY {pct(oct08['SPY'], 1, True)}, EFA {pct(oct08['EFA'], 1, True)} en EEM {pct(oct08['EEM'], 1, True)}. "
      f"F1 verloor die maand {pct(mo('F1_N10', '2008-10'), 1, True)}, gelijk gewicht {pct(mo('EW', '2008-10'), 1, True)}.")
    A(f"  - Pech: VNQ lag nét {nl(dist_sep08['VNQ'], 1)}% boven zijn gemiddelde, deed dus mee, en zakte "
      f"{pct(oct08['VNQ'], 1, True)}.")
    A(f"  - Over heel 2008: F1 {pct(yr('F1_N10', 2008), 1, True)}, gelijk gewicht {pct(yr('EW', 2008), 1, True)}. Maar in 2009 "
      f"stapte F1 pas laat weer in ({pct(yr('F1_N10', 2009), 1, True)} tegen {pct(yr('EW', 2009), 1, True)}).")
    A(f"  - **2022 voor de trendregel kan ik niet laten zien:** 2022 ligt in H3, en H3 mag volgens de afspraak alleen open voor "
      f"candidates. F1 is rejected, dus H3 blijft voor F1 dicht.")
    A(f"- **Volatility targeting, concreet:** eind september 2008 was de beweeglijkheid van 60/40 over de laatste 20 handelsdagen "
      f"(op jaarbasis) ongeveer {pct(10 / e_sep08, 0)}.")
    A(f"  - Doel 10% ÷ {pct(10 / e_sep08, 0)} = {pct(e_sep08 * 100, 0)} belegd: {pct(e_sep08 * 60, 0)} SPY, "
      f"{pct(e_sep08 * 40, 0)} IEF, de rest cash. Eind oktober was dat {pct(w3.loc['2008-10-31'].sum() * 100, 0)}.")
    A(f"  - In 2022 (H3, geopend) zakte het belegde deel van 87% (slot januari) tot {pct(min(e22.values()) * 100, 0)} (slot juni). "
      f"Over 2022: {pct(y22[0], 1, True)} tegen {pct(y22[1], 1, True)} voor 60/40.")
    A(f"- **Bootstrap-interval:** hoe zeker een verschil is. We trekken 2000 keer een nieuwe '16 jaar' uit de echte maanden, "
      f"in aaneengesloten blokken van gemiddeld 12 maanden (crises blijven heel), en kijken hoe het verschil dan schommelt.")
    A(f"  - *Voorbeeld:* F3-60/40, Sharpe-verschil {ci(f3s['ci']['sharpe'])}. Het interval bevat 0, dus het kan ook toeval "
      f"zijn. In {pct(f3s['ci']['sharpe']['p_improve'] * 100, 0)} van de trekkingen was de regel beter.")
    A(f"- **Reality Check (correctie voor 25 trials):** als je 25 regels probeert, is er bij toeval altijd wel één die goed "
      f"lijkt.")
    A(f"  - De toets schat hoe groot het grootste toevalsverschil over 25 regels is. Bij de daling is dat "
      f"(95e percentiel) {nl(f3s['reality_check']['mdd']['max_null_p95'], 1)} procentpunt, bij Sharpe "
      f"{nl(f3s['reality_check']['sharpe']['max_null_p95'], 2)}.")
    A("  - Alleen wat daar duidelijk bovenuit komt, telt als bewezen.")
    A("")

    # ---------------- opzet ----------------
    A("## Opzet")
    A("")
    A("- **Universum (9 ETF's):** SPY (VS-aandelen), EFA (ontwikkelde markten), EEM (opkomende markten), TLT (VS-staats 20+ "
      "jaar), IEF (VS-staats 7–10 jaar), LQD (bedrijfsobligaties), VNQ (vastgoed), GLD (goud) en DBC (grondstoffen).")
    A("  - Een ETF doet mee vanaf 13 maandsloten. Zo groeit het universum van 6 (2005) naar 9 (vanaf maart 2007).")
    A("- **Data:** yfinance Adj Close (inclusief dividend), cash = 3-maands T-bill (FRED TB3MS). Belasting is niet "
      "meegenomen.")
    A("  - Geen ontbrekende handelsdagen.")
    A("  - De dividendcorrectie klopt tot op 0,07 procentpunt per jaar met slotkoers + zelf herbeleggen.")
    A("- **Uitvoering:** signaal op het slot van de laatste handelsdag van de maand, uitvoering op het slot van de eerste "
      "handelsdag erna. Het rendement van die dag hoort nog bij de oude gewichten.")
    A("  - Tussen twee uitvoeringen drijven de gewichten mee.")
    A("  - Kosten = 0,10% × verhandeld bedrag; gevoeligheid 0% en 0,30%.")
    A("- **Primaire configuraties** (vooraf gekozen, niet de beste cel): F1 N = 10; F2 k = 3, L = 12; F3 doel 10%, 20 "
      "dagen, op gelijk gewicht én op 60/40.")
    A("")
    A(table(["Blok", "Periode", "Keer geopend"], [
        ["Research", "2005-01 – 2020-12", "–"],
        ["H3", "2021-01 – 2026-09", f"{n_h3} (alleen F3-60/40)"],
        ["P (fondsen als proxy)", "1996-01 – 2004-12", f"{n_p} (alleen F3-60/40)"]]))
    A("")

    # ---------------- overzicht ----------------
    A("## Overzicht: de vier primaire configuraties (research 2005–2020)")
    A("")
    A("Sharpe-verschil = t.o.v. de volle baseline. MDD-verschil = t.o.v. dezelfde baseline met dezelfde tijd in de markt, "
      "in procentpunt (positief = de regel daalt minder). Tussen haken: 95%-bootstrap-interval.")
    A("")
    rows = []
    for pid in res["primary"]:
        p = P[pid]
        rows.append([SHORT[pid], p["baseline"], ci(p["ci"]["sharpe"]), ci(p["ci"]["mdd"], 1),
                     f"**{p['status']['status']}**" + (" (+H3, −P)" if pid == "F3_sixty_forty_v10_w20" else "")])
    A(table(["Regel", "Baseline", "Sharpe-verschil", "MDD-verschil (pp)", "Status"], rows))
    A("")
    rows = [["Gelijk gewicht (EW)", pct(b["EW"]["cagr"]), pct(b["EW"]["vol"]), nl(b["EW"]["sharpe"], 2), pct(b["EW"]["mdd"]),
             pct(b["EW"]["worst_year"]), "100%", pct(b["EW"]["turnover_py"] * 100, 0)],
            ["60/40", pct(b["60/40"]["cagr"]), pct(b["60/40"]["vol"]), nl(b["60/40"]["sharpe"], 2), pct(b["60/40"]["mdd"]),
             pct(b["60/40"]["worst_year"]), "100%", pct(b["60/40"]["turnover_py"] * 100, 0)]]
    for pid in res["primary"]:
        s = P[pid]["summary"]["strat"]
        rows.append([SHORT[pid], pct(s["cagr"]), pct(s["vol"]), nl(s["sharpe"], 2), pct(s["mdd"]), pct(s["worst_year"]),
                     pct(s["exposure"] * 100, 0), pct(s["turnover_py"] * 100, 0)])
    A(table(["", "CAGR", "Vol", "Sharpe", "MDD", "Slechtste jaar", "Belegd", "Omloop/jaar"], rows))
    A("")
    A("![Vermogensgroei en dalingen, gelijk gewicht](figures/equity_ew.png)")
    A("")
    A("![Vermogensgroei en dalingen, 60/40](figures/equity_6040.png)")
    A("")
    rows = []
    for pid in res["primary"]:
        s, ba = P[pid]["summary"]["strat"], P[pid]["summary"]["base"]
        rows.append([SHORT[pid], f"{pct(yr(pid, 2008), 1, True)} ({pct(ba['years']['2008'], 1, True)})",
                     f"{pct(yr(pid, 2020), 1, True)} ({pct(ba['years']['2020'], 1, True)})",
                     nl(s["sortino"], 2), nl(s["calmar"], 2), pct(s["mdd_daily"]), nl(s["trades_py"], 0)])
    A("Tussen haken: de volle baseline.")
    A("")
    A(table(["", "2008", "2020", "Sortino", "Calmar", "MDD per dag", "Transacties/jaar"], rows))
    A("")

    # ---------------- per familie ----------------
    def fam_block(pid, title, method):
        p = P[pid]
        j = p["judge"]
        A(f"### {title}")
        A("")
        A(f"**Methode.** {method}")
        A("")
        s, ba, mt = p["summary"]["strat"], p["summary"]["base"], p["summary"]["matched"]
        A(f"**Resultaat.** CAGR {pct(s['cagr'])} tegen {pct(ba['cagr'])} ({p['baseline']}). Sharpe {nl(s['sharpe'], 2)} tegen "
          f"{nl(ba['sharpe'], 2)}. MDD {pct(s['mdd'])} tegen {pct(ba['mdd'])}, en {pct(mt['mdd'])} voor de mix met dezelfde tijd "
          f"in de markt ({pct(s['exposure'] * 100, 0)}).")
        A(f"- Sharpe-verschil {ci(p['ci']['sharpe'])}; beter in {pct(p['ci']['sharpe']['p_improve'] * 100, 0)} van de "
          f"trekkingen.")
        A(f"- MDD-verschil {ci(p['ci']['mdd'], 1, ' pp')}; beter in {pct(p['ci']['mdd']['p_improve'] * 100, 0)} van de "
          f"trekkingen.")
        rt = p["random_timing"]
        A(f"- Tegen willekeurige timing (1000×, zelfde tijd in de markt: {pct(rt['exposure_random'] * 100, 0)} tegen "
          f"{pct(rt['exposure_strategy'] * 100, 0)}): Sharpe op het {nl(rt['sharpe_pct'], 0)}e percentiel, daling op het "
          f"{nl(rt['mdd_pct'], 0)}e.")
        sub = " / ".join(f"{nl(x['sharpe'], 2, True)} | {nl(x['mdd'], 1, True)}" for x in p["subperiods"])
        A(f"- Subperiodes 2005–09 / 2010–14 / 2015–20 (Sharpe | MDD): {sub}.")
        A("")
        A(f"**Onzekerheid en status: {p['status']['status']}.** Criteria uit PLAN3 §9 (Sharpe / MDD):")
        A("")
        lab = {"1_estimate_positive": "1 puntschatting > 0", "2_p_improve": "2 ≥ 80% van de trekkingen beter",
               "3_ci_width": "3 interval niet te breed", "4a_subperiods": "4a ≥ 2 van 3 subperiodes",
               "4b_without_best_two_years": "4b zonder de 2 beste jaren", "4c_leave_one_asset_out": "4c zonder elke asset",
               "5_costs_3x": "5 bij 3× kosten", "6_plateau": "6 plateau in het grid", "7_sharpe_not_worse": "7 Sharpe niet slechter"}
        A(table(["Criterium", "Sharpe", "MDD"], [[lab[k], yes(j["sharpe"]["criteria"].get(k)) if k != "7_sharpe_not_worse" else "–",
                                                 yes(j["mdd"]["criteria"].get(k))] for k in lab]))
        A("")

    A("## Per familie")
    A("")
    fam_block("F1_N10", "F1 – Trendfilter per asset (N = 10)",
              "Elke asset krijgt 1/K van het geld als zijn maandslot boven het gemiddelde van de laatste 10 maandsloten ligt; "
              "anders gaat dat deel naar cash. Idee: wie uit dalende trends stapt, ontloopt lange dalingen (Faber 2007). "
              "Vergeleken met gelijk gewicht over dezelfde ETF's.")
    A(f"*F1 per periode (2005–2009 tegen de rest).* Het hele voordeel zit in 2007–2009 (zie de figuur). Zonder 2008 en 2018 is "
      f"het Sharpe-verschil {nl(f1['without_best']['sharpe']['diff'], 2, True)}. De daling blijft dan wel iets kleiner "
      f"({nl(f1['without_best']['mdd']['diff'], 1, True)} pp zonder 2008 en 2007).")
    A("")
    A("![F1 in 2007–2009: welke assets belegd waren](figures/f1_2007_2009.png)")
    A("")
    fam_block("F2_k3_L12", "F2 – Dual momentum (top 3 op 12-maands rendement)",
              "Elke maand de 3 ETF's met het hoogste 12-maands rendement, elk een derde, maar alleen als dat rendement boven "
              "cash ligt; anders dat deel cash. Idee: wat goed liep, loopt nog even door, en stap uit als zelfs het beste "
              "slechter is dan cash (Antonacci 2014). Vergeleken met gelijk gewicht.")
    A(f"*F2 kost vooral rendement in zijwaartse jaren* (2011 {pct(f2['summary']['strat']['years']['2011'], 1, True)}, 2016 "
      f"{pct(f2['summary']['strat']['years']['2016'], 1, True)}, 2018 {pct(f2['summary']['strat']['years']['2018'], 1, True)}): "
      f"het koopt wat net gestegen is en wisselt vaak ({nl(f2['summary']['strat']['trades_py'], 0)} transacties per jaar).")
    A(f"*Kanttekening bij de willekeurige timing van F2:* daar was de tijd in de markt "
      f"{pct(f2['random_timing']['exposure_random'] * 100, 0)} in plaats van {pct(f2['random_timing']['exposure_strategy'] * 100, 0)}. "
      f"Per asset verschoven selecties leveren niet altijd precies drie assets tegelijk op. Die vergelijking is bij F2 dus minder "
      f"zuiver; de andere toetsen wijzen dezelfde kant op.")
    A("")
    fam_block("F3_equal_weight_v10_w20", "F3 – Volatility targeting op gelijk gewicht (10%, 20 dagen)",
              "Bereken elke maand de beweeglijkheid van de gelijk-gewicht-portefeuille over de laatste 20 handelsdagen. Beleg "
              "doel ÷ beweeglijkheid (max. 100%, geen hefboom), de rest in cash. Idee: onrust houdt aan, rendement niet "
              "(Moreira & Muir 2017).")
    fam_block("F3_sixty_forty_v10_w20", "F3 – Volatility targeting op 60/40 (10%, 20 dagen)",
              "Dezelfde regel op 60% SPY / 40% IEF. Gemeten tegen 60/40 zelf (Sharpe) en tegen 60/40 met dezelfde tijd in "
              "de markt (daling). Dit is de enige candidate.")
    A(f"*Zonder elk jaar apart* blijft het voordeel bestaan: minimaal {nl(f3s['leave_one_year_out']['min_sharpe'], 2, True)} "
      f"Sharpe en {nl(f3s['leave_one_year_out']['min_mdd'], 1, True)} pp daling. Er is dus niet één jaar dat alles draagt.")
    pa = f3s["per_asset"]
    A(f"*Per asset* komt het voordeel uit het aandelendeel: dezelfde regel op SPY alleen gaf {nl(pa['SPY']['sharpe'], 2, True)} "
      f"Sharpe, op IEF alleen {nl(pa['IEF']['sharpe'], 2, True)} (IEF was gemiddeld voor {pct(pa['IEF']['exposure'] * 100, 0)} "
      f"belegd).")
    A("")
    A("![Deel belegd van F3-60/40, 1996–2026](figures/exposure_6040.png)")
    A("")

    # ---------------- hold-outs ----------------
    A("## Hold-out H3 en pre-sample P (alleen F3-60/40, elk 1× geopend)")
    A("")
    A("Exact dezelfde regel en meting als in research, met de tijd in de markt uit het blok zelf.")
    A("- H3 = 2021-01 – 2026-09, dezelfde ETF's.")
    A("- P = 1996–2004 met Vanguard-fondsen: VFINX voor SPY en VFITX voor IEF. VFINX komt in 1994–2004 jaar voor jaar "
      "overeen met SPY (verschil ≤ 0,8 procentpunt), dus de uitkeringen zitten in de data.")
    A("")
    rows = []
    for name, blk, c in (("Research 2005–2020", None, None), ("H3 2021–2026", h3, h3c), ("P 1996–2004", pp, ppc)):
        if blk is None:
            s, ba, d, cis = f3s["summary"]["strat"], f3s["summary"]["base"], f3s["ci"], f3s["ci"]
            sd, mdd = d["sharpe"]["est"], d["mdd"]["est"]
        else:
            s, ba, cis = c["strat"], c["base"], c["ci"]
            sd, mdd = c["sharpe"], c["mdd"]
        rows.append([name, f"{pct(s['cagr'])} / {pct(ba['cagr'])}", f"{nl(s['sharpe'], 2)} / {nl(ba['sharpe'], 2)}",
                     f"{pct(s['mdd'])} / {pct(ba['mdd'])}", ci(cis["sharpe"]), ci(cis["mdd"], 1)])
    A(table(["Blok", "CAGR regel / 60/40", "Sharpe", "MDD", "Sharpe-verschil", "MDD-verschil (pp)"], rows))
    A("")
    A(f"- **H3: positief, maar klein.** In 2022 daalden aandelen én obligaties. De regel schaalde terug en verloor "
      f"{pct(y22[0], 1, True)} tegen {pct(y22[1], 1, True)}. Over het hele blok lag het rendement iets lager "
      f"({pct(h3c['strat']['cagr'])} tegen {pct(h3c['base']['cagr'])}).")
    A(f"- **P: negatief.** 1996–2004 was een onrustige periode: de regel was in {pct(share_p * 100, 0)} van de maanden deels "
      f"in cash (research: {pct(share_r * 100, 0)}). Hij schaalde vaak terug ná een schok en miste dan het herstel.")
    A(f"  - Bijvoorbeeld na de Rusland-crisis: in september–november 1998 voor 54–70% belegd, terwijl 60/40 toen +5,1%, +4,7% "
      f"en +3,5% per maand steeg. Ook eind 2002 miste hij zo een herstel.")
    A(f"  - Per jaar: 1998 {pct(p_years[0]['1998'], 1, True)} tegen {pct(p_years[1]['1998'], 1, True)}, 2000 {pct(p_years[0]['2000'], 1, True)} tegen {pct(p_years[1]['2000'], 1, True)}, 2001 {pct(p_years[0]['2001'], 1, True)} tegen {pct(p_years[1]['2001'], 1, True)}, 2002 "
      f"{pct(p_years[0]['2002'], 1, True)} tegen {pct(p_years[1]['2002'], 1, True)}.")
    A("  - Let op: het universum van P is anders (fondsen in plaats van ETF's), dus vergelijkbaarheid is beperkt. Voor F3-60/40 "
      "gaat het wel om bijna dezelfde beleggingen (S&P 500 en middellange staatsobligaties).")
    A("")
    A(f"**Status F3-60/40: blijft candidate, wordt niet validated.**")
    A(f"- H3 is positief, maar P is negatief.")
    A(f"- De Reality Check haalt hij niet: p = {nl(f3s['reality_check']['sharpe']['p'], 2)} (Sharpe) en "
      f"{nl(f3s['reality_check']['mdd']['p'], 2)} (daling); nodig is < 0,05.")
    A("- H3 en P zijn nu voor deze configuratie verbruikt. Aan de regel wordt niets meer veranderd.")
    A("")

    # ---------------- robuustheid ----------------
    A("## Robuustheid")
    A("")
    A("### Het hele grid")
    A("")
    A("Alle 25 trials, kosten 0,10%. Het witte kader is de vooraf gekozen cel.")
    A("- Bij F1 en F3 is (vrijwel) het hele blok blauw. Dat is een plateau, geen toevalspiek.")
    A("- Bij F2 wisselt het: wat werkt hangt af van k en L. Dat is geen stabiel effect.")
    A("")
    A("![Heatmaps van het hele grid](figures/grid.png)")
    A("")
    A("### Per asset (breedte)")
    A("")
    pf1 = res["per_asset_F1"]
    better = [a for a in pf1 if pf1[a]["trend"]["sharpe"] > pf1[a]["buy_hold"]["sharpe"]]
    lower = [a for a in pf1 if abs(pf1[a]["trend"]["mdd"]) < abs(pf1[a]["buy_hold"]["mdd"])]
    A(f"- Het trendfilter op één ETF tegelijk verbeterde de Sharpe bij {len(better)} van de 9 ({', '.join(better)}). De "
      f"grootste daling werd kleiner bij {len(lower)} van de 9 ({', '.join(lower)}).")
    A("- Bij staatsobligaties (TLT, IEF) werd het slechter (Sharpe −0,19). Daar waren nauwelijks grote dalingen om te "
      "ontlopen, dus het filter kostte alleen rendement.")
    A("- Volatility targeting per ETF helpt vooral bij SPY en VNQ en nauwelijks of niet bij de rest. Het effect is dus "
      "**smal**: Amerikaanse aandelen en vastgoed.")
    A("")
    A("![Per asset](figures/per_asset.png)")
    A("")
    loo_rows = []
    for pid in ("F1_N10", "F2_k3_L12", "F3_equal_weight_v10_w20"):
        l = P[pid]["loo"]
        loo_rows.append([SHORT[pid], f"{nl(min(v['sharpe'] for v in l.values()), 2, True)} … {nl(max(v['sharpe'] for v in l.values()), 2, True)}",
                         f"{nl(min(v['mdd'] for v in l.values()), 1, True)} … {nl(max(v['mdd'] for v in l.values()), 1, True)}"])
    A("Leave-one-asset-out: steeds één ETF weggelaten, uit regel én baseline (bandbreedte over de 9 keer).")
    A("")
    A(table(["Regel", "Sharpe-verschil", "MDD-verschil (pp)"], loo_rows))
    A("")
    A("### Kosten, timing en valuta")
    A("")
    rows = []
    for pid in res["primary"]:
        p = P[pid]
        c, t = p["costs"], p["timing"]
        rows.append([SHORT[pid], f"{nl(c['0.0']['sharpe'], 2, True)} / {nl(c['0.003']['sharpe'], 2, True)}",
                     f"{nl(t['lag0']['sharpe'], 2, True)} / {nl(t['lag2']['sharpe'], 2, True)}",
                     f"{nl(p['eur']['usd_cash_converted']['sharpe'], 2, True)} / {nl(p['eur']['cash_in_eur']['sharpe'], 2, True)}",
                     f"{nl(p['eur']['usd_cash_converted']['mdd'], 1, True)} / {nl(p['eur']['cash_in_eur']['mdd'], 1, True)}"])
    A(table(["Regel", "Sharpe-verschil bij 0% / 0,30% kosten", "Signaaldag / 2e handelsdag", "EUR (i) / (ii) Sharpe",
             "EUR (i) / (ii) MDD"], rows))
    A("")
    A("- **Kosten** veranderen weinig: deze regels handelen maandelijks.")
    A("- **Timing:** de uitvoering een dag eerder (op het signaalslot, niet realistisch) of later verandert de uitkomst weinig. "
      "Dat past niet bij een lookahead-fout.")
    A("- **Euro:** (i) = alles in USD, omgerekend naar EUR; (ii) = het cash-deel in euro tegen de eurorente.")
    A(f"  - Voor een euro-belegger zijn de verschillen veel kleiner. De dollar steeg juist in de crises van 2008 en 2020, "
      f"waardoor een euro-belegger in US-ETF's al een ingebouwde buffer had.")
    A(f"  - De daling van gelijk gewicht was in euro {pct(f1['eur']['usd_cash_converted']['base']['mdd'])} in plaats van "
      f"{pct(b['EW']['mdd'])}.")
    A(f"  - Daardoor blijft er minder over om te verbeteren: F3-60/40 in euro {nl(f3s['eur']['usd_cash_converted']['sharpe'], 2, True)} "
      f"tot {nl(f3s['eur']['cash_in_eur']['sharpe'], 2, True)} Sharpe.")
    A("")
    A("### Rolling 10-jaarsvensters")
    A("")
    A("Ieder punt is een periode van 10 jaar (MDD-verschil met de tijd in de markt van de hele periode). Vensters met 2008 "
      "erin (einde t/m 2017) tonen bij F1 en F3 een voordeel.")
    A("- Latere vensters, zonder 2008, tonen dat niet (F1, F3-EW) of veel minder (F3-60/40).")
    A("- Het Sharpe-voordeel van F1 wordt dan negatief.")
    A("")
    A("![Rolling 10 jaar](figures/rolling.png)")
    A("")
    A("### Willekeurige timing")
    A("")
    A("1000 portefeuilles per regel met dezelfde tijd in de markt en evenveel wissels, maar op willekeurige momenten.")
    A("- F1 en de F3-varianten liggen boven 94–100% van de willekeurige portefeuilles. Het *moment* van uitstappen doet er dus "
      "toe, in deze 16 jaar.")
    A("- F2 niet.")
    A("")
    A("![Willekeurige timing](figures/random_timing.png)")
    A("")

    # ---------------- vermogen en correctie ----------------
    A("## Statistisch vermogen: wat kon deze data aantonen?")
    A("")
    A(f"- **Vooraf berekend:** bij 16 jaar en een correlatie van 0,9 tussen regel en baseline is een Sharpe-verschil van "
      f"ongeveer {nl(res['power_prior']['rho0.9']['mde'], 2, True)} met 80% kans aantoonbaar; bij 0,7 is dat "
      f"{nl(res['power_prior']['rho0.7']['mde'], 2, True)}.")
    A("- **Na de run (bootstrap-standaardfout × 2,8):**")
    A("")
    A(table(["Regel", "SE Sharpe-verschil", "Kleinste aantoonbare Sharpe-verschil", "Kleinste aantoonbare MDD-verschil"],
            [[SHORT[pid], nl(P[pid]['power']['sharpe']['se'], 2), nl(P[pid]['power']['sharpe']['mde'], 2, True),
              nl(P[pid]['power']['mdd']['mde'], 0, True) + " pp"] for pid in res["primary"]]))
    A("")
    A(f"**Hoe weeg je dat?** Het gevonden verschil van F3-60/40 ({nl(f3s['ci']['sharpe']['est'], 2, True)}) is de helft van "
      f"wat deze data kan aantonen ({nl(f3s['power']['sharpe']['mde'], 2, True)}). Zelfs als het effect echt is, kon dit "
      f"onderzoek het niet bewijzen. Omgekeerd betekent 'niet bewezen' hier niet 'bestaat niet'. Het effect is klein, en het "
      f"teken is in P omgeslagen.")
    A("")
    A("## Correctie voor 25 trials")
    A("")
    A("Gekozen methode: de **Reality Check** (zie Begrippen). De deflated Sharpe ratio past hier niet: die toetst of één "
      "Sharpe boven nul ligt, en buy-and-hold heeft zelf al een positieve Sharpe. Wij willen weten of een regel *beter is dan* "
      "de baseline.")
    A("")
    A(table(["Regel", "p (Sharpe)", "p (MDD)"], [[SHORT[pid], nl(P[pid]["reality_check"]["sharpe"]["p"], 3),
                                                 nl(P[pid]["reality_check"]["mdd"]["p"], 3)] for pid in res["primary"]]))
    A("")
    A(f"Alleen de daling van F1 komt onder 0,05 (p = {nl(f1['reality_check']['mdd']['p'], 3)}). Dat is het 2008-effect. F1 is "
      f"rejected op stabiliteit, en een candidate-status is nodig voordat de correctie meetelt.")
    A("")

    # ---------------- kapotmaken ----------------
    A("## Wat ik geprobeerd heb kapot te maken")
    A("")
    A("Geen resultaat haalde de drempel van het \"te mooi\"-protocol (Sharpe-winst > 0,40, of daling < 10% bij een even hoog "
      "rendement). F1 kwam met een daling van 8,4% wel dicht bij \"bijna geen daling\", bij een lager rendement. Daarom heb ik "
      "voor alle vier gecontroleerd:")
    A("")
    A("1. **Lookahead:** tests (`tests/test_etf.py`) laten zien dat signalen niet veranderen als de koersen ná het "
      "signaalmoment veranderen, en dat het rendement op de uitvoeringsdag nog bij de oude gewichten hoort.")
    A("2. **Signaaltiming:** een dag eerder of later uitvoeren verandert de uitkomst weinig (zie de tabel).")
    A("3. **Dividend en Adj Close:** het totaalrendement uit Adj Close komt per ETF en per jaar tot op 0,07 procentpunt "
      "overeen met slotkoers + zelf herbelegde dividenden. Een onafhankelijke herberekening van 60/40 geeft 8,14% per jaar "
      "(motor: 8,17%).")
    A("4. **Overlevingsbias:** het universum is achteraf gekozen (alle 9 ETF's bestaan nog). Dat helpt elke regel én de "
      "baselines, dus we meten alleen verschillen. Leave-one-asset-out laat zien dat geen enkele ETF het resultaat draagt.")
    A("5. **Eén jaar of periode:** zonder 2008 valt het Sharpe-voordeel van F1 en F3-EW weg. Bij F3-60/40 blijft het zonder "
      "elk jaar apart positief, maar in P (1996–2004) was het negatief.")
    A("6. **Kosten 3×:** verandert de status van geen enkele regel.")
    A("")

    # ---------------- praktijk ----------------
    A("## Wat betekent dit in de praktijk?")
    A("")
    A("**Geen advies.** Dit onderzoek laat geen regel zien die aantoonbaar beter is. Wie een regel wil gebruiken, doet dat om "
      "persoonlijke redenen (rustiger slapen in een crisis), niet omdat het bewezen meer oplevert.")
    A("")
    s3 = f3s["summary"]["strat"]
    A(f"**Hoe vaak handelen?**")
    share_cash = float((w3.sum(axis=1).iloc[:-1] < 0.999).mean())
    A(f"- **F3-60/40:** één keer per maand kijken, op de eerste handelsdag. Zo'n "
      f"{pct(share_cash * 100, 0)} van de maanden is er iets aan te passen (deels naar cash of terug). Dat zijn ongeveer "
      f"{nl(s3['trades_py'], 0)} transacties per jaar (gewone 60/40 met maandelijks herbalanceren: "
      f"{nl(b['60/40']['trades_py'], 0)}).")
    A(f"  - De omloop is {pct(s3['turnover_py'] * 100, 0)} per jaar; dat kost bij 0,10% ongeveer "
      f"{pct(s3['turnover_py'] * 0.10, 2)} per jaar.")
    A(f"- **F1:** {nl(f1['summary']['strat']['trades_py'], 0)} transacties per jaar, omloop "
      f"{pct(f1['summary']['strat']['turnover_py'] * 100, 0)}.")
    A("- **Vaste orderkosten:** met bijvoorbeeld € 2 per order en € 10.000 belegd kosten 18 orders € 36 per jaar. Dat is "
      "0,36% per jaar, meer dan de 0,10% die in deze berekening zit. Bij kleine bedragen wegen vaste orderkosten zwaar.")
    A("")
    A("**UCITS-alternatieven** (suggesties; in de EU kun je de US-ETF's meestal niet kopen):")
    A("")
    A(table(["US-ETF", "Mogelijke UCITS-tegenhanger (voorbeeld)"], [
        ["SPY", "iShares Core S&P 500 UCITS ETF (Acc), IE00B5BMR087; Vanguard S&P 500 UCITS ETF, IE00B3XXRP09"],
        ["IEF", "iShares $ Treasury Bond 7-10yr UCITS ETF (ook in een EUR-hedged versie)"],
        ["TLT", "iShares $ Treasury Bond 20+yr UCITS ETF"],
        ["LQD", "iShares $ Corp Bond UCITS ETF"],
        ["EFA", "een MSCI EAFE- of MSCI World ex USA-UCITS-ETF"],
        ["EEM", "iShares Core MSCI EM IMI UCITS ETF, IE00BKM4GZ66"],
        ["VNQ", "iShares US Property Yield UCITS ETF"],
        ["GLD", "fysiek goud-ETC, bijv. iShares Physical Gold ETC, IE00B4ND3602 (een ETC, geen UCITS-fonds)"],
        ["DBC", "een brede grondstoffen-UCITS-ETF (andere index dan DBC!)"]]))
    A("")
    A("**Controleer zelf bij je broker:**")
    A("- of het product beschikbaar is en een KID (PRIIPs) heeft;")
    A("- de lopende kosten (TER), spread en orderkosten;")
    A("- dividend: uitkerend of accumulerend, en de belastingbehandeling;")
    A("- de trackingverschillen met de US-ETF (andere domicilie en dividendbelasting);")
    A("- de valuta: USD-noteringen of EUR-hedged. Dat laatste verandert de uitkomst, zie het euro-hoofdstuk.")
    A("")
    A("Ik heb de ISIN's uit mijn kennis gehaald en niet online gecontroleerd.")
    A("")

    # ---------------- onzeker ----------------
    A("## Wat onzeker blijft en wat je zelf moet controleren")
    A("")
    A("- **Weinig crises in de data.** De voordelen komen uit 2008 en 2020 (en in H3 uit 2022). Bij de volgende crisis kan het "
      "anders lopen; 2000–2002 (P) laat dat al zien.")
    A("- **Belasting** is niet meegenomen: in Nederland box 3, en dividendbelasting binnen het fonds.")
    A("- **Valuta:** alle hoofdresultaten zijn in USD. In euro zijn de verschillen kleiner.")
    A("- **Yahoo-data:** gecontroleerd op gaten en dividendcorrectie, maar niet tegen een tweede bron (behalve VFINX tegen SPY "
      "in P).")
    A("- **Overlevingsbias en de keuze van het universum** (achteraf, uit de literatuur): dat bevoordeelt alles wat op dit "
      "universum draait.")
    A("- **Fondswijzigingen** (indexwissels bij TLT/IEF/LQD/VNQ, sponsorwissel DBC) komen uit mijn kennis en zijn niet "
      "gecontroleerd; zie PLAN3 §1.")
    A("- **H3 en P zijn voor F3-60/40 verbruikt.** Een nieuwe variant van die regel heeft geen schone hold-out meer, behalve "
      "de toekomst.")
    A("")
    A(f"Bestanden: [PLAN3.md](PLAN3.md), `research/round3/results/` (results.json, grid.csv, holdout_*.json), code in `etf/`.")
    return "\n".join(md)


def to_html(md_text: str) -> str:
    import markdown
    body = markdown.markdown(fix_lists(md_text), extensions=["tables", "sane_lists"])
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")

    def embed(m):
        f = R3 / m.group(1)
        return f'src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}"' if f.exists() else m.group(0)
    body = re.sub(r'src="(figures/[^"]+\.png)"', embed, body)
    body = body.replace('href="PLAN3.md"', f'href="{GH}PLAN3.md"')
    return ("<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Onderzoek ronde 3</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def main():
    cfg = load_config()
    res = json.loads((RES / "results.json").read_text())
    make_figures(res, cfg)
    md = build(res, cfg)
    (R3 / "report.md").write_text(md, encoding="utf-8")
    (R3 / "report.html").write_text(to_html(md), encoding="utf-8")
    print("research/round3/report.md en report.html geschreven")


if __name__ == "__main__":
    main()
