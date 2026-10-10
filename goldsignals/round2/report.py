"""Bouw research/round2/report.md en report.html.

Cijfers uit research/round2/results/*.json/csv; interpretatie (met de hand, NA de
resultaten) uit research/round2/text/*.md, met {velden} die hier worden ingevuld.
Draaien: .venv/bin/python -m goldsignals.round2.report
"""
import base64
import json
import re

import numpy as np
import pandas as pd

from goldsignals.config import load_config, project_path
from goldsignals.research.report import CSS, fix_lists
from goldsignals.round2 import families as fam
from goldsignals.round2 import figures as fg
from goldsignals.round2 import run
from goldsignals.round2.indicators import bars

ROOT = project_path("research/round2")
RES = ROOT / "results"


def n(x, d=3):
    return "–" if x is None or (isinstance(x, float) and not np.isfinite(x)) else f"{x:+.{d}f}"


def p(x, d=0):
    return "–" if x is None else f"{x:.{d}f}"


def ci(c):
    return "–" if not c else f"{n(c['est'])} [{n(c['lo'])}; {n(c['hi'])}]"


def table(head, rows):
    return "\n".join(["| " + " | ".join(head) + " |", "|" + "---|" * len(head)] +
                     ["| " + " | ".join(str(c) for c in r) + " |" for r in rows])


def text(name, F):
    path = ROOT / "text" / f"{name}.md"
    if not path.exists():
        return f"_(tekst {name}.md ontbreekt)_"
    return re.sub(r"\{(\w+)\}", lambda m: str(F.get(m.group(1), m.group(0))), path.read_text(encoding="utf-8"))


def equity_curves(cfg, res):
    """Groei van 100 per maand: F2 walk-forward, F2-4h sq20/2R (verkennend) en buy-and-hold."""
    r2 = cfg["round2"]
    end = pd.Timestamp(r2["periods"]["holdout_start"], tz="UTC")
    B = {"4h": bars("4h", end, cfg), "1d": bars("1d", end, cfg)}
    run._init(B)
    w = r2["walkforward"]
    months = pd.period_range(f"{w['first_test_year']}-01", f"{w['last_test_year']}-12", freq="M")

    def curve(t):
        ret = pd.Series(0.0, index=months)
        g = (1 + t["r1x"] / 100).groupby(pd.DatetimeIndex(t["exit_time"]).tz_localize(None).to_period("M")).prod() - 1
        g = g[g.index.isin(months)]
        ret.loc[g.index] = g
        return 100 * (1 + ret).cumprod()

    out = {}
    oos = pd.read_csv(RES / "oos_F2.csv", parse_dates=["exit_time"])
    out["F2 walk-forward (officieel)"] = curve(oos)
    v = {"family": "F2", "timeframe": "4h", "squeeze_pct": 20, "exit": "target_2R"}
    _, t = run.run_variant((v, cfg))
    t = t[(t["year"] >= w["first_test_year"]) & (t["year"] <= w["last_test_year"])]
    out["F2 4h sq20 2R (verkennend)"] = curve(t)
    d = B["1d"]
    m = d.set_index(pd.DatetimeIndex(d["close_time"]).tz_localize(None))["close"].resample("ME").last()
    m.index = m.index.to_period("M")
    m = m[m.index.isin(months)]
    out["buy-and-hold"] = 100 * m / m.iloc[0]
    for k in out:
        out[k].index = out[k].index.to_timestamp()
    return out


