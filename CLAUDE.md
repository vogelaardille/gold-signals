# gold-signals – projectcontext

Python-project voor onderzoek en **paper trading** op goud (XAUUSD). Doel: **bewijzen of
een strategie werkt**, zelf leren traden. Nooit echt geld, geen broker-koppeling, geen
trading-API-sleutels. Streng valideren; "het werkt niet" is een geldige uitkomst.
Actuele stand: `STATUS.md`. Gebruikersuitleg en commando's: `README.md`.

## Onderdelen (opdracht A–F)
- **A Onderzoek** (`goldsignals/research/`, `research/`): zone-tests vs. nulmodel
  (verschoven zones), opzet vastgelegd in `research/PLAN.md` vóór resultaten.
  Rapport: `research/report.md/.html`; interpretatieteksten in `research/text/*.md`
  (met de hand, `{velden}` worden uit `results/results.json` gevuld).
- **B Strategieën + backtest** (`goldsignals/strategies/`, `goldsignals/backtest/`):
  plugins met `generate_signals(view)`, walk-forward + Optuna, statusregels in
  `validation.py`, hold-out-bewaker `holdout.py`, output in `research/results/`
  (`leaderboard.csv`, `strategies.json`, `trials.csv`, `oos_*.csv`).
- **C Paper trading** (`goldsignals/paper/`): `runner.run()` = één uurlijkse run. State als
  CSV/JSON in `state/` = aparte git-branch `state`.
- **D Meldingen** (`goldsignals/notify/`): Telegram, vier soorten, dedupe via sleutels.
- **E Dashboard** (`goldsignals/dashboard/build.py`): statische site in `site/`.
- **F Automatisering**: `.github/workflows/hourly.yml` (cron `5 * * * *`), secret-scan
  `scripts/secret_scan.py`, GitHub Pages.

## Werkafspraken
- Gebruiker: bachelorstudent, basis Python. Code simpel en modulair.
- Identifiers Engels; comments, uitleg en communicatie Nederlands. Leg **waarom** uit.
- Alle parameters in `config.yaml`, niet hardcoded.
- Commit na elk onderdeel; houd `STATUS.md` en dit bestand actueel.
- Data: Dukascopy XAUUSD. Bij falen: expliciet melden, **nooit stilzwijgend terugvallen
  op yfinance** (GC=F). yfinance alleen met toestemming van de gebruiker.

## Harde regels (validatie)
- **Geen lookahead.** Zones altijd via `goldsignals.sr.zones_as_of(candles_1h, t, cfg)`
  (snapshots in `data/snapshots/` zijn daarmee berekend). Indicatoren via
  `features.compute_features` (causaal). Strategieën krijgen alleen een `MarketView`.
  Tests `test_no_lookahead.py`, `test_features.py`, `test_strategy_lookahead.py`; nooit
  afzwakken.
- **Periodes vast** (`config.yaml` → `periods`): warm-up 2020-10-01, research
  2021-10-01 – 2025-10-01, hold-out 2025-10-01 – 2026-10-01, daarna forward/paper.
  Research-code laadt data met `until = einde research`.
- **Hold-out**: per strategie max. één keer, alleen via `backtest/holdout.py`
  (`research/holdout_log.json`). Strategie aanpassen na openen = hold-out verbrand.
- **Status**: rejected handelt nooit; validated nooit zonder hold-out.
- **Backtest/paper-regels**: signaal op 1h-close, entry op de volgende open, SL gaat voor
  TP binnen één candle, gat voorbij stop = exit op de open, kosten = spread + 2× slippage,
  1% risico incl. kosten, max 1 open trade per strategie. Engine en paper-runner delen
  `try_fill`/`check_exit`.
- Niet achteraf definities/parameters/meetmethode aanpassen voor een mooier resultaat;
  wijzigingen loggen in `research/PLAN.md` §8.
- Tijden: alles UTC; index = openingstijd; `close_time` = sluitmoment. Daily sluit 17:00
  New York (DST-bewust), 4h uitgelijnd op 17/21/01/05/09/13 NY. Meldingen in
  Europe/Amsterdam.

## Secrets
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` alleen in `.env` (gitignored) en GitHub
  Secrets. Nooit printen, loggen, committen of in `site/`. `telegram.redact()` filtert
  foutmeldingen. Draai `scripts/secret_scan.py` vóór elke push/publicatie.
- Git-auteur is het GitHub-noreply-adres (repo is openbaar).

## Technisch
- Python 3.12 in `.venv` (systeem-Python 3.9 is te oud; 3.12 via uv in
  `~/.local/share/uv/python`).
- Tests: `.venv/bin/python -m pytest -q` (offline, synthetische data, ~3 min).
- Cache: `data/cache/XAUUSD_1h_bid.parquet` (+ .json). Snapshots: `data/snapshots/`
  (~25 min om opnieuw te bouwen; niet in git).
- In GitHub Actions: data-cache via `actions/cache`; state-branch uitgecheckt in `state/`.

## Open punten
- XAUUSD spot (Dukascopy) vs. GC=F futures: verschillende koersniveaus; nooit mengen.
- Merged `touches` telt aanrakingen per timeframe op (zelfde swing kan op 1d/4h/1h tellen).
- Feestdagen kent `market_hours.py` niet: dan komt er een SYSTEEM-melding (max 1 per 6 uur).
