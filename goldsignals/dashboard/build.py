"""Statisch dashboard (GitHub Pages): Nu, Chart, Paper trading, Strategieën, Onderzoek.

Mobiel-eerst en donker. Alles wordt als losse HTML-bestanden in site/ geschreven.
Er komen GEEN secrets of lokale paden in: alleen koersen, zones, trades en cijfers.
scripts/secret_scan.py controleert dat voor elke publicatie.

Draaien: .venv/bin/python -m goldsignals.dashboard.build
"""
import json
import shutil
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from goldsignals.backtest.metrics import max_drawdown_pct
from goldsignals.config import load_config, project_path
from goldsignals.data.timeframes import resample
from goldsignals.paper.runner import STRATEGIES_FILE, deviation_warning
from goldsignals.paper.state import State
from goldsignals.sr import zones_as_of

TF_COLORS = {"1d": "#3987e5", "4h": "#d95926", "1h": "#199e70"}
TF_NAME = {"1d": "Daily", "4h": "4h", "1h": "1h"}
STATUS_NL = {"validated": "validated", "candidate": "candidate", "rejected": "rejected", "baseline": "baseline"}
PAGES = [("index.html", "Nu"), ("chart.html", "Chart"), ("paper.html", "Paper trading"),
         ("strategies.html", "Strategieën"), ("research.html", "Onderzoek")]
PLOTLY_CDN = "https://cdn.plot.ly/plotly-2.35.2.min.js"

CSS = """
:root{color-scheme:dark;--bg:#0d0d0d;--surface:#1a1a19;--surface2:#232321;--ink:#f0efec;--ink2:#c3c2b7;
--muted:#898781;--line:#2c2c2a;--accent:#3987e5;--good:#0ca30c;--bad:#e66767;--warn:#fab219}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:10;background:var(--bg);border-bottom:1px solid var(--line)}
nav{display:flex;gap:4px;overflow-x:auto;padding:8px 12px;max-width:1100px;margin:0 auto}
nav a{flex:0 0 auto;padding:8px 12px;border-radius:999px;color:var(--ink2);text-decoration:none;font-size:14px}
nav a.on{background:var(--surface2);color:var(--ink);font-weight:600}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:1.3rem;margin:.2rem 0 1rem}
h2{font-size:1.05rem;margin:1.6rem 0 .6rem;color:var(--ink)}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.card .k{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.04em}
.card .v{font-size:1.5rem;font-weight:600;margin-top:2px}
.card .s{color:var(--ink2);font-size:13px}
.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--surface)}
table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}
th,td{padding:8px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--ink2);font-weight:600;background:var(--surface2)}
tr:last-child td{border-bottom:0}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line)}
.pill.validated{color:var(--good);border-color:var(--good)} .pill.candidate{color:var(--warn);border-color:var(--warn)}
.pill.rejected{color:var(--muted)} .pill.baseline{color:var(--ink2)}
.pos{color:var(--good)} .neg{color:var(--bad)} .muted{color:var(--muted)}
.note{color:var(--ink2);font-size:13px}
.warn{color:var(--warn)}
.plot{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:4px;margin-top:8px}
footer{max-width:1100px;margin:24px auto;padding:0 16px 24px;color:var(--muted);font-size:12px}
"""


def page(title: str, active: str, body: str, updated: str, plotly: bool = False) -> str:
    nav = "".join(f'<a href="{href}" class="{"on" if href == active else ""}">{name}</a>' for href, name in PAGES)
    js = f'<script src="{PLOTLY_CDN}"></script>' if plotly else ""
    return (f"<!doctype html><html lang='nl'><head><meta charset='utf-8'>"
            f"<meta name='viewport' content='width=device-width,initial-scale=1'>"
            f"<title>{escape(title)} · Gold signals</title><style>{CSS}</style>{js}</head><body>"
            f"<header><nav>{nav}</nav></header><main>{body}</main>"
            f"<footer>Paper trading met fictief geld (10.000 euro, 1% risico per trade). Geen advies, geen echt geld. "
            f"Data: Dukascopy XAU/USD spot (bid). Bijgewerkt: {escape(updated)}.</footer></body></html>")


