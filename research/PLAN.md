# Onderzoeksplan: wat werkt er echt aan S/R-zones op goud?

Vastgelegd **voordat** er resultaten bekeken zijn (git-commit van dit bestand is het
bewijs). Wijzigingen na het zien van resultaten worden onderaan gelogd met reden.

## 1. Data-indeling (vast, ook in `config.yaml` onder `periods`)

| Periode | Van (UTC) | Tot (UTC, exclusief) | Gebruik |
|---|---|---|---|
| Warm-up | 2020-10-01 | 2021-10-01 | alleen historie voor zones/indicatoren; er wordt niets op gemeten |
| Research | 2021-10-01 | 2025-10-01 | onderzoek (deel A) en strategie-ontwerp/optimalisatie (deel B) |
| Hold-out | 2025-10-01 | 2026-10-01 | per strategie maximaal één keer openen, ter bevestiging |
| Forward | 2026-10-01 | — | paper trading |

- Bron: Dukascopy XAU/USD spot, 1h bid. 4h en daily worden uit 1h geresampled.
- De hold-out wordt in deel A **niet** gebruikt. Code die de hold-out leest loopt via
  `goldsignals.backtest.holdout`, die elke opening logt in `research/holdout_log.json`
  en een tweede opening van dezelfde strategie weigert.
- Walk-forward binnen research (deel B): train 12 maanden, test 3 maanden, stap 3
  maanden. Test-vensters lopen van 2022-10-01 tot 2025-10-01 (12 vensters).
  Deel A heeft geen gefitte parameters (alle definities hieronder liggen vast); daar
  toon ik stabiliteit per jaar en per walk-forward-testvenster.

## 2. Definities

**Zones.** Altijd via `zones_as_of(candles_1h, t, cfg, method)` met de fase-1-parameters
uit `config.yaml` (niet geoptimaliseerd). Primaire methode: **A** (pivot-clustering).
Methode B (KDE) alleen in vraag 3. Per uur wordt één snapshot opgeslagen
(`goldsignals/snapshots.py`): de zones zoals ze bekend waren op het sluitmoment van dat uur.

**ATR.** ATR(14) van de 1h-candles, op het moment van de snapshot.

**Zone-test (event).** 1h-candle *i* (open op tijd T) met de zones uit de snapshot op T
(= sluiting van candle *i-1*, dus zonder kennis van candle *i*):
- Support-test: zone ligt onder de vorige slotkoers (`close[i-1] > zone.high`) en
  `low[i] <= zone.high`.
- Resistance-test: zone ligt boven de vorige slotkoers (`close[i-1] < zone.low`) en
  `high[i] >= zone.low`.
- Zones waar de vorige slotkoers al in zat tellen niet (geen nieuwe aanraking).
- Raakt één candle meerdere zones, dan is dat één event per zone.

**Uitkomst over de volgende N = 24 candles** (support; resistance gespiegeld):
- *break*: eerste candle j in [i, i+24] met `close[j] <= zone.low - 0.5 x ATR`.
- *bounce*: eerste candle j in [i+1, i+24] met `high[j] >= zone.high + 1.0 x ATR`.
- Uitkomst = de eerste van de twee. Vallen ze in dezelfde candle, dan telt *break*
  (volgorde binnen een candle is onbekend; conservatief voor de S/R-hypothese).
  Geen van beide = *geen*.
- *Bounce-rate* = aantal bounces / alle events (inclusief *geen*).

**MFE/MAE** (in ATR) t.o.v. de entry = `open[i+1]`, over candles i+1 t/m i+24.
MFE = grootste beweging in de richting van de bounce, MAE = grootste beweging ertegen.

**Vaste 1:2-setup ("zone alleen").** Alleen als `close[i] > zone.low` (support niet
doorgebroken op de slotkoers; resistance gespiegeld).
- Entry = `open[i+1]`, stop = `zone.low - 0.25 x ATR`, target = entry + 2 x risico.
- Risico moet minstens 0.25 x ATR zijn, anders geen trade.
- Exit bij eerste raak van SL of TP in candles i+1 t/m i+48; raakt een candle beide,
  dan telt **SL eerst**. Na 48 candles exit op de slotkoers.
- Kosten: 0.40 USD spread + 2 x 0.10 USD slippage = 0.60 USD/oz per round trip.
  R_netto = (winst per oz - kosten) / (risico per oz + kosten). Een stop is dus precies -1R.

## 3. Nulmodel: willekeurige niveaus

Per replicatie en per kalendermaand wordt de **hele zone-set verschoven** met een vaste
offset: grootte uniform tussen 1 en 4 x daily ATR (de daily ATR aan het begin van de
maand), teken willekeurig. Breedte, aantal, onderlinge afstand en
eigenschappen (timeframe, confluence, aanrakingen) blijven gelijk, maar de niveaus
liggen niet meer op echte pivots. Daarna exact dezelfde event- en uitkomstberekening.
200 replicaties (50 voor de opsplitsingen in vraag 2 en 6). Seed vast (`config.yaml`).

## 4. Onzekerheid

- **Betrouwbaarheidsintervallen**: block-bootstrap per kalenderweek (2000 trekkingen),
  95%-percentielinterval. Per week omdat events dicht op elkaar niet onafhankelijk zijn.
