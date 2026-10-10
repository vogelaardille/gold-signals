# Deel B – Strategieën en backtest

_Walk-forward binnen de research-periode: train 12 maanden, test 3 maanden, test-vensters 2022-10-01 t/m 2025-10-01. Alle cijfers zijn out-of-sample (OOS), na kosten (0,40 spread + 2 × 0,10 slippage per oz), 1% risico per trade._

## Conclusie in gewone taal

- **Geen enkele strategie is validated.** De S/R-strategieën (sr_bounce, breakout_retest)
  zijn **rejected**: ze halen geen positieve verwachting die niet van één jaar afhangt, en
  sr_bounce heeft te weinig trades. Dat sluit aan bij het onderzoek (deel A): de zones
  zelf voorspellen niets.
- **ema_pullback (zonder zones) is candidate**: 206 OOS-trades, +0,14 R gemiddeld na
  kosten, in elk jaar positief en nog positief bij 3× kosten. Maar:
  - willekeurige longs met **dezelfde stop en target** verdienen precies evenveel
    (+0,14 R). Het resultaat is dus de goudtrend, niet de instapregel;
  - op de **hold-out** (laatste 12 maanden, één keer geopend) was hij vlak: −0,002 R
    over 51 trades;
  - na correctie voor 671 geprobeerde varianten (deflated Sharpe) blijft er niets over.
  Volgens de regels mag hij op paper handelen (label CANDIDATE). Verwacht er geen voorsprong
  van; hij is vooral een manier om "long gaan in een stijgende markt" te volgen.
- **Buy-and-hold** (+132%) versloeg alle strategieën ruim in rendement over dezelfde periode.
- **Shorts tegen de goudtrend** verloren in elke strategie, ook bij willekeurige entries.



## Leaderboard

| strategie | status | trades | winrate | gem. R | totaal R | rendement | max DD | DSR | t.o.v. random (zelfde regels) | hold-out gem. R (n) |
|---|---|---|---|---|---|---|---|---|---|---|
| ema_pullback | **candidate** | 206 | 31% | +0.144 | +29.7 | +30.4% | -13.8% | 0.00 | +0.000 | -0.002 (51) |
| sr_bounce | **rejected** | 94 | 29% | +0.097 | +9.1 | +7.9% | -27.5% | 0.00 | +0.156 | niet geopend |
| breakout_retest | **rejected** | 134 | 29% | +0.027 | +3.6 | +1.9% | -14.1% | 0.00 | +0.061 | niet geopend |
| random_entry | **baseline** | 421 | 36% | -0.037 | -15.5 | -17.4% | -35.1% | 0.00 | +0.077 | niet geopend |
| buy_and_hold | **baseline** | – | – | – | – | +132.4% | -11.7% | – | – | niet geopend |

**Toelichting per strategie:**

- **ema_pullback** (candidate): voldoet aan candidate-eisen; hold-out niet positief (-0.002R); deflated Sharpe te laag (0.00 < 0.95)
- **sr_bounce** (rejected): te weinig trades (94 < 100); zonder beste jaar niet positief (-3.7R)
- **breakout_retest** (rejected): zonder beste jaar niet positief (-1.7R)
- **random_entry** (baseline): baseline, handelt nooit
- **buy_and_hold** (baseline): baseline: rendement zonder hefboom over dezelfde OOS-periode

## Kostengevoeligheid (gemiddelde R, zelfde gekozen parameters)

| strategie | 0× kosten | 1× | 2× | 3× |
|---|---|---|---|---|
| ema_pullback | +0.209 | +0.144 | +0.086 | +0.034 |
| sr_bounce | +0.196 | +0.097 | +0.018 | -0.048 |
| breakout_retest | +0.085 | +0.027 | -0.022 | -0.066 |
| random_entry | +0.070 | -0.037 | -0.122 | -0.191 |

## Long en short apart

| strategie | long n | long gem. R | short n | short gem. R | random zelfde regels long / short |
|---|---|---|---|---|---|
| sr_bounce | 53 | +0.599 | 41 | -0.551 | +0.036 / -0.182 |
| breakout_retest | 75 | +0.292 | 59 | -0.310 | +0.231 / -0.371 |
| ema_pullback | 206 | +0.144 | 0 | – | +0.144 / -0.268 |
| random_entry | 212 | +0.026 | 209 | -0.101 | -0.066 / -0.163 |

## Per jaar (totaal R)

| strategie | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|
| sr_bounce | +3.3 (5) | -8.8 (20) | +1.8 (52) | +12.9 (17) |
| breakout_retest | -1.1 (5) | +3.2 (54) | -3.7 (47) | +5.3 (28) |
| ema_pullback | +3.2 (19) | +7.0 (52) | +11.0 (61) | +8.5 (74) |
| random_entry | +8.3 (42) | -22.1 (134) | -0.8 (131) | -0.9 (114) |

**Buy-and-hold** over dezelfde periode: +132.4% (max drawdown -11.7%).

## Correctie voor het aantal varianten (deflated Sharpe)

In totaal zijn **671 varianten** geprobeerd (alle Optuna-trials van alle strategieën, zie `results/trials.csv`). Als je zoveel varianten probeert, ziet de beste er ook bij puur toeval goed uit. De deflated Sharpe ratio (DSR) schat eerst hoe goed de beste van al die varianten door toeval zou zijn, en geeft dan de kans (0–1) dat de echte strategie daar werkelijk boven zit. De lat voor *validated* is 0,95.

Voorbeeld: ema_pullback haalt per trade een Sharpe van 0.082 (gemiddelde R gedeeld door de spreiding). De beste van 671 toevalsvarianten zou volgens de DSR rond 0.55 uitkomen. Daar zit hij ver onder.

**Gevoeligheidscheck (niet de statusregel).** De trial-Sharpes zijn gemeten op train-vensters met ~50 trades en zijn daardoor erg ruisig, wat de lat hoog legt. Een mildere variant haalt die ruis eruit en rekent om naar het aantal OOS-trades:

- sr_bounce: DSR 0.00, mild 0.00
- breakout_retest: DSR 0.00, mild 0.00
- ema_pullback: DSR 0.00, mild 0.01
- random_entry: DSR 0.00, mild 0.00

Ook met de milde variant haalt geen enkele strategie 0,95. De conclusie hangt dus niet af van deze keuze.

## Hold-out

- **ema_pullback** geopend op 2026-10-10T14:51:46+00:00 met parameters `{"allow_short": false, "daily_filter": false, "rr": 3.0, "stop_atr": 2.0}`: 51 trades, winrate 25%, gem. -0.002 R, totaal -0.1 R, max DD -16.8%.

Elke strategie mag de hold-out maar één keer zien. Wordt de strategie daarna aangepast, dan is de hold-out voor die strategie **verbrand** en kan hij niet meer *validated* worden.
