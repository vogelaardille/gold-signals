# STATUS

_Bijgewerkt: 2026-10-10_

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
- **F (code)**: workflow `.github/workflows/hourly.yml`, `scripts/secret_scan.py`.

## Loopt
- D en F: wacht op de gebruiker (Telegram chat-id; daarna testbericht; daarna repo aanmaken + push).

## Open
- Dukascopy-latency live meten: kon niet op 10-10 (zaterdag, markt dicht). De run logt de
  vertraging per uur in `state/runs.csv` (`latency_min`) en op het dashboard (Nu → Laatste run).
- Feestdagen: geven een SYSTEEM-melding "candle ontbreekt" (max 1 per 6 uur).

## Wat jij nog moet doen
1. Stuur je bot **@dille_gold_signals_bot** in Telegram een bericht (bijv. "hoi").
2. Daarna kan het chat-id worden opgehaald en een testbericht verstuurd.
