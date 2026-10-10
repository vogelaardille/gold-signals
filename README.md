# gold-signals

Support/resistance-zones, signalen en (later) paper trading op goud (XAUUSD).
Zie `CLAUDE.md` voor het volledige doel en de fasen. **Status: fase 1** (data, zones,
charts, Pine Script-export).

## Installatie

Vereist Python ≥ 3.10 (dukascopy-python werkt niet op 3.9).

```bash
cd ~/gold-signals
python3.12 -m venv .venv          # of het pad naar een andere Python >= 3.10
.venv/bin/pip install -r requirements.txt
```

## Gebruik

```bash
.venv/bin/python -m goldsignals.phase1     # alles draaien + samenvatting
.venv/bin/python -m pytest -q              # tests (offline)
```

De eerste run downloadt ~5 jaar 1h-data van Dukascopy (± 15 s) en cachet die in
`data/cache/`. Volgende runs halen alleen de nieuwste uren op.

Output in `output/`:

| Bestand | Inhoud |
|---|---|
| `zones_A.csv`, `zones_B.csv` | samengevoegde zones per methode, gesorteerd op score |
| `zones_*_per_timeframe.csv` | dezelfde zones vóór het samenvoegen |
| `chart_zones_A.html`, `chart_zones_B.html` | interactieve 4h-chart (laatste 3 maanden) |
| `tradingview_zones.pine` | top-20 zones als Pine Script v6-indicator |

**TradingView:** open de Pine Editor, plak `tradingview_zones.pine`, klik *Add to chart*.
Gebruik een **spot**-chart (bijv. `OANDA:XAUUSD`), geen futures.

Alle instellingen staan in `config.yaml`.

## Hoe het werkt

1. **Data** (`goldsignals/data/`): een `DataProvider`-interface, met Dukascopy als
   implementatie. Alleen 1h-candles worden gedownload; 4h en daily worden daaruit
   geresampled, zodat alle timeframes consistent zijn. Bij een mislukte download stopt
   het programma met een duidelijke fout — er is **geen** automatische fallback naar
   yfinance.
2. **Pivots**: swing highs/lows met een fractal-venster van n candles. Een pivot is pas
   bekend n candles later (`confirmed_time`).
3. **Zones per timeframe**, twee methodes met hetzelfde outputformaat:
   - **A – pivot-clustering:** pivots binnen k × ATR van elkaar vormen een zone.
   - **B – KDE:** dichtheid van pivotprijzen; elke piek wordt een zone.
4. **Sterkte** = som van de aanrakingen, elk gewogen naar recency
   (halfwaardetijd per timeframe).
5. **Samenvoegen over timeframes**: de zone van de hoogste timeframe is het anker, en
   overlappende lagere zones versterken hem. `confluence` = som van de
   timeframe-gewichten (daily 3, 4h 2, 1h 1); `score` = Σ gewicht × sterkte.
   `role` = support/resistance t.o.v. de laatste prijs.

## Tijdconventies

- Alles in **UTC**. De index van een candle is zijn openingstijd; `close_time` is het
  sluitmoment.
- **Daily candle: 17:00 – 17:00 New York-tijd** (goud-conventie, sluiting = einde
  handelsdag). In UTC is dat 21:00 (zomertijd) of 22:00 (wintertijd). De handel van
  zondagavond hoort bij de maandag-candle.
- **4h-candles** starten om 17, 21, 01, 05, 09 en 13 uur New York-tijd, zodat er
  precies zes in een daily candle passen. (TradingView kan per broker anders uitlijnen;
  daardoor kunnen 4h-candles daar iets afwijken.)
- Data = Dukascopy **bid**-prijzen (instelbaar via `offer_side`).

## Geen lookahead

`zones_as_of(candles_1h, t, cfg)` berekent de zones zoals ze op moment `t` bekend
waren: alleen gesloten candles (een lopende 4h/daily telt niet mee), alleen bevestigde
pivots, ATR en recency op `t`. `tests/test_no_lookahead.py` bewijst dat het resultaat
niet verandert als je alle data na `t` aanpast, en dat het wél verandert als je data
vóór `t` aanpast.

## Open punt (beslissen in fase 5)

XAUUSD **spot** (Dukascopy, de meeste CFD-brokers) en **GC=F futures** (yfinance,
COMEX) hebben verschillende koersniveaus: futures bevatten een rente-/opslagcomponent
(contango) die per contract en looptijd varieert. Zones uit de ene bron mogen dus niet
zomaar op de andere worden gebruikt.