def fields(res, z, ex, f2) -> dict:
    F = {"n_trials_r2": res["meta"]["n_trials_round2"], "n_trials_total": res["meta"]["n_trials_total"]}
    for f, s in res["families"].items():
        F[f"{f}_n"], F[f"{f}_r"], F[f"{f}_ci"] = s["n"], n(s["avg_r_1x"]), ci(s["ci"])
        F[f"{f}_rnd"], F[f"{f}_rnd95"], F[f"{f}_pct"] = n(s["random_mean"]), n(s["random_p95"]), p(s["random_pct"])
    bh = res["meta"]["buy_and_hold"]
    F.update(bh_cagr=f"{bh['cagr_pct']:.1f}", bh_dd=f"{bh['max_dd_pct']:.0f}", bh_sharpe=f"{bh['sharpe']:.2f}",
             bh_calmar=f"{bh['calmar']:.2f}")
    if z:
        F.update(z_n=z["n_events"], z_bounce=f"{z['bounce']['est'] * 100:.1f}%",
                 z_bounce_null=f"{z['bounce_null']['null_mean'] * 100:.1f}%", z_bounce_pct=p(z["bounce_null"]["pct"]),
                 z_r=n(z["r"]["est"]), z_r_null=n(z["r_null"]["null_mean"]), z_r_pct=p(z["r_null"]["pct"]),
                 z_r_gross=n(z["r_gross"]), z_decision=z["decision"],
                 z_years_b=f"{round(z['share_years_better_bounce'] * len(z['by_year']))} van de {len(z['by_year'])}",
                 z_years_r=f"{round(z['share_years_better_r'] * len(z['by_year']))} van de {len(z['by_year'])}")
    k = "F2|timeframe=4h|squeeze_pct=20|exit=target_2R"
    if f2 and k in f2:
        s = f2[k]
        F.update(x_n=s["n"], x_r=n(s["avg_r_1x"]), x_ci=ci(s["ci"]), x_r3=n(s["avg_r_3x"]),
                 x_long=n(s["avg_r_long"]), x_short=n(s["avg_r_short"]), x_top5=n(s["without_top5"]),
                 x_sharpe=f"{s['equity']['sharpe']:.2f}", x_calmar=f"{s['equity']['calmar']:.2f}",
                 x_dd=f"{s['equity']['max_dd_pct']:.0f}", x_cagr=f"{s['equity']['cagr_pct']:.1f}",
                 x_dsr=f"{s['dsr']:.2f}", x_dsr_mild=f"{s['dsr_mild']:.2f}",
                 x_win=f"{s['winrate']:.0f}", x_be=f"{s['breakeven_winrate']:.0f}", x_loss_years=s["losing_years"])
        row = ex[ex["variant"] == k.replace("family=", "")]
        if len(row):
            F.update(x_rnd=n(row["random_mean"].iloc[0]), x_rnd_pct=p(row["pct_vs_random"].iloc[0]))
    pp = RES / "power.json"
    if pp.exists():
        pw = json.loads(pp.read_text())
        F.update(pw_per_year=f"{pw['trades_per_year']:.0f}", pw_min=pw["trades_per_year_min"], pw_max=pw["trades_per_year_max"],
                 pw_h2_n=pw["h2"]["n"], pw_h2_lo=pw["h2_n_range"][0], pw_h2_hi=pw["h2_n_range"][1],
                 pw_sd=f"{pw['sd_r']:.2f}", pw_h2_ci=f"{pw['h2']['ci95_halfwidth']:.2f}",
                 pw_h2_mde=f"{pw['h2']['mde_sim']:.2f}", pw_mean=f"{pw['mean_r_research']:.2f}",
                 pw_h2_power=f"{pw['h2']['power_at_research_mean'] * 100:.0f}", pw_years100=f"{pw['years_to_100']:.1f}",
                 pw_f_ci=f"{pw['forward100']['ci95_halfwidth']:.2f}", pw_f_mde=f"{pw['forward100']['mde_sim']:.2f}",
                 pw_f_power=f"{pw['forward100']['power_at_research_mean'] * 100:.0f}")
    return F


