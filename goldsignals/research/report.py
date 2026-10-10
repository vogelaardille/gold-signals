"""Bouw research/report.md en research/report.html uit results.json + teksten.

De cijfers en tabellen komen automatisch uit research/results/results.json.
De interpretatie (in gewone taal) staat in research/text/*.md; die is met de hand
geschreven NA het bekijken van de resultaten. In die teksten kun je {sleutel}-velden
gebruiken die hieronder in `fields()` worden gevuld, zodat getallen altijd kloppen.

Draaien: .venv/bin/python -m goldsignals.research.report
"""
import base64
import json
import re

import markdown

from goldsignals.config import load_config, project_path
from goldsignals.research.analysis import FILTERS, SPLIT_LABEL

ROOT = project_path("research")


def pct(x, d=1):
    return "–" if x is None else f"{x * 100:.{d}f}%"


def num(x, d=3, sign=True):
    return "–" if x is None else (f"{x:+.{d}f}" if sign else f"{x:.{d}f}")


def ci(d, f=num):
    return f"{f(d['est'])} [{f(d['lo'])}; {f(d['hi'])}]"


def text(name: str, fields: dict) -> str:
    p = ROOT / "text" / f"{name}.md"
    if not p.exists():
        return f"_(tekst {name}.md ontbreekt)_"
    t = p.read_text(encoding="utf-8")
    return re.sub(r"\{(\w+)\}", lambda m: str(fields.get(m.group(1), m.group(0))), t)


def fields(res: dict) -> dict:
    q1, q4 = res["q1"], res["q4"]
    ex = res["example"]
    f = {
        "n_events": f"{res['meta']['n_events']:,}".replace(",", "."),
        "n_setups": f"{res['meta']['n_setups']:,}".replace(",", "."),
        "bounce": pct(q1["bounce"]), "bounce_null": pct(q1["bounce_null"]),
        "bounce_lo": pct(q1["bounce_lo"]), "bounce_hi": pct(q1["bounce_hi"]),
        "bounce_pct": f"{q1['bounce_pct']:.0f}", "r": num(q1["r"]), "r_null": num(q1["r_null"]),
        "r_lo": num(q1["r_lo"]), "r_hi": num(q1["r_hi"]), "r_pct": f"{q1['r_pct']:.0f}",
        "r_edge": num(q1["r_edge"]), "bounce_edge": f"{q1['bounce_edge'] * 100:+.1f} procentpunt",
        "brk": pct(q1["brk"]), "brk_null": pct(q1["brk_null"]),
        "ex_time": ex["time"][:16].replace("T", " "), "ex_zlow": f"{ex['zlow']:.2f}",
        "ex_zhigh": f"{ex['zhigh']:.2f}", "ex_atr": f"{ex['atr_1h']:.2f}", "ex_tf": ex["timeframe"],
        "ex_entry": f"{ex['entry']:.2f}", "ex_r": num(ex["r"], 2), "ex_mfe": f"{ex['mfe']:.1f}",
        "ex_mae": f"{ex['mae']:.1f}", "ex_bounce_level": f"{ex['zhigh'] + ex['atr_1h']:.2f}",
        "ex_break_level": f"{ex['zlow'] - 0.5 * ex['atr_1h']:.2f}",
        "ex_stop": f"{ex['zlow'] - 0.25 * ex['atr_1h']:.2f}",
        "cost": f"{res['meta']['cost_per_oz']:.2f}",
        "q4_retest": pct(q4["retest"]), "q4_retest_null": pct(q4["retest_null"]["null_mean"]),
        "q4_r_retest": num(q4["r_retest"]), "q4_r_retest_null": num(q4["r_retest_null"]["null_mean"]),
        "q4_r_cont": num(q4["r_cont"]), "q4_r_cont_null": num(q4["r_cont_null"]["null_mean"]),
    }
    return f


def table(headers, rows) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def compare_rows(items, label_fn=lambda g: g):
    rows = []
    for it in items:
        rows.append([label_fn(it["group"]), it["n_r"],
                     f"{pct(it['bounce'])} ({pct(it['bounce_null'])})",
                     f"{num(it['r'])} [{num(it['r_lo'])}; {num(it['r_hi'])}]",
                     num(it["r_null"]), f"{num(it['r_edge'])} [{num(it['r_edge_lo'])}; {num(it['r_edge_hi'])}]",
                     f"{it['r_pct']:.0f}"])
    return rows


CMP_HEAD = ["groep", "setups", "bounce echt (nul)", "R echt [95%-int.]", "R nul", "verschil [95%-int.]", "pctl"]


