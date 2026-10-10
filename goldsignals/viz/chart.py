"""Interactieve Plotly-chart: candles + S/R-zones als horizontale banden.

- Kleur van een zone = zijn belangrijkste timeframe (daily/4h/1h).
- Hoe sterker de zone (score), hoe minder doorzichtig en hoe dikker de rand.
- Beweeg met de muis over het bolletje rechts van een zone voor de details.
- De candles zijn bewust grijs, zodat de gekleurde zones opvallen.
"""
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

TF_LABEL = {"1d": "Daily", "4h": "4h", "1h": "1h"}
METHOD_LABEL = {"A": "methode A (pivot-clustering)", "B": "methode B (KDE)"}


def plot_zones(candles: pd.DataFrame, merged: pd.DataFrame, price: float, method: str,
               cfg: dict, path: Path) -> Path:
    ocfg = cfg["output"]
    colors = ocfg["colors"]
    tf = ocfg["chart_timeframe"]

    start = candles.index[-1] - pd.DateOffset(months=ocfg["chart_months"])
    c = candles[candles.index >= start]

    # x-as als categorie (tekst) i.p.v. tijd: zo zijn weekenden en de dagelijkse
    # handelspauze geen lege gaten in de chart.
    x = c.index.strftime("%Y-%m-%d %H:%M")

    y_min, y_max = c["low"].min(), c["high"].max()
    margin = (y_max - y_min) * 0.05
    y_lo, y_hi = y_min - margin, y_max + margin

    visible = merged[(merged["high"] >= y_lo) & (merged["low"] <= y_hi)]
    visible = visible.sort_values("score", ascending=False).head(ocfg["chart_max_zones"])
    max_score = visible["score"].max() if len(visible) else 1.0

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=x, open=c["open"], high=c["high"], low=c["low"], close=c["close"],
        name=f"XAUUSD {tf}", showlegend=False,
        increasing=dict(line=dict(color="#8a8986", width=1), fillcolor="#e4e3df"),
        decreasing=dict(line=dict(color="#52514e", width=1), fillcolor="#52514e"),
    ))

    for _, z in visible.iterrows():
        rel = z["score"] / max_score                      # 0..1
        color = colors[z["timeframe"]]
        # Banden over de volle breedte (xref='paper': 0 = links, 1 = rechts)
        fig.add_shape(type="rect", xref="paper", x0=0, x1=1, y0=z["low"], y1=z["high"],
                      fillcolor=color, opacity=0.08 + 0.37 * rel,
                      line=dict(color=color, width=0.5 + 2 * rel), layer="below")
        fig.add_annotation(xref="paper", x=1.0, xanchor="left", y=z["mid"], showarrow=False,
                           text=f"{z['timeframes']} · {z['score']:.1f}",
                           font=dict(size=10, color="#52514e"))

    # Hover-punten: een per zone, rechts naast de laatste candle
    for tf_name in colors:
        sub = visible[visible["timeframe"] == tf_name]
        hover = [
            f"<b>{r.role}</b> {r.low:.2f} – {r.high:.2f}<br>"
            f"timeframes: {r.timeframes}<br>aanrakingen: {r.touches}<br>"
            f"laatste aanraking: {r.last_touch:%Y-%m-%d %H:%M} UTC<br>"
            f"score: {r.score:.2f} · confluence: {r.confluence}"
            for r in sub.itertuples()
        ]
        # Ook zonder zones een (lege) trace, zodat de legenda altijd alle timeframes toont
        fig.add_trace(go.Scatter(
            x=[x[-1]] * len(sub), y=sub["mid"], mode="markers",
            marker=dict(symbol="square", size=10, color=colors[tf_name]),
            name=f"{TF_LABEL[tf_name]}-zone", hovertext=hover, hoverinfo="text",
        ))

    fig.add_hline(y=price, line=dict(color="#0b0b0b", width=1, dash="dot"),
                  annotation_text=f"prijs {price:.2f}", annotation_position="top left",
                  annotation_font=dict(size=10, color="#0b0b0b"))

    fig.update_layout(
        title=f"XAUUSD {tf} – S/R-zones, {METHOD_LABEL[method]} – laatste candle {c.index[-1]:%Y-%m-%d %H:%M} UTC",
        template="plotly_white",
        height=800,
        margin=dict(l=60, r=150, t=70, b=60),
        xaxis=dict(type="category", nticks=12, rangeslider=dict(visible=False), showgrid=False),
        yaxis=dict(range=[y_lo, y_hi], title="USD", gridcolor="#eeeeec"),
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1.0),
        hovermode="closest",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(path, include_plotlyjs=True)
    return path