- **Vergelijking met het nulmodel**: de echte waarde t.o.v. de verdeling van de 200
  nulreplicaties (percentiel, "hoe vaak doet een willekeurige zone-set het minstens zo
  goed"). Plus het verschil echt minus nul-gemiddelde, met bootstrap-interval.
- Effectgroottes met intervallen, geen jacht op p-waarden. Bij ~25 opsplitsingen sluit
  naar verwachting ~1 interval nul uit door toeval; alleen consistente patronen tellen.

## 5. Primaire meetwaarden

1. **Bounce-rate** (echt vs. nulmodel).
2. **Gemiddelde netto R van de vaste 1:2-setup** (echt vs. nulmodel).

Secundair: break-rate, MFE/MAE, aantal events.

## 6. Hypotheses en vragen

**V1 (belangrijkste).** H1: echte zones hebben een hogere bounce-rate en hogere
gemiddelde R dan verschoven (willekeurige) zones. H0: geen verschil.

**V2. Zone-eigenschappen.** Alleen deze opsplitsingen (methode A), elk met echt én
nulmodel in dezelfde opsplitsing:
| Eigenschap | Groepen |
|---|---|
| timeframe (belangrijkste) | 1d / 4h / 1h |
| confluence | laag (1-2) / midden (3-4) / hoog (5-6) |
| eerste vs. herhaalde test | eerste = geen event op een overlappende zone in de 120 candles ervoor |
| leeftijd (T - first_touch) | < 30 dagen / 30-180 dagen / > 180 dagen |
| support vs. resistance | support / resistance |
| t.o.v. daily-trend | mee / tegen. Trend = slot laatste gesloten daily > EMA50(daily) |
| sessie (uur van candle i, UTC) | Azië 21-07 / Londen 07-12 / New York 12-21 |
| volatiliteitsregime | percentiel van ATR(1h)/koers t.o.v. de 365 dagen ervoor: laag <33 / midden / hoog >67 |

**V3. Methode A vs. B.** Zelfde primaire meetwaarden en nulmodel voor B.

**V4. Breakout en retest.** Na een *break*-event (zone uit V1): komt de koers binnen
48 candles terug naar de zone (retest vanaf de andere kant)? Bij een retest:
1:2-setup in de breakout-richting (stop 0.25 ATR aan de andere kant van de zone,
alleen als de retest-candle aan de breakout-kant sluit). Ook: 1:2-setup direct na de
break (doorzetten zonder retest). Alles vs. nulmodel.

**V5. Stabiliteit.** Primaire meetwaarden per kalenderjaar, per walk-forward
testvenster, per volatiliteitsregime en per daily-trend; long (support) en short
(resistance) apart. Vergelijking met buy-and-hold per jaar en met willekeurige
entries (willekeurig uur, zelfde stopafstand-verdeling in ATR, 1:2, zelfde kosten),
long en short apart. Doel: zien hoeveel van een long-resultaat gewoon de stijgende
trend van goud is.

**V6. Bevestiging bovenop de zone.** Op de 1:2-setup, elk filter apart:
- RSI(14, 1h) op de slotkoers van de test-candle <= 40 (support) / >= 60 (resistance);
- afwijzingscandle: slot terug buiten de zone aan de naderingskant én de lont in de
  zone-richting >= 50% van de candle-range;
- EMA-trend: EMA50 > EMA200 (1h) voor long, < voor short.
Meetwaarde: gemiddelde R met filter minus zonder filter, en hetzelfde verschil in het
nulmodel (werkt het filter door de zone, of ook zonder zone?).

## 7. Wat telt als "werkt"

Een zone-effect telt als echt als de echte waarde boven het 95e percentiel van het
nulmodel ligt **én** het verschil in minstens 3 van de 4 volledige jaren (2022-2025;
2025 = jan-sep) dezelfde kant op wijst. Anders: "onzeker" of "werkt niet".
Strategie-hypotheses voor deel B worden alleen gebaseerd op effecten die hieraan voldoen,
of expliciet gemarkeerd als zwak/onzeker.

## 9. Deel B: strategieën (vastgelegd na deel A, vóór de eerste backtest)

- Strategieën en hun parameterruimtes staan in `config.yaml` onder `strategies`. Alleen
  deze ruimtes worden doorzocht (Optuna TPE, 20 trials per walk-forward-venster, seed 7,
  doelwaarde = gemiddelde R na kosten in het train-venster, min. 15 trades).
- sr_bounce volgt de opzet van de gebruiker, met twee opties uit deel A (zwak bewijs):
  `fresh_only` (vraag 2) en `reject_candle` (vraag 6).
- Statusregels: zie `goldsignals/backtest/validation.py` en de opdracht. "100 trades in de
  research-periode" = 100 out-of-sample trades in de walk-forward test-vensters samen
  (strenger dan alle trades in de periode).
- Deflated Sharpe (per trade) met N = alle gelogde trials van alle strategieën; drempel 0,95.
- Long-bias-toets: gemiddelde R minus gemiddelde R van willekeurige entries in dezelfde
  richting (random_entry, zelfde OOS-periode, kans 0,25 per candle, stop 1 ATR, 1:2) > 0.
- Kosten-gevoeligheid: dezelfde gekozen parameters bij 0x, 1x, 2x, 3x kosten.
- Hold-out alleen voor strategieën die candidate zijn; één keer, met de parameters die
  dezelfde procedure kiest op de laatste 12 maanden van de research-periode.

## 8. Wijzigingslog (na het zien van resultaten)

- 2026-10-10, **vóór** het bekijken van resultaten: volatiliteitsregime gebaseerd op
  ATR/koers in plaats van ATR in dollars. Reden: bij een koers die van 1.700 naar 5.000
  steeg is de dollar-ATR vooral 'hoog' omdat goud duurder is (44% van de uren in
  'hoog', 26% in 'laag'; met ATR/koers: 40% / 27%, de volatiliteit steeg ook relatief). Dit is een verbetering van de meting, niet van de uitkomst.