def build(res: dict) -> str:
    F = fields(res)
    q1, q2, q3, q4, q5, q6 = (res[k] for k in ("q1", "q2", "q3", "q4", "q5", "q6"))
    md = ["# Onderzoek: wat werkt er echt aan support/resistance op goud?", "",
          f"_Research-periode {res['meta']['first_event'][:10]} t/m {res['meta']['last_event'][:10]} "
          f"(XAUUSD spot, 1h). Hold-out (laatste 12 maanden) niet gebruikt. Opzet vooraf vastgelegd "
          f"in [PLAN.md](PLAN.md)._", "",
          "## Samenvatting in gewone taal", "", text("samenvatting", F), "",
          "## Begrippen, met een voorbeeld uit de data", "", text("begrippen", F), "",
          "![Voorbeeld](figures/voorbeeld.png)", ""]

    # V1
    md += ["## Vraag 1 – Voorspellen zones iets, vergeleken met willekeurige niveaus?", "",
           "**Methode.** Elke keer dat een 1h-candle een bekende zone raakt is een *test*; we meten of de "
           "koers daarna 1 ATR wegveert (*bounce*) of 0,5 ATR erdoor sluit (*break*), en wat een vaste "
           "1:2-trade had opgeleverd. Hetzelfde doen we 200 keer met de zones verschoven naar willekeurige "
           "niveaus (zelfde breedte, aantal en eigenschappen). Is het echte resultaat beter dan vrijwel alle "
           "verschoven versies, dan zit er iets in de zones zelf.", "",
           table(["meetwaarde", "echte zones [95%-int.]", "nulmodel (gem. [2,5–97,5%])", "percentiel echt"], [
               ["bounce-rate", ci({"est": q1["bounce"], "lo": q1["bounce_lo"], "hi": q1["bounce_hi"]}, pct),
                f"{pct(q1['bounce_null'])} [{pct(q1['bounce_null_lo'])}; {pct(q1['bounce_null_hi'])}]",
                f"{q1['bounce_pct']:.0f}"],
               ["gem. R (1:2, na kosten)", ci({"est": q1["r"], "lo": q1["r_lo"], "hi": q1["r_hi"]}),
                f"{num(q1['r_null'])} [{num(q1['r_null_lo'])}; {num(q1['r_null_hi'])}]", f"{q1['r_pct']:.0f}"],
               ["break-rate", pct(q1["brk"]), pct(q1["brk_null"]), ""],
               ["mediaan MFE / MAE (ATR)", f"{q1['mfe_med']:.2f} / {q1['mae_med']:.2f}",
                f"{q1['mfe_med_null']:.2f} / {q1['mae_med_null']:.2f}", ""],
               ["aantal tests / setups", f"{res['meta']['n_events']} / {res['meta']['n_setups']}",
                f"{q1['null_n_mean']:.0f} tests", ""],
           ]), "", "![Nulmodel](figures/v1_nulmodel.png)", "", text("q1", F), ""]

    # V2
    md += ["## Vraag 2 – Welke zone-eigenschappen doen ertoe?", "",
           "**Methode.** Dezelfde tests, opgesplitst naar één eigenschap tegelijk (alleen de opsplitsingen uit "
           "PLAN.md). Per groep vergelijken we met het nulmodel in *dezelfde* groep, zodat bijvoorbeeld een "
           "trend-effect niet ten onrechte aan de zone wordt toegeschreven. 'pctl' = percentiel van het echte "
           "resultaat in het nulmodel (50 replicaties).", ""]
    for split, items in q2.items():
        md += [f"**{SPLIT_LABEL[split]}**", "", table(CMP_HEAD, compare_rows(items)), ""]
    md += ["![Eigenschappen](figures/v2_eigenschappen.png)", "", text("q2", F), ""]

    # V3
    md += ["## Vraag 3 – Methode A (clustering) versus B (KDE)", "",
           "**Methode.** Exact dezelfde meting op de zones van methode B, met een eigen nulmodel "
           "(200 replicaties). Het verschil tussen echte en verschoven zones is de maat, niet het ruwe getal: "
           "B heeft minder en bredere zones, dus andere aantallen.", "",
           table(CMP_HEAD, compare_rows([{**q3["A"], "group": "A totaal"}, {**q3["B"], "group": "B totaal"}]
                                        + [{**x, "group": f"A {x['group']}"} for x in q3["A_side"]]
                                        + [{**x, "group": f"B {x['group']}"} for x in q3["B_side"]])),
           "", text("q3", F), ""]

    # V4
    def q4row(key, label, f=num):
        c, nl = q4[f"{key}_ci"], q4[f"{key}_null"]
        return [label, ci(c, f), f(nl["null_mean"]), f"{nl['pct']:.0f}"]
    md += ["## Vraag 4 – Wat gebeurt er na een doorbraak?", "",
           f"**Methode.** We nemen alle *break*-uitkomsten uit vraag 1 ({q4['n_break']} stuks). Daarna: komt de "
           "koers binnen 48 uur terug naar de zone (*retest*)? En wat levert een 1:2-trade in de "
           "doorbraakrichting op, direct na de break of pas bij de retest? Vergeleken met dezelfde meting "
           "op verschoven zones.", "",
           table(["meetwaarde", "echt [95%-int.]", "nulmodel", "pctl"], [
               q4row("retest", "kans op retest binnen 48u", pct),
               q4row("retest_held", "retest houdt (slot aan breakout-kant)", pct),
               q4row("r_cont", f"R doorzetten direct na break (n={q4['n_cont_trades']})"),
               q4row("r_retest", f"R instap bij retest (n={q4['n_retest_trades']})"),
           ]), "", text("q4", F), ""]

    # V5
    rows = []
    for it in sorted(q5["by_year"], key=lambda x: (x["side"], x["year"])):
        rows.append([it["year"], it["side"], it["n_r"], ci(it["r"]), num(it["r_null"]["null_mean"]),
                     num(it["r_random"]), f"{it['r_null']['pct']:.0f}"])
    bh = q5["bh"]
    md += ["## Vraag 5 – Is het stabiel? Per jaar, regime, long en short", "",
           "**Methode.** De vaste 1:2-setup per kalenderjaar, apart voor long (support) en short (resistance), "
           "naast het nulmodel en naast willekeurige entries met dezelfde stopafstanden. Goud steeg in deze "
           "periode sterk, dus longs verdienen 'vanzelf'; het verschil met willekeurige longs laat zien wat de "
           "zone toevoegt.", "",
           table(["jaar", "kant", "setups", "R echt [95%-int.]", "R nul", "R willekeurig", "pctl"], rows), "",
           "**Buy-and-hold per jaar:** " + ", ".join(f"{k}: {v:+.1f}%" for k, v in bh.items()), "",
           "**Per walk-forward-testvenster (kwartaal, beide kanten):**", "",
           table(CMP_HEAD, compare_rows(q5["by_wf"], lambda g: f"venster {g}")), ""]
    for split, lab in (("vol_regime", "volatiliteit"), ("trend_rel", "daily-trend")):
        rr = [[s, g, v["n"], ci(v)] for s, gg in q5[split].items() for g, v in gg.items()]
        md += [f"**Per {lab}, long/short apart (alleen echte zones):**", "",
               table(["kant", "groep", "setups", "R [95%-int.]"], rr), ""]
    md += ["![Per jaar](figures/v5_per_jaar.png)", "", text("q5", F), ""]

    # V6
    rows = []
    for f, it in q6.items():
        rows.append([it["label"], f"{it['n_on']} / {it['n_off']}", ci(it["r_on"]), num(it["r_off"]),
                     ci(it["diff"]), num(it["diff_null"]["null_mean"]),
                     f"{num(it['did'])} [{num(it['did_lo'])}; {num(it['did_hi'])}]"])
    md += ["## Vraag 6 – Voegt een bevestiging iets toe?", "",
           "**Methode.** We splitsen de setups uit vraag 1 in 'met' en 'zonder' bevestiging en vergelijken de "
           "gemiddelde R. Om te zien of het filter werkt *door de zone* of ook zonder zone, doen we hetzelfde "
           "op verschoven zones; het verschil daartussen staat in de laatste kolom.", "",
           table(["filter", "setups met/zonder", "R met [95%-int.]", "R zonder", "verschil [95%-int.]",
                  "verschil nulmodel", "extra door zone [95%-int.]"], rows), "",
           "![Bevestiging](figures/v6_bevestiging.png)", "", text("q6", F), ""]

    md += ["## Wat betekent dit voor strategieën? (hypotheses voor deel B)", "", text("hypotheses", F), "",
           "## Beperkingen", "", text("beperkingen", F), ""]
    return "\n".join(md)


