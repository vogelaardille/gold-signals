# gold-signals – projectcontext

Python-project voor paper trading op goud (XAUUSD). Doel: **bewijzen of een strategie
werkt**, zelf leren traden, en eventueel later echt handelen. Daarom: streng valideren.

## Eindproduct
Een systeem dat:
- automatisch support/resistance-zones (S/R) op goud herkent, over meerdere
  timeframes (daily, 4h, 1h), en die kan tekenen
- met een tweede indicator (RSI) en een trendfilter een instapmoment vindt, met
  stoploss, target en R:R
- een Telegram-melding stuurt met entry/SL/TP/R:R, een chart en een korte uitleg
  waarom het een signaal is
- alles eerst op fictief geld doet (paper trading, 10.000 euro, 1% risico per trade)
- nieuwe strategieën kan leren: strategieën zijn plugins, de gebruiker geeft ideeën en
  het systeem genereert ook varianten. Elke strategie gaat door dezelfde backtest met
  walk-forward validatie. Minimaal 100 trades nodig, anders telt hij niet mee.
- later elk uur draait via GitHub Actions

## Fasen
1. Data, zone-detectie, plots, Pine Script-export — **gebouwd, wacht op akkoord gebruiker**
2. Eerste strategie (S/R + RSI, multi-timeframe) + backtest-engine
3. Optuna, leaderboard, variantengenerator
4. Paper-trade-log (SQLite)
5. Telegram + GitHub Actions

Bouw per fase, stop daarna, vat samen en wacht op akkoord.

## Werkafspraken
- De gebruiker heeft basis Python-kennis: kan code lezen en kleine dingen aanpassen.
  Houd de code simpel en modulair.
- Variabelen/functies in het Engels; comments, uitleg en communicatie in het Nederlands.
  Leg bij belangrijke stukken kort uit **waarom**, niet alleen wat.
- Alle parameters in `config.yaml`, niet hardcoded.
- Data: Dukascopy XAUUSD. Als de download faalt: expliciet melden, **nooit stilzwijgend
  terugvallen op yfinance** (GC=F). yfinance alleen met toestemming van de gebruiker.

## Harde regels (validatie)
- **Geen lookahead.** Gebruik zones altijd via `goldsignals.sr.zones_as_of(candles_1h, t, cfg)`.
  Die gebruikt alleen candles die op t gesloten waren (ook 4h/daily) en pivots pas na
  hun bevestigingscandles. `tests/test_no_lookahead.py` bewaakt dit; nooit afzwakken.
- Tijden: alles UTC; index = openingstijd van de candle; kolom `close_time` = sluitmoment.
  Daily sluit om 17:00 New York (DST-bewust), 4h uitgelijnd op 17/21/01/05/09/13 NY.
- Alle timeframes worden geresampled uit dezelfde 1h-data.

## Technisch
- Python 3.12 in `.venv` (systeem-Python is 3.9, te oud voor dukascopy-python; 3.12 is
  geïnstalleerd via uv in `~/.local/share/uv/python`).
- Draaien: `.venv/bin/python -m goldsignals.phase1`
- Tests: `.venv/bin/python -m pytest -q` (offline, synthetische data)
- Cache: `data/cache/XAUUSD_1h_bid.parquet` (+ .json met de gedekte periode)

## Open punten
- XAUUSD spot (Dukascopy) en GC=F futures hebben verschillende koersniveaus. Zones uit de
  ene bron niet blind op de andere gebruiken. Beslissen in fase 5.
- Merged `touches` telt aanrakingen per timeframe op; dezelfde swing kan dus op 1d, 4h
  en 1h meetellen.
