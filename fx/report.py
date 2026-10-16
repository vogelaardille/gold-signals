"""Rapporten ronde 4 en 5: research/round4|5/report.md en report.html (+ figuren).

Leest alleen opgeslagen uitkomsten (results.json, holdout_*.json, k5_descriptive.json, trades_*.csv).
Er wordt niets opnieuw berekend en niets geopend.
Draaien: .venv/bin/python -m fx.report
"""
import base64
import json
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from fx.data import ROOT  # noqa: E402
from goldsignals.research.figures import AQUA, BLUE, INK2, MUTED, ORANGE, _style  # noqa: E402
from goldsignals.research.report import CSS, fix_lists  # noqa: E402

GH = "https://github.com/vogelaardille/gold-signals/blob/main/research/"


# ----------------------------- opmaak -------------------------------------

def nl(x, d=2, sign=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "–"
    s = f"{x:+.{d}f}" if sign else f"{x:.{d}f}"
    return s.replace(".", ",").replace("-", "−")


def pct(x, d=0):
    return "–" if x is None else f"{x * 100:.{d}f}%".replace(".", ",")


def table(head, rows):
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def to_html(md_text: str, folder, title: str, plan: str) -> str:
    import markdown
    body = markdown.markdown(fix_lists(md_text), extensions=["tables", "sane_lists"])
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")

    def embed(m):
        f = folder / m.group(1)
        return f'src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}"' if f.exists() else m.group(0)
    body = re.sub(r'src="(figures/[^"]+\.png)"', embed, body)
    body = body.replace(f'href="{plan}"', f'href="{GH}{folder.name}/{plan}"')
    return ("<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{title}</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def _cum(tr: pd.DataFrame) -> pd.Series:
    t = pd.to_datetime(tr["entry_time"], utc=True)
    return tr["net_bp"].groupby(t.dt.tz_localize(None).dt.normalize()).sum().cumsum()


def _save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ----------------------------- ronde 4 ------------------------------------

R4 = ROOT / "research/round4"
NAMES4 = {"F1-EU": "F1-EU fix-reversal Europa (EUR/USD)", "F1-TK": "F1-TK fix-reversal Tokio (USD/JPY)",
          "F2-B": "F2-B ronde getallen, bounce", "F2-D": "F2-D ronde getallen, breakout",
          "F3": "F3 London breakout"}


def figures4(res, h4):
    fig_dir = R4 / "figures"
    fig_dir.mkdir(exist_ok=True)
    _style()
    tr = pd.read_csv(R4 / "results/trades_F1-EU.csv")
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    c = _cum(tr)
    ax.plot(c.index, c / 100, color=BLUE, lw=1.8, label="research 2005–2019")
    h = R4 / "results/trades_H4_F1-EU.csv"
    if h.exists():
        ch = _cum(pd.read_csv(h)) + c.iloc[-1]
        ax.plot(ch.index, ch / 100, color=ORANGE, lw=1.8, label="hold-out H4 2020–2026")
        ax.axvline(pd.Timestamp("2020-01-01"), color=MUTED, ls="--", lw=1)
    ax.set_ylabel("cumulatief netto (%)")
    ax.set_title("F1-EU: opgeteld netto rendement per trade", loc="left")
    ax.legend(fontsize=8, loc="upper left")
    _save(fig, fig_dir / "f1eu_cumulative.png")

    pl = res["primaries"]["F1-EU"]["placebo_gross_bp_by_shift_hours"]
    xs = sorted(int(k) for k in pl)
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    ax.bar(xs, [pl[str(x)] for x in xs], color=[ORANGE if x == 0 else MUTED for x in xs])
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xlabel("vensters verschoven met … uur (0 = de echte fix-vensters)")
    ax.set_ylabel("bruto bp per trade")
    ax.set_title("F1-EU placebo: dezelfde vensters op andere uren", loc="left")
    _save(fig, fig_dir / "f1eu_placebo.png")

    keys = list(res["primaries"])
    p = res["primaries"]
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    x = np.arange(len(keys))
    ax.bar(x - 0.2, [p[k]["gross_bp"] for k in keys], 0.4, color=MUTED, label="bruto (vóór kosten)")
    ax.bar(x + 0.2, [p[k]["net_bp"] for k in keys], 0.4, color=BLUE, label="netto (na spread + slippage)")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x, keys)
    ax.set_ylabel("bp per trade")
    ax.set_title("Primaire configuraties, research 2005–2019", loc="left")
    ax.legend(fontsize=8)
    _save(fig, fig_dir / "primaries.png")

    if h4:
        yr = {**res["trials"]["F1|EUR/USD|Europe"]["net_bp_by_year"], **h4["net_bp_by_year"]}
        ys = sorted(int(k) for k in yr)
        fig, ax = plt.subplots(figsize=(6.4, 3.2))
        ax.bar(ys, [yr[str(y)] / 100 for y in ys], color=[ORANGE if y >= 2020 else BLUE for y in ys])
        ax.axhline(0, color=INK2, lw=0.8)
        ax.set_ylabel("netto per jaar (%)")
        ax.set_title("F1-EU per jaar (blauw research, oranje H4)", loc="left")
        _save(fig, fig_dir / "f1eu_years.png")


def build4(res, h4) -> str:
    p = res["primaries"]
    eu = p["F1-EU"]
    md, A = [], None
    A = md.append
    A("# Ronde 4: daytrade-patronen in valuta")
    A("")
    A("*Research 2005–2019 op EUR/USD, GBP/USD en USD/JPY (Dukascopy 1h, bid én ask). Kopen op de ask, verkopen op "
      "de bid, plus 0,1 pip slippage per kant. Nooit een positie over 17:00 New York. Opzet vooraf vastgelegd in "
      "[PLAN4.md](PLAN4.md). 32 trials. Hold-out H4 (2020-01 – 2026-10) 1× geopend, alleen voor F1-EU. Alleen "
      "onderzoek: geen paper trading, geen Telegram, geen echt geld.*")
    A("")
    A("## Oordeel in gewone taal")
    A("")
    A("**Kort: één patroon bestond echt (de dollar rond de grote fixes), maar het is na de publicatie grotendeels "
      "verdwenen. De rest leverde na kosten niets op.**")
    A("")
    if h4:
        A(f"- **F1-EU** (dollar long van 08:00 tot 14:00 Frankfurt, dollar short van 16:00 Londen tot 16:00 New York, "
          f"op EUR/USD) is volgens de vooraf vastgelegde regels **validated**.")
        A(f"  - In research: {nl(eu['net_bp'], sign=True)} bp netto per trade (bruto {nl(eu['gross_bp'])}), "
          f"Sharpe {nl(eu['sharpe'])}, {eu['n_trades']} trades, positief in alle drie de subperiodes.")
        A(f"  - In H4 (2020–2026): **{nl(h4['net_bp'], sign=True)} bp** (bruto {nl(h4['gross_bp'])}), Sharpe "
          f"{nl(h4['sharpe'])}, maar {pct(h4['boot_pos'])} van de bootstrap-trekkingen > 0. Dat is statistisch niet "
          f"van nul te onderscheiden. 2025 en 2026 waren verliesjaren; met gewone broker-kosten "
          f"{nl(h4['net_bp_retail'], sign=True)} bp.")
        A("  - **Hoe zeker: laag.** De H4-regel in PLAN4 eiste alleen een positief gemiddelde. Achteraf was dat te "
          "soepel. In ronde 5 is die eis daarom strenger gemaakt. F1-EU gaat niet naar paper trading zonder apart "
          "plan en akkoord.")
    A(f"- **F1-TK** (rond de Tokio-fix, USD/JPY): het patroon is er bruto ({nl(p['F1-TK']['gross_bp'], sign=True)} bp), "
      f"maar na kosten blijft {nl(p['F1-TK']['net_bp'], sign=True)} bp over, en bij 3× slippage is het negatief. "
      "Rejected.")
    A(f"- **Ronde getallen** (Osler 2003): de koers keert niet vaker bij 00-niveaus; bounce op echte ronde getallen "
      f"was zelfs slechter dan op willekeurig verschoven niveaus ({nl(p['F2-B']['net_bp'], sign=True)} bp). Breakout: "
      f"{nl(p['F2-D']['net_bp'], sign=True)} bp, niet beter dan het nulmodel. Rejected.")
    A(f"- **London breakout** (populair bij particulieren): {nl(p['F3']['net_bp'], sign=True)} bp netto, niet beter "
      "dan willekeurige entries. Rejected.")
    A("")
    A("## Waarom deze strategieën?")
    A("")
    A("- **Fix-reversal:** Krohn, Mueller & Whelan (*Journal of Finance* 2024) vonden dat de dollar stijgt vóór de "
      "grote valutafixes en daarna daalt. Hun verklaring: dealers dekken de dollarvraag rond de fix af. De paper "
      "meldde ~2,5 bp per venster, vóór kosten.")
    A("- **Ronde getallen:** Osler (*JF* 2003) zag in echte orderboeken dat take-profit-orders óp ronde koersen liggen "
      "(daar zou de koers keren) en stop-losses er net voorbij (na doorbraak zou hij versnellen).")
    A("- **London breakout:** de bekendste daytradestrategie op forex-fora, zonder onafhankelijk onderzoek. Hier als "
      "controle.")
    A("")
    A("## Resultaten")
    A("")
    A("![Primaire configuraties](figures/primaries.png)")
    A("")
    rows = []
    for k, r in p.items():
        c = r["net_bp_by_slippage_multiplier"]
        rows.append([k, r["n_trades"], nl(r["net_bp"], sign=True), nl(r["gross_bp"]), nl(r["cost_bp"]),
                     nl(r["sharpe"]), pct(r["boot_pos"]), nl(c["3"], sign=True), nl(c["retail"], sign=True),
                     nl(r["reality_check_p"]), f"**{r['status']}**"])
    A(table(["", "trades", "netto bp", "bruto bp", "kosten bp", "Sharpe", "bootstrap > 0", "3× slip", "retail",
             "RC p", "status research"], rows))
    A("")
    A("*bp = basispunt = 0,01%. Netto = na de echte spread van dat uur plus 0,1 pip slippage per kant. Retail = "
      "+0,5 pip per kant extra, alleen ter informatie. RC p = Reality Check over alle 32 trials.*")
    A("")
    A("### F1-EU: het fix-patroon")
    A("")
    A("![F1-EU cumulatief](figures/f1eu_cumulative.png)")
    A("")
    if h4:
        A("![F1-EU per jaar](figures/f1eu_years.png)")
        A("")
    A(f"- Per been in research: dollar long vóór de ECB-fix {nl(eu['by_leg_net_bp']['E_pre'], sign=True)} bp, "
      f"dollar short na de Londen-fix {nl(eu['by_leg_net_bp']['L_post'], sign=True)} bp.")
    if h4:
        A(f"- Per been in H4: {nl(h4['by_leg_net_bp']['E_pre'], sign=True)} bp en "
          f"{nl(h4['by_leg_net_bp']['L_post'], sign=True)} bp. Het tweede been werkt niet meer.")
    A("- Hetzelfde patroon is bruto ook zichtbaar op GBP/USD "
      f"({nl(eu['gross_by_pair']['GBP/USD'], sign=True)} bp) en zwakker op USD/JPY "
      f"({nl(eu['gross_by_pair']['USD/JPY'], sign=True)} bp): het is een dollar-effect, geen EUR-effect.")
    A("")
    A("![Placebo](figures/f1eu_placebo.png)")
    A("")
    A("*Placebo: dezelfde vensters, maar een aantal uur verschoven. Vlak rond de echte fix-tijden is het bruto "
      "positief, 5–10 uur eerder negatief. Dat past bij het W-patroon uit de paper.*")
    A("")
    A("### Ronde getallen en London breakout")
    A("")
    rows = []
    for k in ("F2-B", "F2-D", "F3"):
        r = p[k]
        rows.append([NAMES4[k], nl(r["net_bp"], sign=True), nl(r["null_p95"], sign=True),
                     f"{nl(r['null_percentile_of_real'], 0)}e", pct(r["grid_share_positive"])])
    A(table(["", "netto bp", "nulmodel 95e pct", "echt op percentiel", "grid netto > 0"], rows))
    A("")
    A("*Nulmodel: F2 dezelfde regels op 200× willekeurig verschoven niveaus; F3 200× willekeurige entries met "
      "dezelfde stops en exits. Een echte strategie moet daar ruim boven liggen.*")
    A("")
    A("## Wat dit betekent")
    A("")
    A("- Echte intraday-patronen in valuta zijn klein: 1–2,5 bp per trade bruto. De kosten van een daytrade liggen "
      "rond 0,8–1,2 bp, zelfs bij de krappe spreads van Dukascopy. Bij een gewone broker blijft er niets over.")
    A("- Een gepubliceerd patroon werkt na publicatie minder (hier: van 2,1 naar 0,7 bp bruto).")
    A("- Populaire regels (ronde getallen, London breakout) doen het niet beter dan toeval.")
    A("")
    A("## Kanttekeningen")
    A("")
    A("- Alleen 1h-data (kleiner pas vanaf 2012), dus de ECB-fix (14:15) is afgerond op 14:00.")
    A("- USD/JPY 2010 ontbreekt bij de bron (jan–sep) en telt niet mee.")
    A("- Dukascopy-spreads zijn krapper dan bij de meeste brokers; zie de kolom retail.")
    A("")
    A("Bestanden: [PLAN4.md](PLAN4.md), `research/round4/results/`, `research/round4/research_results.md` (alle 32 "
      "trials), code in `fx/`.")
    return "\n".join(md)


# ----------------------------- ronde 5 ------------------------------------

R5 = ROOT / "research/round5"


def figures5(res, k5):
    fig_dir = R5 / "figures"
    fig_dir.mkdir(exist_ok=True)
    _style()
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    for fam, col, lab in (("G1", BLUE, "G1 momentum 12→16 NY"), ("G2", AQUA, "G2 noise-area, anker Londen")):
        c = _cum(pd.read_csv(R5 / f"results/trades_{fam}.csv"))
        ax.plot(c.index, c / 100, color=col, lw=1.8, label=lab)
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_ylabel("cumulatief netto (%)")
    ax.set_title("Research 2005–2019, 3 paren samen, na kosten", loc="left")
    ax.legend(fontsize=8, loc="lower left")
    _save(fig, fig_dir / "cumulative.png")

    p = res["primaries"]["G2"]
    pairs = list(p["net_by_pair"])
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    x = np.arange(len(pairs))
    ax.bar(x - 0.2, [p["net_by_pair"][q] for q in pairs], 0.4, color=AQUA, label="research 2005–2019")
    if k5:
        ax.bar(x + 0.2, [k5["G2"]["net_by_pair"][q] for q in pairs], 0.4, color=ORANGE, label="2020–2026 (besmet)")
    ax.axhline(0, color=INK2, lw=0.8)
    ax.set_xticks(x, pairs)
    ax.set_ylabel("netto bp per trade")
    ax.set_title("G2 per paar", loc="left")
    ax.legend(fontsize=8)
    _save(fig, fig_dir / "g2_pairs.png")


def build5(res, k5) -> str:
    p = res["primaries"]
    g1, g2 = p["G1"], p["G2"]
    md = []
    A = md.append
    A("# Ronde 5: intraday momentum in valuta")
    A("")
    A("*Research 2005–2019 op EUR/USD, GBP/USD en USD/JPY, met dezelfde data, kosten en engine als ronde 4. "
      "Opzet vooraf vastgelegd in [PLAN5.md](PLAN5.md). 6 trials. Bevestigingsblok C5 (AUD/USD, USD/CAD, USD/CHF) "
      "niet geopend, omdat er geen candidate was. 2020–2026 alleen beschrijvend.*")
    A("")
    A("## Oordeel in gewone taal")
    A("")
    A("**Kort: intraday momentum werkt in spot-valuta niet na kosten. Ook niet in de recente jaren waarin het "
      "bekend werd.**")
    A("")
    A(f"- **G1 – momentum van de dag** (richting van 17:00 tot 12:00 NY vasthouden tot 16:00): "
      f"{nl(g1['net_bp'], sign=True)} bp netto per trade, bruto {nl(g1['gross_bp'], sign=True)}. Niet beter dan "
      f"willekeurig long of short (percentiel {nl(g1['null_percentile_of_real'], 0)}). Rejected.")
    A(f"- **G2 – noise-area breakout** (anker 08:00 Londen): {nl(g2['net_bp'], sign=True)} bp netto, bruto "
      f"{nl(g2['gross_bp'], sign=True)}. De richting van de doorbraak voegt wél iets toe: hij scoort beter dan alle "
      f"200 willekeurige varianten. Maar de kosten ({nl(g2['cost_bp'])} bp) zijn groter dan de winst. Rejected "
      "(bruto wel, netto niet).")
    if k5:
        A(f"- **2020–2026** (alle 6 paren, besmet, alleen beschrijvend): G1 {nl(k5['G1']['net_bp'], sign=True)} bp, G2 "
          f"{nl(k5['G2']['net_bp'], sign=True)} bp netto; bruto rond nul. Het voordeel van G2 is daar ook bruto weg.")
    A("")
    A("## Waarom deze strategieën, en waarom zo getest?")
    A("")
    A("- De vraag was welke strategieën de afgelopen ~5 jaar het best werkten. Intraday momentum had daarvan de "
      "sterkste onderbouwing: Gao e.a. (JFE 2018), Baltussen e.a. (JFE 2021, ook valutafutures) en Zarattini, Aziz & "
      "Barbon (2024, de noise-area op SPY).")
    A("- **Probleem:** wie een strategie kiest omdát hij recent goed werkte, kan die recente jaren niet meer als "
      "toets gebruiken. Daarom: research op 2005–2019 (vóór de strategie bekend werd), bevestiging op drie andere "
      "valutaparen in dezelfde jaren, en 2020–2026 alleen als beschrijving.")
    A("- **Nulmodellen:** G1 met dezelfde vensters maar willekeurig gehusselde richtingen; G2 met dezelfde "
      "entrymomenten en houdduur maar een willekeurige richting. Zo meet je alleen wat het signaal toevoegt, los "
      "van tijd-van-de-dag-effecten (zoals het fix-patroon uit ronde 4).")
    A("")
    A("## Resultaten")
    A("")
    A("![Cumulatief](figures/cumulative.png)")
    A("")
    rows = []
    for k, r in p.items():
        c = r["net_bp_by_slippage_multiplier"]
        rows.append([k, r["n_trades"], nl(r["net_bp"], sign=True), nl(r["gross_bp"], sign=True), nl(r["cost_bp"]),
                     nl(r["sharpe"]), pct(r["boot_pos"]), nl(r["null_p95"], sign=True),
                     f"{nl(r['null_percentile_of_real'], 0)}e", f"**{r['status']}**"])
    A(table(["", "trades", "netto bp", "bruto bp", "kosten bp", "Sharpe", "bootstrap > 0", "nulmodel 95e pct",
             "echt op percentiel", "status"], rows))
    A("")
    trials = res["trials"]
    A(table(["trial", "trades", "netto bp", "bruto bp", "Sharpe"],
            [[f"`{k}`", v["n_trades"], nl(v["net_bp"], sign=True), nl(v["gross_bp"], sign=True), nl(v["sharpe"])]
             for k, v in trials.items()]))
    A("")
    A("![G2 per paar](figures/g2_pairs.png)")
    A("")
    if k5:
        A("### 2020–2026 (besmet, alleen beschrijvend)")
        A("")
        A(table(["", "trades", "netto bp", "bruto bp", "Sharpe"] + list(k5["G1"]["net_by_pair"]),
                [[k, v["n_trades"], nl(v["net_bp"], sign=True), nl(v["gross_bp"], sign=True), nl(v["sharpe"])]
                 + [nl(x, sign=True) for x in v["net_by_pair"].values()] for k, v in k5.items()]))
        A("")
    A("## Wat dit betekent")
    A("")
    A("- In aandelen wordt intraday momentum verklaard door partijen die opties hebben verkocht en mee moeten "
      "handelen met de beweging. In spot-valuta is daar in deze data niets van te zien.")
    A("- Het doorbraak-idee (G2) heeft een klein echt voordeel in de richting, maar dat is kleiner dan de spread. "
      "Hetzelfde beeld als ronde 4: echte patronen bestaan, maar zijn te klein voor daytrading na kosten.")
    A("- De bevestigingsparen (AUD/USD, USD/CAD, USD/CHF) zijn nog ongezien en dus bruikbaar voor een volgende ronde.")
    A("")
    A("Bestanden: [PLAN5.md](PLAN5.md), `research/round5/results/`, code in `fx/momentum.py`, `fx/run5.py`.")
    return "\n".join(md)


def main():
    res4 = json.loads((R4 / "results/results.json").read_text())
    h = R4 / "results/holdout_H4_F1-EU.json"
    h4 = json.loads(h.read_text()) if h.exists() else None
    figures4(res4, h4)
    md4 = build4(res4, h4)
    (R4 / "report.md").write_text(md4, encoding="utf-8")
    (R4 / "report.html").write_text(to_html(md4, R4, "Onderzoek ronde 4", "PLAN4.md"), encoding="utf-8")

    res5 = json.loads((R5 / "results/results.json").read_text())
    k = R5 / "results/k5_descriptive.json"
    k5 = json.loads(k.read_text()) if k.exists() else None
    figures5(res5, k5)
    md5 = build5(res5, k5)
    (R5 / "report.md").write_text(md5, encoding="utf-8")
    (R5 / "report.html").write_text(to_html(md5, R5, "Onderzoek ronde 5", "PLAN5.md"), encoding="utf-8")
    print("research/round4 en round5: report.md en report.html geschreven")


if __name__ == "__main__":
    main()
