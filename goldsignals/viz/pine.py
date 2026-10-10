"""Export van de top-zones naar een Pine Script v6-indicator voor TradingView.

Gebruik: open in TradingView de Pine Editor, plak de inhoud van
output/tradingview_zones.pine, klik 'Add to chart'.

Waarom staan de zones als vaste getallen in het script? Pine Script kan geen
bestanden of internet lezen; de enige manier om onze zones in TradingView te
krijgen is ze in de code te zetten. Na elke nieuwe run moet je het script dus
opnieuw plakken.

Pine-limieten waar we rekening mee houden:
- max 500 boxes en 500 labels per script (max_boxes_count / max_labels_count);
- een label mag max ~500 candles rechts van de laatste candle staan (wij: 3);
- tijden in Pine zijn UNIX-milliseconden (int, 64-bit).
"""
from pathlib import Path

import pandas as pd

PINE_MAX_DRAWINGS = 500


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return f"color.rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _pine_str(s: str) -> str:
    return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'


def export_pine(zones: pd.DataFrame, price: float, as_of: pd.Timestamp, method: str,
                cfg: dict, path: Path) -> Path:
    """zones: de top-N samengevoegde zones (al gefilterd en gesorteerd op score)."""
    if zones.empty:
        raise ValueError("Geen zones om te exporteren naar Pine Script")
    if len(zones) > PINE_MAX_DRAWINGS:
        raise ValueError(f"Pine Script kan max {PINE_MAX_DRAWINGS} boxes tekenen; verlaag pine_top_n")

    colors = cfg["output"]["colors"]
    max_score = zones["score"].max()
    # Transparantie 0 = ondoorzichtig, 100 = onzichtbaar. Sterkste zone: 55, zwakste: 88.
    transp = [int(round(88 - 33 * s / max_score)) for s in zones["score"]]
    starts = [int(pd.Timestamp(t).timestamp() * 1000) for t in zones["first_touch"]]
    texts = [f"{r.timeframes} | {r.score:.1f}" for r in zones.itertuples()]

    def arr(values, fmt="{}"):
        return ", ".join(fmt.format(v) for v in values)

    table = "\n".join(
        f"//  {i + 1:>2}. {r.low:9.2f} - {r.high:9.2f}  {r.timeframes:<9} score {r.score:6.2f}  {r.role}"
        for i, r in enumerate(zones.itertuples())
    )

    script = f'''//@version=6
// ============================================================================
// Gold S/R zones - gegenereerd door gold-signals (python -m goldsignals.phase1)
// Berekend op: {as_of:%Y-%m-%d %H:%M} UTC, prijs toen: {price:.2f}
// Bron: Dukascopy {cfg["data"]["instrument"]} spot ({cfg["data"]["offer_side"]}), methode {method}
// LET OP: dit zijn zones van XAUUSD SPOT. Gebruik ze op een spot-chart
// (bijv. OANDA:XAUUSD), niet op futures (GC1!): die koers ligt op een ander niveau.
// Zones zijn een momentopname; draai phase1 opnieuw en plak het script opnieuw.
//
// Zones (sterkste eerst):
{table}
// ============================================================================
indicator("Gold S/R zones (gold-signals)", overlay = true, max_boxes_count = {PINE_MAX_DRAWINGS}, max_labels_count = {PINE_MAX_DRAWINGS})

showD      = input.bool(true, "Toon daily-zones")
show4h     = input.bool(true, "Toon 4h-zones")
show1h     = input.bool(true, "Toon 1h-zones")
showLabels = input.bool(true, "Toon labels met score")

// Zone-data: element i van elke array hoort bij dezelfde zone
var zLow    = array.from({arr(zones["low"], "{:.2f}")})
var zHigh   = array.from({arr(zones["high"], "{:.2f}")})
var zStart  = array.from({arr(starts)})
var zTf     = array.from({arr(zones["timeframe"], '"{}"')})
var zText   = array.from({", ".join(_pine_str(t) for t in texts)})
var zTransp = array.from({arr(transp)})

var int firstBarTime = time
var boxes  = array.new<box>()
var labels = array.new<label>()

tfColor(string tf) =>
    switch tf
        "1d" => {_hex_to_rgb(colors["1d"])}
        "4h" => {_hex_to_rgb(colors["4h"])}
        => {_hex_to_rgb(colors["1h"])}

tfVisible(string tf) =>
    tf == "1d" ? showD : tf == "4h" ? show4h : show1h

// Alleen op de laatste candle tekenen. Oude tekeningen eerst weggooien, zodat er bij
// elke realtime-tick niet steeds nieuwe boxes bijkomen.
if barstate.islast
    for b in boxes
        box.delete(b)
    for l in labels
        label.delete(l)
    array.clear(boxes)
    array.clear(labels)
    for i = 0 to array.size(zLow) - 1
        tf = array.get(zTf, i)
        if tfVisible(tf)
            c = tfColor(tf)
            zLeft = math.max(array.get(zStart, i), firstBarTime)
            array.push(boxes, box.new(zLeft, array.get(zHigh, i), time, array.get(zLow, i), xloc = xloc.bar_time, extend = extend.right, border_color = color.new(c, 30), bgcolor = color.new(c, array.get(zTransp, i))))
            if showLabels
                zMid = (array.get(zLow, i) + array.get(zHigh, i)) / 2
                array.push(labels, label.new(bar_index + 3, zMid, array.get(zText, i), style = label.style_label_left, color = color.new(c, 10), textcolor = color.white, size = size.small))
'''
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(script, encoding="utf-8")
    return path
