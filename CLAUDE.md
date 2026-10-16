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

## Ronde 2 (`goldsignals/round2/`, `research/round2/`)
- Opzet: `research/round2/PLAN2.md` (vooraf gecommit). Lange historie: 1h vanaf 2004,
  15m vanaf 2005, cache `data/cache/round2/` (live-cache van ronde 1 onaangeroerd).
- Blokken: research R2 2006–2018, **hold-out H2 2019-01-01 – 2020-10-01 (0× geopend)**,
  K 2020-10 – 2025-10 (gezien in ronde 1, niet gebruiken), H1 2025-10 – 2026-10 (verbrand).
- Eigen engine (`round2/engine.py`, met trailing/tijdstop) en families F1–F4
  (`round2/families.py`); zone-toets 15m in `round2/zone15.py`.
- Trials tellen door: ronde 1 (671) + 1 (H1) + ronde 2 (`research/round2/results/trials.csv`).
- Niets uit ronde 2 naar paper trading of `strategies.json` zonder akkoord van de gebruiker.
- **Forward-test vol_squeeze_4h** (akkoord 2026-10-10): `research/round2/FORWARD.md`,
  register `research/round2/forward_strategies.json` (status `forward`, label
  "AANWIJZING, NIET BEWEZEN", `notify_signals: false`). Runner laadt hem alleen met akkoord
  én kloppende vingerafdruk (`round2/forward.py: fingerprint()`). NOOIT de regels of de
  code in de vingerafdruk aanpassen (`tests/test_forward.py` bewaakt dat).

## Ronde 3 (`etf/`, `research/round3/`): ETF-universum, geen goud
- Alleen onderzoek: niets naar live workflow, Telegram of paper trading. Parameters in `etf/config.yaml`.
- Opzet `research/round3/PLAN3.md` (vooraf gecommit, wijzigingen in §11). Data: yfinance Adj Close
  (cache `data/cache/etf/`, extra pakket in `etf/requirements.txt`, niet in de workflow), FRED TB3MS.
- Blokken: research 2005-01 – 2020-12; **H3 2021-01 – 2026-09** en **P 1996–2004** (fondsen) zijn
  elk 1× geopend, alleen voor `F3_sixty_forty_v10_w20` (`research/round3/holdout_log.json`).
  Research-code laadt data altijd met `until = research_end`; openen alleen via `etf/open_holdout.py`.
- Commando's: `python -m etf.data` (download+kwaliteit), `python -m etf.run` (research),
  `python -m etf.report` (rapport + figuren). Tests: `tests/test_etf.py`.

## Ronde 4 (`fx/`, `research/round4/`): valuta-daytrades, geen goud
- Alleen onderzoek: niets naar live workflow, Telegram of paper trading zonder akkoord.
  Parameters in `fx/config.yaml`. Opzet `research/round4/PLAN4.md` (vooraf gecommit, wijzigingen in §11).
- Data: Dukascopy 1h **bid én ask** (EUR/USD, GBP/USD, USD/JPY), cache `data/cache/fx/`. Kleiner dan
  1h pas vanaf 2012 → alleen 1h. Tijden altijd tz-aware UTC aan `dukascopy_python` geven (naive = lokale tijd).
- Blokken: warm-up 2003-06 – 2004, research 2005 – 2019, **H4 2020-01 – 2026-10 (1× geopend, alleen F1-EU)**.
  Research-code laadt via `fx.data.research_data()`; H4 alleen via `fx/open_holdout.py`.
- Fills op bid/ask (echte spread) + slippage; nooit een positie over 17:00 NY.
- Commando's: `python -m fx.data` (download + `research/round4/data_quality.md`), `python -m fx.run`
  (research → `research/round4/research_results.md`, `results/`), `python -m fx.open_holdout <primair>`
  (H4, eenmalig, alleen candidates; log `research/round4/holdout_log.json`). Tests: `tests/test_fx.py`.
- Status: **F1-EU validated** (formeel; in H4 zwak, +0,26 bp, 2025–2026 negatief); de rest rejected.
  H4 is open voor F1-EU: niets meer aan F1-regels/vensters veranderen.

## Ronde 5 (`fx/momentum.py`, `fx/run5.py`, `research/round5/`): intraday momentum in valuta
- Opzet `research/round5/PLAN5.md` (vooraf gecommit). Parameters `fx/config.yaml` → `round5`. Engine van ronde 4
  ongewijzigd hergebruikt. Research 2005–2019 op EUR/USD, GBP/USD, USD/JPY; **C5** = AUD/USD, USD/CAD, USD/CHF
  2005–2019 (bevestiging, max. 1× per candidate via `fx/open_c5.py`, log `research/round5/holdout_log.json`);
  K5 2020–2026 alleen beschrijvend (`fx/k5.py`).
- Status: G1 en G2 **rejected**; C5 0× geopend.

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
  De vingerafdruk is de broncode van de klasse + params: **`strategies/ema_pullback.py`
  niet wijzigen** (hold-out op 2026-10-10 geopend).
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