def fmt_time(t, tz="Europe/Amsterdam") -> str:
    if t is None or (isinstance(t, float) and np.isnan(t)) or pd.isna(t):
        return "–"
    return pd.Timestamp(t).tz_convert(tz).strftime("%d-%m-%Y %H:%M")


def cls(x) -> str:
    return "pos" if x > 0 else "neg" if x < 0 else ""


def table(headers, rows) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    trs = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    if not rows:
        trs = f"<tr><td colspan='{len(headers)}' class='muted'>Nog niets.</td></tr>"
    return f"<div class='table-wrap'><table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table></div>"


def fig_html(fig, div_id: str) -> str:
    fig.update_layout(template="plotly_dark", paper_bgcolor="#1a1a19", plot_bgcolor="#1a1a19",
                      font=dict(color="#c3c2b7", size=12))
    if not fig.layout.margin.t:
        fig.update_layout(margin=dict(l=48, r=12, t=36, b=36))
    return "<div class='plot'>" + fig.to_html(include_plotlyjs=False, full_html=False, div_id=div_id,
                                              config={"displaylogo": False, "responsive": True}) + "</div>"


# ---------------------------------------------------------------------------

def load_strategies() -> dict:
    p = project_path(STRATEGIES_FILE)
    return json.loads(p.read_text()) if p.exists() else {}


def page_now(price, as_of, zones, state, strategies, cfg, updated) -> str:
    sup = zones[zones["high"] < price].sort_values("high", ascending=False).head(3)
    res = zones[zones["low"] > price].sort_values("low").head(3)
    zrows = []
    for kind, df in (("resistance", res.iloc[::-1]), ("support", sup)):
        for _, z in df.iterrows():
            zrows.append([kind, f"{z['low']:.2f} – {z['high']:.2f}", z["timeframes"], f"{z['score']:.1f}",
                          int(z["touches"]), f"{z['distance_pct']:+.2f}%"])
    open_t = state.open_trades() if state else pd.DataFrame()
    trows = [[escape(r["strategy"]), "long" if r["direction"] == 1 else "short", f"{r['entry']:.2f}",
              f"{r['stop']:.2f}", f"{r['target']:.2f}", f"{float(r['units_oz']):.2f}",
              f"<span class='{cls(price - r['entry'] if r['direction'] == 1 else r['entry'] - price)}'>"
              f"{(price - r['entry']) * r['direction'] / abs(r['entry'] - r['stop']):+.2f}R</span>",
              fmt_time(r["entry_time"])] for _, r in open_t.iterrows()]
    active = [k for k, v in strategies.items() if v.get("status") in ("candidate", "validated")]
    meta = state.meta if state else {}
    lat = meta.get("last_latency_min")
    cards = (f"<div class='cards'>"
             f"<div class='card'><div class='k'>XAUUSD spot</div><div class='v'>{price:.2f}</div>"
             f"<div class='s'>slot candle tot {fmt_time(as_of)}</div></div>"
             f"<div class='card'><div class='k'>Open paper trades</div><div class='v'>{len(open_t)}</div>"
             f"<div class='s'>{len(state.pending) if state else 0} wachtend op entry</div></div>"
             f"<div class='card'><div class='k'>Actieve strategieën</div><div class='v'>{len(active)}</div>"
             f"<div class='s'>alleen candidate / validated</div></div>"
             f"<div class='card'><div class='k'>Laatste run</div><div class='v' style='font-size:1rem'>"
             f"{fmt_time(meta.get('last_run'))}</div><div class='s'>data-vertraging: "
             f"{'–' if lat is None else f'{lat:.0f} min'}</div></div></div>")
    body = (f"<h1>Nu</h1>{cards}<h2>Dichtstbijzijnde zones (methode {cfg['notify']['zone_alert']['method']})</h2>"
            + table(["soort", "zone", "timeframes", "score", "aanrakingen", "afstand"], zrows)
            + "<p class='note'>Score = timeframe-gewicht × aantal aanrakingen, recente aanrakingen tellen zwaarder. "
              "Een zone is geen voorspelling; zie Onderzoek voor wat ze in het verleden waard waren.</p>"
            + "<h2>Open paper trades</h2>"
            + table(["strategie", "richting", "entry", "stop", "target", "oz", "nu", "sinds"], trows))
    if not active:
        body += ("<p class='note warn'>Er handelt op dit moment geen enkele strategie: geen strategie haalde de "
                 "status candidate. Alleen zone-alerts en dit dashboard zijn actief.</p>")
    return page("Nu", "index.html", body, updated)


