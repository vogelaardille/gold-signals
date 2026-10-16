# STATUS

_Bijgewerkt: 2026-10-16 (ronde 4 gestart: plan + data)_

## Klaar
- **Fase 1**: data (Dukascopy, cache), zones A/B, `zones_as_of`, charts, Pine-export.
- **A – Onderzoek**: `research/PLAN.md` (vooraf), `research/report.md/.html`.
  Conclusie: zones voorspellen niets t.o.v. willekeurig verschoven niveaus.
- **B – Strategieën/backtest**: walk-forward + Optuna (671 trials), validatie, hold-out,
  leaderboard (`research/results/leaderboard.csv`), verslag `research/backtest.md`.
  - sr_bounce, breakout_retest: **rejected**
  - ema_pullback: **candidate** (hold-out geopend: −0,002 R over 51 trades; DSR 0,00;
    niet beter dan random longs met dezelfde SL/TP). Handelt op paper met label CANDIDATE.
  - **Let op:** `goldsignals/strategies/ema_pullback.py` niet meer wijzigen (ook geen
    comments): de hold-out-vingerafdruk is gebaseerd op de broncode; wijzigen = hold-out verbrand.
- **C – Paper trading**: `goldsignals/paper/` (state CSV/JSON, idempotent, getest).
- **E – Dashboard**: `goldsignals/dashboard/build.py` (5 pagina's, donker, mobiel getest op breedte).
- **D – Meldingen**: Telegram werkt (testberichten bevestigd op 10-10). Chat-id in `.env` en GitHub Secrets.
- **F – Automatisering**: openbaar repo https://github.com/vogelaardille/gold-signals, workflow
  elk uur (`5 * * * *`), state-branch `state`, GitHub Pages
  https://vogelaardille.github.io/gold-signals/, secret-scan vóór elke publicatie.
  Eerste runs op 10-10 geslaagd (handmatig met force; idempotentie live gecontroleerd).

- **Ronde 2 (onderzoek)**: `research/round2/PLAN2.md` (vooraf), `research/round2/report.md/.html`
  (ook op het dashboard: Onderzoek → Ronde 2). 1428 trials in totaal.
  - F1 daily trend, F2 vol-compressie, F3 mean reversion, F4 macrofilter: **alle rejected**.
  - F5 zone-toets 15m (2007–2018): echte zones niet beter dan willekeurig → geen 15m-zonestrategie.
  - Verkennend (achteraf): F2 op 4h boven random met dezelfde exits (~+0,2 R), maar niet
    significant na correctie. **Hold-out H2 (2019-01 – 2020-09) is NIET geopend (0×).**
  - Niets uit ronde 2 is naar paper trading gegaan.

- **Ronde 3 (onderzoek, ETF's, geen goud)**: `research/round3/PLAN3.md` (vooraf gecommit),
  `research/round3/report.md/.html` (dashboard: Onderzoek → Ronde 3). Code in `etf/`, 25 trials.
  - F1 trendfilter (N=10): **rejected**. De daling zakte van −30,7% naar −8,4%, maar het voordeel
    komt vrijwel alleen uit 2008 (niet stabiel over subperiodes).
  - F2 dual momentum: **rejected** (slechter dan gelijk gewicht).
  - F3 vol-target op gelijk gewicht: **rejected** (te onzeker).
  - F3 vol-target op 60/40 (10%, 20 dagen): **candidate, niet validated**. Research Sharpe +0,12,
    MDD −19% tegen −29%; H3 klein positief (+0,03); P (1996–2004) negatief (−0,10); Reality Check
    p = 0,57. In EUR verdwijnt het voordeel grotendeels.
  - **H3 en P elk 1× geopend, alleen voor F3-60/40** (`research/round3/holdout_log.json`). Niet
    meer aan die regel sleutelen.
  - Niets uit ronde 3 gaat naar paper trading of Telegram.

## Ronde 4 (onderzoek, valuta-daytrades, geen goud) – bezig
- Literatuuronderzoek (2026-10-16) → drie families: F1 fix-reversal (Krohn e.a. 2024),
  F2 ronde getallen (Osler 2003), F3 London breakout (controle). 32 trials.
- `research/round4/PLAN4.md` **vooraf gecommit** (30efff6). Paren EUR/USD, GBP/USD, USD/JPY;
  Dukascopy 1h bid+ask (15m pas vanaf 2012, dus alleen 1h). Research 2005–2019,
  **hold-out H4 2020-01 – 2026-10** (later 1× geopend voor F1-EU, zie onder).
- Klaar: `fx/data.py` + `fx/config.yaml`, download (cache `data/cache/fx/`), kwaliteit
  `research/round4/data_quality.md`. Tijdstempels OK; USD/JPY 2010 valt weg (bron mist jan–sep);
  weekendcandles en ask<bid-uren worden bij het laden weggefilterd (PLAN4 §11).
- Engine (`fx/engine.py`, fills op bid/ask), families (`fx/families.py`), statistiek
  (`fx/stats.py`), research-run (`python -m fx.run`, ~45 s) → `research/round4/research_results.md`.
- **Research-uitkomsten (R4 2005–2019, 32 trials):**
  - **F1-EU** (long USD 08–14 Frankfurt + short USD 16:00 Londen → 16:00 NY, EUR/USD):
    **candidate**. +1,32 bp/trade netto (bruto 2,13), Sharpe 1,00, 7.804 trades, alle 3
    subperiodes > 0, ook bij 3× slippage (+1,00) en retail (+0,53); Reality Check p < 0,001.
  - F1-TK (Tokio op USD/JPY): rejected, bruto wel (+1,45) maar netto weg bij 3× slippage (oordeel b).
  - F2 ronde getallen (bounce/breakout) en F3 London breakout: **rejected**, netto negatief, niet
    beter dan het nulmodel. Bounce op echte ronde getallen is zelfs slechter dan op verschoven niveaus.
- **H4 1× geopend voor F1-EU** (akkoord gebruiker, 2026-10-16; `research/round4/holdout_log.json`).
  Formeel **validated** (regels PLAN4 §9: ≥300 trades, netto > 0, > 0 bij 2× slippage, RC p < 0,05),
  maar zwak: netto +0,26 bp/trade (research +1,32), bruto 0,71 (research 2,13), Sharpe 0,24,
  bootstrap > 0 maar 71%, 2025 en 2026 negatief, L_post-been netto negatief, retail −0,64 bp.
  Effect is na publicatie grotendeels verdwenen. Niet naar paper trading zonder apart FORWARD-plan
  en akkoord. **Niets meer aan F1-regels veranderen.**

## Loopt
- Uurlijkse runs. In het weekend stoppen ze stil (markt dicht); eerste echte run met nieuwe
  candle: zondag 11-10 rond 23:05 UTC.

## Open
- Dukascopy-latency live meten: kon niet op 10-10 (zaterdag, markt dicht). De run logt de
  vertraging per uur in `state/runs.csv` (`latency_min`) en op het dashboard (Nu → Laatste run).
- Feestdagen: geven een SYSTEEM-melding "candle ontbreekt" (max 1 per 6 uur).

- GitHub waarschuwt dat actions op Node 20 verouderd zijn (ze draaien nu geforceerd op Node 24).
  Werkt; later de actions naar nieuwere hoofdversies zetten.
- Tests draaien niet in de workflow (alleen lokaal: `.venv/bin/python -m pytest -q`, 106 tests).
- `tests/test_paper.py::test_rejected_strategy_never_trades` faalde sinds de activering van de
  forward-test (las het echte forward-register); op 10-10 gerepareerd door de test af te schermen.

- **Forward-test vol_squeeze_4h** (besluit gebruiker 2026-10-10: optie 2, H2 blijft dicht):
  regels in `research/round2/FORWARD.md` (gecommit vóór activering), vingerafdruk code
  `93b69b0a83febada`. Label **AANWIJZING, NIET BEWEZEN**. Geen Telegram-signalen (alleen
  dashboard-log), wel trade-updates en weekoverzicht. Stopregel vanaf trade 40 (< −0,25 R),
  evaluatie na 100 trades (`python -m goldsignals.round2.forward`), ~3,6 jaar.
  Start: eerste nieuwe candle na activering (zondag 11-10 avond), zie `state/meta.json` → `forward_start`.
  - **Niet wijzigen**: `goldsignals/strategies/vol_squeeze_4h.py` en de functies in de
    vingerafdruk (`goldsignals/round2/forward.py`); anders stopt de strategie automatisch.

## Wat jij nog moet doen
- Na zondagavond/maandag: kijk op het dashboard (Nu → "data-vertraging") en in
  `state/runs.csv` hoe snel Dukascopy de candle levert; zie je vaak "data-fout", meld het.
- Controleer af en toe of de meldingen kloppen met de chart (TradingView, spot-chart).