CSS = """
:root{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
--line:#2c2c2a;--accent:#3987e5}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:860px;margin:0 auto;padding:16px}
h1{font-size:1.5rem;line-height:1.25}
h2{font-size:1.2rem;margin-top:2.2rem;padding-top:1rem;border-top:1px solid var(--line)}
a{color:var(--accent)}
img{max-width:100%;height:auto;border-radius:8px;background:var(--surface)}
.table-wrap{overflow-x:auto;margin:1rem 0;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;font-size:.82rem;font-variant-numeric:tabular-nums;min-width:100%}
th,td{padding:6px 8px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--ink2);background:var(--surface);font-weight:600}
code{background:var(--surface);padding:1px 4px;border-radius:4px}
blockquote{margin:1rem 0;padding:.5rem 1rem;border-left:3px solid var(--accent);background:var(--surface);color:var(--ink2)}
em{color:var(--ink2)}
"""


def to_html(md_text: str, embed_images: bool = True) -> str:
    body = markdown.markdown(md_text, extensions=["tables"])
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")
    if embed_images:
        def embed(m):
            p = ROOT / m.group(1)
            if not p.exists():
                return m.group(0)
            b64 = base64.b64encode(p.read_bytes()).decode()
            return f'src="data:image/png;base64,{b64}"'
        body = re.sub(r'src="(figures/[^"]+\.png)"', embed, body)
    body = body.replace('href="PLAN.md"', 'href="https://github.com/vogelaardille/gold-signals/blob/main/research/PLAN.md"')
    return ("<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Onderzoek S/R goud</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def main():
    load_config()
    res = json.loads((ROOT / "results" / "results.json").read_text())
    md_text = build(res)
    (ROOT / "report.md").write_text(md_text, encoding="utf-8")
    (ROOT / "report.html").write_text(to_html(md_text), encoding="utf-8")
    print("research/report.md en research/report.html geschreven")


if __name__ == "__main__":
    main()
