# STATUS

_Bijgewerkt: 2026-10-10 (ronde 2 afgerond)_

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

## Loopt
- Uurlijkse runs. In het weekend stoppen ze stil (markt dicht); eerste echte run met nieuwe
  candle: zondag 11-10 rond 23:05 UTC.

## Open
- Dukascopy-latency live meten: kon niet op 10-10 (zaterdag, markt dicht). De run logt de
  vertraging per uur in `state/runs.csv` (`latency_min`) en op het dashboard (Nu → Laatste run).
- Feestdagen: geven een SYSTEEM-melding "candle ontbreekt" (max 1 per 6 uur).

- GitHub waarschuwt dat actions op Node 20 verouderd zijn (ze draaien nu geforceerd op Node 24).
  Werkt; later de actions naar nieuwere hoofdversies zetten.
- Tests draaien niet in de workflow (alleen lokaal: `.venv/bin/python -m pytest -q`).

## Wacht op jouw beslissing (ronde 2)
- Wil je één bevestigingstoets van F2-4h (squeeze 20%, stop 2 ATR, target 2R) op hold-out H2,
  of F2-4h alleen forward op paper volgen, of geen van beide? Zie report ronde 2, "Voorstel".

## Wat jij nog moet doen
- Na zondagavond/maandag: kijk op het dashboard (Nu → "data-vertraging") en in
  `state/runs.csv` hoe snel Dukascopy de candle levert; zie je vaak "data-fout", meld het.
- Controleer af en toe of de meldingen kloppen met de chart (TradingView, spot-chart).
