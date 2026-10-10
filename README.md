# gold-signals

Onderzoek, backtest en **paper trading** (fictief geld) op goud (XAUUSD), met
Telegram-meldingen en een dashboard. Geen echt geld, geen broker, geen trading-API.

- Dashboard: <https://vogelaardille.github.io/gold-signals/>
- Onderzoek: [`research/report.md`](research/report.md) (ook op het dashboard, tab *Onderzoek*); ronde 2 en 3 in `research/round2/` en `research/round3/`
- Huidige stand en open punten: [`STATUS.md`](STATUS.md)

## Hoe het in elkaar zit

| Map | Wat |
|---|---|
| `goldsignals/data/` | Dukascopy 1h-data (cache), resamplen naar 4h/daily |
| `goldsignals/sr/` | zone-detectie (A: clustering, B: KDE) en `zones_as_of` (geen lookahead) |
| `goldsignals/features.py` | ATR, RSI, EMA, daily-trend, volatiliteitsregime (causaal) |
| `goldsignals/snapshots.py` | zones per uur, eenmalig berekend via `zones_as_of` |
| `goldsignals/research/` | deel A: zone-tests, nulmodel, bootstrap, rapport |
| `goldsignals/strategies/` | strategie-plugins (`generate_signals(view)`) |
| `goldsignals/backtest/` | engine, walk-forward + Optuna, validatie, hold-out-bewaker, leaderboard |
| `goldsignals/paper/` | uurlijkse paper-trading-run, state (CSV/JSON) |
| `goldsignals/notify/` | Telegram, teksten van de meldingen, signaal-chart |
| `goldsignals/dashboard/` | statische site (GitHub Pages) |
| `etf/` | ronde 3: onderzoek naar trend/momentum/volatiliteit op 9 ETF's (los van goud, alleen onderzoek) |
| `scripts/secret_scan.py` | scan op tokens/e-mail/lokale paden vóór publicatie |
| `.github/workflows/hourly.yml` | elk uur om minuut 5 |

Alle parameters staan in `config.yaml`.

## Installatie (lokaal)

Vereist Python ≥ 3.10 (dukascopy-python werkt niet op 3.9).

```bash
cd ~/gold-signals
python3.12 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Secrets alleen in `.env` (staat in `.gitignore`):

```
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

## Commando's

```bash
.venv/bin/python -m pytest -q                       # tests (offline, synthetische data)
.venv/bin/python -m goldsignals.phase1              # zones + charts + Pine-export (fase 1)
.venv/bin/python -m goldsignals.research.run        # deel A: onderzoek doorrekenen
.venv/bin/python -m goldsignals.research.report     # deel A: rapport md + html
.venv/bin/python -m goldsignals.backtest.run        # deel B: walk-forward + leaderboard
.venv/bin/python -m goldsignals.backtest.run --holdout   # hold-out openen (eenmalig per strategie!)
.venv/bin/python -m goldsignals.paper.run --no-send # één paper-run lokaal, zonder Telegram
.venv/bin/python -m goldsignals.dashboard.build     # dashboard in site/
.venv/bin/python scripts/secret_scan.py             # secret-scan
.venv/bin/pip install -r etf/requirements.txt       # ronde 3: yfinance
.venv/bin/python -m etf.data && .venv/bin/python -m etf.run && .venv/bin/python -m etf.report   # ronde 3
```

De eerste keer worden de zone-snapshots berekend (~25 min op 8 cores). Daarna staan ze in
`data/snapshots/`.

## Handmatig een run starten (GitHub)

- Op GitHub: tab **Actions** → **Elk uur** → **Run workflow** (vink *force* aan om ook
  in het weekend te draaien).
- Of in de terminal: `gh workflow run hourly.yml` (met force: `gh workflow run hourly.yml -f force=true`).

## Een strategie toevoegen

1. Maak `goldsignals/strategies/mijn_idee.py` met een klasse die erft van `Strategy`:

   ```python
   from goldsignals.strategies.base import Signal, Strategy

   class MijnIdee(Strategy):
       name = "mijn_idee"
       zone_method = "A"          # of None als je geen zones gebruikt

       def generate_signals(self, view):
           f, bar = view.feat, view.bar          # indicatoren en laatste candle
           zones = view.zones("A")               # zones zoals ze NU bekend zijn
           if f["rsi"] < self.params["rsi_max"]:
               stop = bar["close"] - 1.5 * f["atr"]
               target = bar["close"] + 3.0 * f["atr"]
               return [Signal(self.name, view.t, 1, stop, target, "uitleg in gewone taal", min_rr=2)]
           return []
   ```
   De `view` geeft alleen wat op dat moment bekend was. Kijk niet naar andere data.
2. Voeg hem toe in `config.yaml` onder `strategies:` met `class`, `params` en een
   **kleine** `space` (lijsten met opties). Hoe groter de ruimte, hoe strenger de
   correctie voor het aantal varianten.
3. Draai `.venv/bin/python -m goldsignals.backtest.run --only mijn_idee`. Het
   leaderboard laat de status zien.
4. Alleen bij status **candidate**: eventueel
   `... backtest.run --only mijn_idee --holdout` (één keer!). Daarna niet meer aan de
   strategie sleutelen, anders is de hold-out "verbrand".
5. Commit en push `research/results/` (o.a. `strategies.json`). Vanaf de volgende
   uurlijkse run handelt de strategie op paper, maar alleen als hij candidate of
   validated is.

## Regels die het systeem bewaakt

- **Geen lookahead**: zones via `zones_as_of`, indicatoren causaal, strategieën zien
  alleen een `MarketView`. Tests: `test_no_lookahead.py`, `test_features.py`,
  `test_strategy_lookahead.py`.
- **Entry op de volgende open**, stop gaat voor target als een candle beide raakt, kosten
  meegerekend, 1% risico per trade (`test_backtest.py`).
- **Hold-out maximaal één keer** per strategie (`research/holdout_log.json`).
- **Rejected handelt nooit**, ook niet op paper. Uitzondering met expliciet akkoord van de
  gebruiker: forward-tests (status `forward`, label "AANWIJZING, NIET BEWEZEN"), zie
  `research/round2/FORWARD.md`.
- **Idempotent**: dubbele runs geven geen dubbele trades of meldingen (`test_paper.py`).
- **Geen stille fallback** naar een andere databron. Mist Dukascopy de laatste candle,
  dan volgt een SYSTEEM-melding en wordt de run overgeslagen.

## Tijdconventies

- Alles intern in **UTC**; meldingen en dashboard in **Europe/Amsterdam**.
- De index van een candle is de openingstijd; `close_time` is het sluitmoment.
- Daily candle: 17:00–17:00 New York-tijd. 4h-candles starten om 17/21/01/05/09/13 NY.
- Data: Dukascopy **bid**, spot. Gebruik zones op een **spot**-chart (bijv.
  `OANDA:XAUUSD`), niet op futures (GC1!): die hebben een ander koersniveau.