def build(cfg) -> str:
    res = json.loads((RES / "results.json").read_text())
    zp = RES / "zone15.json"
    z = json.loads(zp.read_text()) if zp.exists() else None
    ex = pd.read_csv(RES / "explore_variants.csv")
    f2p = RES / "explore_f2.json"
    f2 = json.loads(f2p.read_text()) if f2p.exists() else None
    figs = ROOT / "figures"
    figs.mkdir(exist_ok=True)
    fg.families_forest(res["families"], figs / "families.png")
    fg.entry_vs_random(ex, figs / "entry_vs_random.png")
    fg.equity_vs_bh(equity_curves(cfg, res), figs / "equity.png")
    if z:
        fg.zone15_null(z, figs / "zone15.png")
    F = fields(res, z, ex, f2)
    fams = res["families"]
    md = ["# Ronde 2: bestaat er een strategie op goud die na kosten werkt?", "",
          f"_Research-periode 2006–2018 (walk-forward test-jaren 2010–2018), XAUUSD spot (Dukascopy). "
          f"Hold-out H2 (2019-01 t/m 2020-09) **niet geopend**. Opzet vooraf vastgelegd in "
          f"[PLAN2.md](PLAN2.md). {F['n_trials_r2']} trials in ronde 2, {F['n_trials_total']} in totaal._", "",
          "## Samenvatting in gewone taal", "", text("samenvatting", F), "",
          "## Overzicht per familie (walk-forward, out-of-sample)", "",
          table(["familie", "status", "trades", "gem. R na kosten [95%-int.]", "2× kosten", "3× kosten",
                 "random zelfde exits: gem. / p95", "pctl t.o.v. random", "Sharpe", "max DD", "DSR"],
                [[fg.FAM_NAME[f], f"**{s['status']}**", s["n"], ci(s["ci"]), n(s["avg_r_2x"]), n(s["avg_r_3x"]),
                  f"{n(s['random_mean'])} / {n(s['random_p95'])}", p(s["random_pct"]),
                  f"{s['equity']['sharpe']:.2f}" if s.get("equity") else "–",
                  f"{s['equity']['max_dd_pct']:.0f}%" if s.get("equity") else "–", f"{s['dsr']:.2f}"]
                 for f, s in fams.items()]), "",
          f"Buy-and-hold over 2010–2018: {F['bh_cagr']}% per jaar, max drawdown {F['bh_dd']}%, "
          f"Sharpe {F['bh_sharpe']}, Calmar {F['bh_calmar']}.", "",
          "![Families](figures/families.png)", "",
          "**Redenen per familie:** " + " ".join(f"{fg.FAM_NAME[f]}: {'; '.join(s['reasons'])}." for f, s in fams.items()), "",
          "## Begrippen", "", text("begrippen", F), ""]
    for f in ("F1", "F2", "F3", "F4"):
        s = fams[f]
        by = s["by_year"]
        md += [f"## {fg.FAM_NAME[f]}", "", text(f"{f}_methode", F), "",
               table(["", "waarde"], [
                   ["trades (long / short)", f"{s['n']} ({s['n_long']} / {s['n_short']})"],
                   ["gem. R na kosten 1× / 2× / 3× / bruto", f"{n(s['avg_r_1x'])} / {n(s['avg_r_2x'])} / {n(s['avg_r_3x'])} / {n(s['avg_r_gross'])}"],
                   ["95%-interval (1×)", ci(s["ci"])],
                   ["long / short (1×)", f"{n(s['avg_r_long'])} / {n(s['avg_r_short'])}"],
                   ["win rate (alleen ter info) / break-even", f"{p(s['winrate'])}% / {p(s['breakeven_winrate'])}%"],
                   ["verliesjaren", f"{s['losing_years']} van {len(by)}"],
                   ["random met dezelfde exits: gem. / 95e pctl / positie", f"{n(s['random_mean'])} / {n(s['random_p95'])} / {p(s['random_pct'])}e pctl"],
                   ["Sharpe / Calmar / max DD", f"{s['equity']['sharpe']:.2f} / {s['equity']['calmar']:.2f} / {s['equity']['max_dd_pct']:.0f}%"],
                   ["DSR (streng / mild)", f"{s['dsr']:.2f} / {s['dsr_mild']:.2f}"],
                   ["status", f"**{s['status']}** – {'; '.join(s['reasons'])}"],
               ]), "",
               "**Per test-jaar (totaal R, trades):** " + ", ".join(f"{y}: {v['total_r']:+.1f} ({v['n']})" for y, v in by.items()), "",
               "**Gekozen variant per jaar:** " + ", ".join(f"{c['test_year']}: `{(c['variant'] or '–').replace('family=' + f + '|', '')}`" for c in s["chosen"]), "",
               text(f"{f}_resultaat", F), ""]
        if f == "F4":
            md += ["![Entry of exit](figures/entry_vs_random.png)", ""]
    md += ["## Verkenning: F2 op 4h (achteraf, niet gekozen in de walk-forward)", "", text("F2_verkenning", F), "",
           table(["variant", "trades", "gem. R [95%-int.]", "3× kosten", "long / short", "zonder top-5", "random zelfde exits (pctl)", "Sharpe", "DSR / mild"],
                 [[k.replace("F2|", ""), s["n"], ci(s["ci"]), n(s["avg_r_3x"]), f"{n(s['avg_r_long'])} / {n(s['avg_r_short'])}",
                   n(s["without_top5"]),
                   p(ex.loc[ex["variant"] == k, "pct_vs_random"].iloc[0]) if (ex["variant"] == k).any() else "–",
                   f"{s['equity']['sharpe']:.2f}", f"{s['dsr']:.2f} / {s['dsr_mild']:.2f}"]
                  for k, s in (f2 or {}).items() if not k.startswith("_")]), "",
           "![Equity](figures/equity.png)", ""]
    md += ["## F5 – Zone-toets op 15m", "", text("F5", F), ""]
    if z:
        md += [table(["meetwaarde", "echte zones [95%-int.]", "willekeurige niveaus", "pctl", "jaren beter"], [
            ["bounce-rate", f"{z['bounce']['est'] * 100:.1f}% [{z['bounce']['lo'] * 100:.1f}; {z['bounce']['hi'] * 100:.1f}]",
             f"{z['bounce_null']['null_mean'] * 100:.1f}%", p(z["bounce_null"]["pct"]), F["z_years_b"]],
            ["gem. R 1:2-setup na kosten", ci(z["r"]), n(z["r_null"]["null_mean"]), p(z["r_null"]["pct"]), F["z_years_r"]],
        ]), "", f"Aantal tests: {z['n_events']}. **Beslissing: {z['decision']}.**", "",
            "![Zone 15m](figures/zone15.png)", ""]
    md += ["## Correctie voor het aantal varianten", "", text("correctie", F), "",
           "## Wat ik gecontroleerd heb", "", text("controles", F), "",
           "## Conclusie", "", text("conclusie", F), "",
           "## Voorstel (vraagt jouw akkoord)", "", text("voorstel", F), ""]
    if (RES / "power.json").exists():
        md += ["## Hoeveel trades in H2, en wat kon je daar aantonen?", "", text("power", F), ""]
    if (ROOT / "text" / "besluit.md").exists():
        md += ["## Besluit van de gebruiker", "", text("besluit", F), ""]
    return "\n".join(md)


def to_html(md_text: str) -> str:
    import markdown
    body = markdown.markdown(fix_lists(md_text), extensions=["tables", "sane_lists"])
    body = body.replace("<table>", '<div class="table-wrap"><table>').replace("</table>", "</table></div>")

    def embed(m):
        f = ROOT / m.group(1)
        return f'src="data:image/png;base64,{base64.b64encode(f.read_bytes()).decode()}"' if f.exists() else m.group(0)
    body = re.sub(r'src="(figures/[^"]+\.png)"', embed, body)
    for f in ("PLAN2.md", "FORWARD.md"):
        body = body.replace(f'href="{f}"', f'href="https://github.com/vogelaardille/gold-signals/blob/main/research/round2/{f}"')
    return ("<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>Onderzoek ronde 2</title><style>{CSS}</style></head><body><main>{body}</main></body></html>")


def main():
    cfg = load_config()
    md = build(cfg)
    (ROOT / "report.md").write_text(md, encoding="utf-8")
    (ROOT / "report.html").write_text(to_html(md), encoding="utf-8")
    print("research/round2/report.md en report.html geschreven")


if __name__ == "__main__":
    main()
