# Forward-test: vol_squeeze_4h

**Label in alle meldingen en op het dashboard: AANWIJZING, NIET BEWEZEN.**

Vastgelegd op 2026-10-10, vóór de eerste trade en vóór de strategie aan de live workflow
wordt toegevoegd (de git-commit van dit bestand is het bewijs). Besluit van de gebruiker:
optie 2 uit `report.md`: alleen forward op paper volgen. Hold-out H2 blijft dicht.

## 1. Waarom deze strategie, en wat we er nu van weten
In ronde 2 lag deze variant **achteraf** boven random entries met dezelfde exits:
+0,22 R per trade na kosten [+0,04; +0,40] over 251 trades (2010–2018). De vooraf
vastgelegde walk-forward koos hem maar zelden, en na correctie voor 1.428 varianten is
hij niet significant. Het is een aanwijzing, geen bevinding. Niet met echt geld handelen.

## 2. Exacte regels (worden NOOIT meer aangepast)

| onderdeel | waarde |
|---|---|
| Data | Dukascopy XAU/USD spot, **bid**, 1h-candles (live-cache) |
| Timeframe | **4h**, geresampled uit 1h; candles sluiten om 17, 21, 01, 05, 09, 13 uur New York-tijd |
| Compressie | Bollinger-bandbreedte (20 candles, 2σ, standaardafwijking met ddof 0) / SMA(20); percentiel t.o.v. de afgelopen **365 dagen** (incl. de huidige candle) **≤ 20** |
| Compressie recent | in minstens één van de **5** candles vóór de breakout-candle |
| Long | slot **>** hoogste high van de **20** vorige 4h-candles |
| Short | slot **<** laagste low van de **20** vorige 4h-candles |
| Entry | open van de eerstvolgende 1h-candle na het slot (= open van de volgende 4h-candle) |
| Stop | entry ∓ **2 × ATR(14)** van de 4h-candles (Wilder), berekend op de signaal-candle |
| Target | entry ± **2 × risico (2R)** |
| Uitvoering | stop en target per 1h-candle gecontroleerd; raakt een candle beide, dan telt de **stop**; gat voorbij de stop = exit op de open |
| Posities | max. **1** open trade; long en short |
| Kosten | spread 0,40 + 2 × slippage 0,10 = **0,60 USD/oz** per round trip |
| Account | eigen paper-account, € 10.000, **1% risico** per trade (incl. kosten) |
| Strategie-id | `vol_squeeze_4h` (`goldsignals/strategies/vol_squeeze_4h.py`) |

**Vingerafdruk van de code: `93b69b0a83febada`** (`goldsignals.round2.forward.fingerprint()`:
sha256 over de strategie en alle functies die signaal en uitvoering bepalen).
`tests/test_forward.py` faalt als daar iets aan verandert.

**Gecontroleerd vóór vastleggen** (research-data 2010–2018, H2 niet geladen,
`results/forward_check.json`): de live-plugin geeft **exact dezelfde 579 signalen** als
de onderzoekscode, en levert met de live-motor (exits per 1h-candle) **exact dezelfde 251
trades en +0,215 R** op als het onderzoek (exits per 4h-candle).

## 3. Start
De forward-periode begint bij de eerste 1h-candle die de live workflow verwerkt nadat de
strategie is toegevoegd. Dat tijdstip wordt vastgelegd in `state/meta.json`
(`forward_start`). Niets van daarvóór telt mee, en er wordt niets uit het verleden nagespeeld.

## 4. Meldingen
- **Telegram: GEEN signaalmeldingen** voor deze strategie. Signalen worden alleen gelogd
  op het dashboard (pagina Paper trading). Bedoeling: niet erop handelen of reageren.
- **Trade-updates (stop/target geraakt) en het weekoverzicht blijven aan**, met het label
  AANWIJZING, NIET BEWEZEN.
- Gaat de stopregel af of wordt het evaluatiemoment bereikt, dan staat dat in de
  trade-update van de trade die het veroorzaakt.

## 5. Evaluatie: na 100 gesloten trades
Na de 100e gesloten trade worden **geen nieuwe trades** meer geopend tot de gebruiker
beslist. Dan draait `python -m goldsignals.round2.forward`:
- **gemiddelde R per trade na kosten** over de 100 trades, met een **95%-bootstrap-interval**
  (blokken per kalendermaand, 5000 trekkingen);
- **vergelijking met random entries met exact dezelfde exits**: 200 replicaties,
  willekeurige 4h-sluitingen in dezelfde forward-periode, per kalenderjaar evenveel entries
  en dezelfde long/short-verhouding; zelfde stop, target, uitvoering en kosten. Uitkomst =
  percentiel van de strategie in die verdeling;
- **oordeel** (vooraf vastgelegd):
  - *negatief* als de bovengrens van het interval < 0;
  - *aanwijzing bevestigd* als de ondergrens > 0 **én** de strategie boven het 95e
    percentiel van random ligt. Ook dan is hij **niet "validated"**: de correctie voor
    alle geprobeerde varianten blijft gelden, en echt geld valt buiten dit project;
  - anders *niet bevestigd*.
- Win rate wordt alleen getoond naast de break-even win rate, nooit gebruikt voor een oordeel.

**Wat 100 trades kunnen aantonen** (`results/power.json`): het interval is ongeveer
±0,28 R breed. Het kleinste effect dat je met 80% kans vindt is ~+0,35 R per trade. Is het
ware effect +0,22 R (zoals in het onderzoek), dan is de kans op "bevestigd" maar ~43%. Een
uitkomst "niet bevestigd" betekent dus niet automatisch dat er niets is. Verwachte duur:
~3,6 jaar (~28 trades per jaar).

## 6. Stopregel
Vanaf de **40e** gesloten trade wordt na **elke** gesloten trade het gemiddelde van alle
forward-trades tot dan toe berekend (R na kosten). Ligt dat **onder −0,25 R**, dan stopt de
strategie: geen nieuwe trades meer (een open trade loopt nog af). Gecontroleerd tot en met
trade 100.

Kans dat de stopregel afgaat (simulatie met de R-verdeling uit het onderzoek):
bij een waar gemiddelde van +0,22 R: ~3%; +0,10 R: ~10%; 0 R: ~23%; −0,15 R: ~56%;
−0,30 R: ~85%.

## 7. Wat dit niet is
- Geen strategie met status candidate of validated, en geen advies.
- Geen echt geld, geen broker.
- Geen aanleiding om parameters bij te stellen als het tegenvalt. Dat zou een nieuwe
  hypothese zijn, met een nieuw plan.

## 8. Wijzigingslog
_(nog geen wijzigingen)_