def page_chart(candles, zones, state, cfg, updated) -> str:
    d = cfg["data"]
    body = "<h1>Chart</h1><p class='note'>Tik in de legenda op een timeframe om de zones aan/uit te zetten. Knijp om te zoomen.</p>"
    for tf, months in (("4h", 4), ("1h", 1)):
        c = resample(candles, tf, d["session_tz"], d["session_close_hour"]) if tf != "1h" else candles
        c = c[c.index >= c.index[-1] - pd.DateOffset(months=months)]
        x = c.index.tz_convert("Europe/Amsterdam").strftime("%d-%m %H:%M")
        fig = go.Figure(go.Candlestick(x=x, open=c["open"], high=c["high"], low=c["low"], close=c["close"],
                                       name="XAUUSD", showlegend=False,
                                       increasing=dict(line=dict(color="#c3c2b7", width=1), fillcolor="#c3c2b7"),
                                       decreasing=dict(line=dict(color="#6b6a66", width=1), fillcolor="#3a3a37")))
        lo, hi = c["low"].min(), c["high"].max()
        pad = (hi - lo) * 0.04
        vis = zones[(zones["high"] >= lo - pad) & (zones["low"] <= hi + pad)]
        vis = vis.sort_values("score", ascending=False).head(cfg["dashboard"]["chart_max_zones"])
        shown = set()
        for _, z in vis.iterrows():
            tf_z = z["timeframe"]
            fig.add_trace(go.Scatter(
                x=[x[0], x[-1], x[-1], x[0], x[0]], y=[z["low"], z["low"], z["high"], z["high"], z["low"]],
                fill="toself", mode="lines", line=dict(width=0, color=TF_COLORS[tf_z]),
                opacity=0.22,
                legendgroup=tf_z, name=f"{TF_NAME[tf_z]}-zones", showlegend=tf_z not in shown,
                hovertemplate=f"{z['low']:.2f} – {z['high']:.2f}<br>{z['timeframes']} · score {z['score']:.1f}"
                              f"<br>{int(z['touches'])} aanrakingen<extra></extra>"))
            shown.add(tf_z)
        if state is not None:
            for _, t in state.open_trades().iterrows():
                for y, col, lab in ((t["entry"], "#f0efec", "entry"), (t["stop"], "#e66767", "stop"),
                                    (t["target"], "#0ca30c", "target")):
                    fig.add_hline(y=float(y), line=dict(color=col, width=1, dash="dash"),
                                  annotation_text=f"{lab} {float(y):.2f}", annotation_font_color=col)
        # Categorie-as (geen gaten voor weekenden); zelf een paar korte labels kiezen
        ticks = list(range(0, len(x), max(1, len(x) // 4)))
        local_idx = c.index.tz_convert("Europe/Amsterdam")
        fig.update_layout(height=480, margin=dict(l=8, r=8, t=8, b=8),
                          xaxis=dict(type="category", rangeslider=dict(visible=False), tickangle=0,
                                     tickvals=[x[k] for k in ticks], ticktext=[local_idx[k].strftime("%d-%m") for k in ticks]),
                          yaxis=dict(range=[lo - pad, hi + pad], side="right"),
                          legend=dict(orientation="h", y=1.0, x=0, yanchor="bottom"), dragmode="pan")
        body += f"<h2>XAUUSD {tf} · laatste {months} maand{'en' if months > 1 else ''}</h2>" + fig_html(fig, f"chart_{tf}")
    return page("Chart", "chart.html", body, updated, plotly=True)


def page_paper(state, strategies, cfg, updated) -> str:
    acc = cfg["account"]
    closed = state.closed_trades() if state else pd.DataFrame()
    body = "<h1>Paper trading</h1><p class='note'>Fictief geld: elke strategie start met € 10.000 en riskeert 1% per trade. Kosten (spread + slippage) zijn meegerekend.</p>"
    rows, fig = [], go.Figure()
    for sid, s in strategies.items():
        if s.get("status") not in ("candidate", "validated") and not (len(closed) and (closed["strategy"] == sid).any()):
            continue
        mine = closed[closed["strategy"] == sid].sort_values("exit_time") if len(closed) else closed
        r = mine["r"].astype(float) if len(mine) else pd.Series(dtype=float)
        eq = pd.Series(np.r_[acc["start_equity_eur"], acc["start_equity_eur"] + mine["pnl_eur"].astype(float).cumsum()]) if len(mine) else pd.Series([acc["start_equity_eur"]])
        warn = deviation_warning(s, mine, cfg["paper"]) if len(mine) else ""
        bt = s.get("backtest", {})
        rows.append([escape(sid), f"<span class='pill {s['status']}'>{s['status']}</span>", len(mine),
                     f"{(r > 0).mean() * 100:.0f}%" if len(r) else "–",
                     f"<span class='{cls(r.mean() if len(r) else 0)}'>{r.mean():+.2f}R</span>" if len(r) else "–",
                     f"€ {eq.iloc[-1]:,.0f}", f"{max_drawdown_pct(eq):.1f}%",
                     f"{bt.get('avg_r', float('nan')):+.2f}R" if bt else "–",
                     f"<span class='warn'>{escape(warn)}</span>" if warn else ""])
        if len(mine):
            fig.add_trace(go.Scatter(x=[mine["entry_time"].iloc[0]] + list(mine["exit_time"]), y=eq, mode="lines",
                                     name=sid, line=dict(width=2)))
    body += "<h2>Per strategie</h2>" + table(
        ["strategie", "status", "trades", "winrate", "gem. R", "equity", "max DD", "backtest gem. R", "waarschuwing"], rows)
    if fig.data:
        fig.update_layout(height=360, title="Equity-curve (paper)", yaxis_title="€")
        body += fig_html(fig, "equity")
    else:
        body += "<p class='note'>Nog geen gesloten paper trades, dus nog geen equity-curve.</p>"
    trows = []
    if state is not None and len(state.trades):
        for _, t in state.trades.sort_values("entry_time", ascending=False).head(200).iterrows():
            rv = float(t["r"]) if pd.notna(t["r"]) else None
            trows.append([fmt_time(t["entry_time"]), escape(t["strategy"]), "long" if t["direction"] == 1 else "short",
                          f"{t['entry']:.2f}", f"{t['stop']:.2f}", f"{t['target']:.2f}", t["status"],
                          t["result"] if pd.notna(t["result"]) else "",
                          f"<span class='{cls(rv)}'>{rv:+.2f}R</span>" if rv is not None else "",
                          f"€ {float(t['pnl_eur']):+.0f}" if pd.notna(t["pnl_eur"]) else ""])
    body += "<h2>Trades</h2>" + table(["entry", "strategie", "richting", "entry", "stop", "target", "status",
                                       "uitkomst", "R", "€"], trows)
    return page("Paper trading", "paper.html", body, updated, plotly=bool(fig.data))


def page_strategies(updated) -> str:
    p = project_path("research/results/leaderboard.csv")
    body = ("<h1>Strategieën</h1><p class='note'><b>rejected</b>: haalt de eisen niet en handelt nooit. "
            "<b>candidate</b>: ≥ 100 out-of-sample trades in de walk-forward, positief na kosten, niet gedragen door één jaar; "
            "handelt op paper. <b>validated</b>: daarbovenop één keer positief op de hold-out (≥ 30 trades), "
            "overleeft de correctie voor het aantal geprobeerde varianten (deflated Sharpe) en is beter dan "
            "willekeurige entries in dezelfde richting. Alle cijfers zijn out-of-sample (walk-forward test-vensters), na kosten. "
            "Uitgebreid verslag met kosten, long/short en hold-out: "
            "<a href='https://github.com/vogelaardille/gold-signals/blob/main/research/backtest.md'>research/backtest.md</a>.</p>")
    if not p.exists():
        return page("Strategieën", "strategies.html", body + "<p class='note'>Nog geen leaderboard.</p>", updated)
    lb = pd.read_csv(p)
    rows = []
    for _, r in lb.iterrows():
        def f(k, fmt):
            v = r.get(k)
            return "–" if pd.isna(v) else fmt.format(v)
        rows.append([escape(str(r["strategy"])), f"<span class='pill {r['status']}'>{r['status']}</span>",
                     f("n", "{:.0f}"), f("winrate", "{:.0f}%"),
                     f"<span class='{cls(r['avg_r'] if pd.notna(r['avg_r']) else 0)}'>{f('avg_r', '{:+.3f}')}</span>",
                     f("total_r", "{:+.1f}"), f("max_dd_pct", "{:.1f}%"), f("return_pct", "{:+.1f}%"),
                     f("avg_r_2x", "{:+.3f}"), f("dsr", "{:.2f}"), f("excess_vs_random", "{:+.3f}"),
                     f("holdout_avg_r", "{:+.3f}"), escape(str(r.get("reasons", "")))])
    body += table(["strategie", "status", "trades", "winrate", "gem. R", "totaal R", "max DD", "rendement",
                   "gem. R bij 2× kosten", "DSR", "t.o.v. random", "hold-out gem. R", "toelichting"], rows)
    return page("Strategieën", "strategies.html", body, updated)


def page_research(updated, src_rel: str = "research/report.html", other: tuple = None) -> str:
    """Een onderzoeksrapport met de dashboard-navigatie erboven. other = (href, tekst) van
    een link naar het andere rapport (ronde 1 <-> ronde 2)."""
    src = project_path(src_rel)
    if not src.exists():
        return page("Onderzoek", "research.html", "<h1>Onderzoek</h1><p>Nog geen rapport.</p>", updated)
    html = src.read_text(encoding="utf-8")
    nav = "".join(f'<a href="{href}" class="{"on" if href == "research.html" else ""}">{name}</a>' for href, name in PAGES)
    bar = (f"<header style='position:sticky;top:0;z-index:10;background:#0d0d0d;border-bottom:1px solid #2c2c2a'>"
           f"<nav style='display:flex;gap:4px;overflow-x:auto;padding:8px 12px'>{nav}</nav></header>")
    if other:
        bar += (f"<div style='max-width:860px;margin:12px auto 0;padding:0 16px'><a href='{other[0]}' "
                f"style='display:block;padding:10px 14px;border:1px solid #2c2c2a;border-radius:12px;"
                f"background:#1a1a19;color:#3987e5;text-decoration:none'>{other[1]} →</a></div>")
    style = ("<style>nav a{flex:0 0 auto;padding:8px 12px;border-radius:999px;color:#c3c2b7;text-decoration:none;font-size:14px}"
             "nav a.on{background:#232321;color:#f0efec;font-weight:600}</style>")
    return html.replace("<body>", "<body>" + bar, 1).replace("</head>", style + "</head>", 1)


def build_site(cfg: dict, state_dir: Path = None, out_dir: Path = None, candles: pd.DataFrame = None) -> Path:
    from goldsignals.market import load_candles
    out = out_dir or project_path("site")
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    candles = load_candles(cfg) if candles is None else candles
    state = State(state_dir) if state_dir and Path(state_dir).exists() else None
    as_of = candles.index[-1] + pd.Timedelta(hours=1)
    r = zones_as_of(candles, as_of, cfg, cfg["notify"]["zone_alert"]["method"])
    strategies = load_strategies()
    updated = fmt_time(pd.Timestamp.now(tz="UTC")) + " (Amsterdam)"
    files = {
        "index.html": page_now(r.price, as_of, r.merged, state, strategies, cfg, updated),
        "chart.html": page_chart(candles, r.merged, state, cfg, updated),
        "paper.html": page_paper(state, strategies, cfg, updated),
        "strategies.html": page_strategies(updated),
        "research.html": page_research(updated, "research/report.html",
                                       ("research2.html", "Ronde 2: trend, compressie, mean reversion, macro, zones op 15m")),
    }
    if project_path("research/round2/report.html").exists():
        files["research2.html"] = page_research(updated, "research/round2/report.html",
                                                ("research.html", "Terug naar ronde 1 (S/R-zones en strategieën)"))
    for name, html in files.items():
        (out / name).write_text(html, encoding="utf-8")
    lb = project_path("research/results/leaderboard.csv")
    if lb.exists():
        shutil.copy(lb, out / "leaderboard.csv")
    (out / ".nojekyll").write_text("")
    return out


if __name__ == "__main__":
    cfg = load_config()
    print(build_site(cfg, project_path(cfg["paper"]["state_dir"])))
