# Ronde 2 – onderzoeksplan

Vastgelegd **voordat** er één backtest van ronde 2 is gedraaid (de git-commit van dit
bestand is het bewijs). Alleen de data-beschikbaarheid en -kwaliteit
(`data_quality.md`) zijn vooraf bekeken. Wijzigingen achteraf staan in §10.

**Doel.** Bestaat er een regelgebaseerde strategie op goud met positieve verwachting in R
**na kosten**, stabiel over jaren en regimes? "Er bestaat geen" is een geldige uitkomst.
Win rate is geen doel en wordt nooit gebruikt om te kiezen of af te stellen; hij wordt
alleen getoond naast de break-even win rate 1/(1+R:R).

`goldsignals/strategies/ema_pullback.py` wordt niet aangeraakt. Niets uit ronde 2 gaat
naar paper trading of naar `research/results/strategies.json` zonder akkoord van de gebruiker.

## 1. Data

- Dukascopy XAU/USD **bid**, 1h vanaf 2004-01-01 (eerder levert Dukascopy niets) en 15m
  vanaf 2005-01-01. Aparte cache `data/cache/round2/`. Kwaliteit: `data_quality.md`.
- Gaten binnen handelstijd: 0–1,7% per jaar, vrijwel volledig feestdagen en vroege
  sluitingen. Geen datagaten van betekenis.
- **Sessie:** vóór 2013 bevat de feed ook candles in de dagelijkse pauze (17:00 NY) en
  op vrijdagavond/zondagmiddag. Die worden in ronde 2 **weggelaten** (filter
  `market_hours.is_trading_hour`), zodat 4h/daily-candles over alle jaren dezelfde
  sessie (17:00–17:00 NY) hebben en er geen mini-candles op zaterdag ontstaan.
- Daily/4h worden geresampled uit 1h; 15m wordt apart gedownload (niet geresampled).
- Macro (familie 4): FRED **DFII10** (reële rente 10 jaar, TIPS, dagelijks) en
  **DTWEXBGS** (brede dollarindex, dagelijks, maar wekelijks gepubliceerd). Gratis, zonder
  sleutel. Om lookahead te voorkomen gebruiken we een waarde pas na een vaste
  publicatievertraging: DFII10 **+3 kalenderdagen**, DTWEXBGS **+10 kalenderdagen**.

## 2. Data-indeling

| Blok | Van | Tot (excl.) | Status | Keer geopend |
|---|---|---|---|---|
| Warm-up | 2004-01-01 | 2006-01-01 | alleen historie voor indicatoren/zones | – |
| **Research R2** | 2006-01-01 | 2019-01-01 | ontwerp, walk-forward, selectie | – |
| **Hold-out H2** | 2019-01-01 | 2020-10-01 | **nooit geopend**; max. 1× per strategie | **0** |
| Bekend blok K | 2020-10-01 | 2025-10-01 | ronde 1 (warm-up + research): gezien | n.v.t. |
| Verbrand blok H1 | 2025-10-01 | 2026-10-01 | hold-out ronde 1 | **1** (ema_pullback) |
| Forward | 2026-10-01 | – | paper trading (alleen met akkoord) | – |

- **H2** (21 maanden) is door geen enkele strategie of toets gebruikt: ronde 1 begon zijn
  data op 2020-10-01. Het is ≥ 12 maanden en bevat twee regimes (stijging 2019, crash en
  herstel 2020).
- **K** is in ronde 1 uitgebreid bekeken (o.a. "de goudtrend domineert"). Die kennis heeft
  de keuze van families in ronde 2 beïnvloed. K wordt daarom **nooit** voor selectie of
  validatie gebruikt; definitieve strategieën worden er alleen beschrijvend op getoond,
  met die waarschuwing.
- **H1 is verbrand** (1× geopend door ema_pullback). Hoe dat meetelt: (1) H1 wordt in
  ronde 2 niet gebruikt, ook niet beschrijvend; (2) die ene opening telt als **1 extra
  trial** in de correctie (§7); (3) de wetenschap uit K en H1 dat goud sterk steeg, is
  precies waarom elke strategie tegen random entries met dezelfde exits en dezelfde
  long/short-verhouding moet worden getoetst (§6).
- Walk-forward binnen R2: **train 4 jaar, test 1 jaar, stap 1 jaar** → test-jaren
  2010 t/m 2018 (9 vensters). Eén schema voor alle families (eenvoud; dagstrategieën
  hebben een lang train-venster nodig voor genoeg trades).

## 3. Uitvoeringsregels (alle families)

- Beslissing op het **slot** van een candle van het beslis-timeframe (15m/1h/4h/daily);
  **entry op de open van de volgende candle** van dat timeframe.
- Stop/target/trailing worden per candle van het beslis-timeframe gecontroleerd. Raakt een
  candle stop en target, dan telt **de stop eerst**. Opent een candle voorbij de stop
  (gat), dan is de exit die open. Een trailing stop wordt bijgewerkt op het slot van een
  candle en geldt vanaf de volgende candle.
- Max. 1 open positie per variant. Initiële stop bepaalt 1R.
- Kosten per round trip = spread + 2 × slippage; standaard 0,40 + 2 × 0,10 = 0,60 USD/oz.
  Elke strategie draait op **1×, 2× en 3×** kosten (instelbaar in `config.yaml`).
  R_netto = (winst/oz − kosten) / (risico/oz + kosten), zoals ronde 1.
- Equity voor drawdown, Sharpe en Calmar: 1% risico per trade, samengesteld.

## 4. Hypothesefamilies (max. 5) en parameterruimtes

Elke variant = één combinatie uit de ruimte. Alle varianten worden in elk train-venster
geëvalueerd (rooster, geen Optuna: de ruimtes zijn klein).

**F1. Daily trendvolgend.** *Waarom:* tijdreeks-momentum is in veel grondstoffen
gedocumenteerd (o.a. Moskowitz, Ooi & Pedersen 2012). Verklaringen: trage
informatieverwerking, kuddegedrag en langzaam bewegende macro-stromen.
- Entry (op daily slot, alleen als er geen positie is):
  `donchian50` / `donchian100` (slot boven het hoogste high / onder het laagste low van de
  vorige N dagen), `tsmom3` / `tsmom6` / `tsmom12` (teken van het rendement over 63/126/252
  dagen; > 0 long, < 0 short).
- Exit: alleen een ATR-trailing stop (chandelier): initieel entry ∓ k × ATR(20 dagen),
  daarna max(stop, hoogste slot sinds entry − k × ATR) (short gespiegeld); k ∈ {3, 4, 5}.
- Long en short. Ruimte: 5 × 3 = **15 varianten**.

**F2. Volatiliteitscompressie → breakout (4h en daily).** *Waarom:* volatiliteit
clustert en keert terug naar het gemiddelde; na een rustige periode volgt vaak een
uitbraak, en de richting daarvan weerspiegelt nieuwe informatie.
- Compressie: Bollinger-bandbreedte (20, 2σ) / koers ligt in het laagste p-percentiel van
  het afgelopen jaar, p ∈ {10, 20}.
- Entry: slot boven het hoogste high (onder het laagste low) van de vorige 20 candles,
  terwijl er in de 5 candles ervoor compressie was.
- Stop: 2 × ATR(14) van dat timeframe. Exit ∈ {`target_2R`, `trail_3atr`}.
- Timeframe ∈ {4h, 1d}. Ruimte: 2 × 2 × 2 = **8 varianten**.

**F3. Mean reversion in rustige regimes (15m en 1h).** *Waarom:* zonder nieuws worden
tijdelijke orderstroom-onevenwichten door liquiditeitsverschaffers teruggeduwd; in rustige
regimes overheerst dat effect, in trends niet.
- Regime: ADX(14) < 20 **of** ATR/koers-percentiel (t.o.v. het afgelopen jaar) < 33.
- Entry: slot onder de onderste Bollinger-band (20, zσ) → long; boven de bovenste → short;
  z ∈ {2,0; 2,5}.
- Target: SMA(20) op het moment van het signaal (vast niveau). Stop: k × ATR(14), k ∈ {1,5; 2,5}.
  Tijdstop: na 40 candles exit op het slot.
- Timeframe ∈ {15m, 1h}. Ruimte: 2 × 2 × 2 × 2 = **16 varianten**.

**F4. Macro-regimefilter bovenop F1 (alleen long).** *Waarom:* goud levert geen rente op,
dus de reële rente is de alternatieve opbrengst; en goud noteert in dollars.
- Alle 15 F1-varianten, **alleen long**, met filter ∈ {`geen`, `reele_rente`, `dollar`}:
  long alleen als de 20-handelsdagen-verandering van DFII10 (resp. DTWEXBGS), met de
  publicatievertraging uit §1, **< 0** is. Een open positie wordt niet door het filter gesloten.
- Ruimte: 15 × 3 = **45 varianten** (`geen` = de long-only referentie om de waarde van
  het filter te kunnen zien).

**F5. Zone-toets op 15m (geen strategie, tenzij er een verschil is).** Herhaling van
vraag 1 uit ronde 1, maar met tests op **15m-candles**:
- Zones: dezelfde zones (methode A, fase-1-parameters) via `zones_as_of` op de
  ronde-2-1h-data, per uur een snapshot. Een 15m-candle gebruikt de snapshot van het
  laatste gesloten uur (geen lookahead).
- Test, uitkomst, 1:2-setup, kosten en nulmodel zoals ronde 1 (horizon 24 candles,
  setup max. 48 candles), met ATR(14) van 15m. 200 nulreplicaties (verschuiving 1–4 ×
  daily ATR per kalendermaand).
- Periode: 2007-01-01 tot 2019-01-01 (zones hebben ≥ 1 jaar historie nodig).
- Beslisregel (zoals ronde 1): alleen als de echte zones boven het 95e percentiel van het
  nulmodel liggen **én** het verschil in ≥ 75% van de jaren dezelfde kant op wijst, mag er
  een 15m-zonestrategie komen (en dan alleen met akkoord van de gebruiker). Anders niet.

## 5. Selectie binnen walk-forward

- Per train-venster de variant met de hoogste **gemiddelde R na kosten (1×)**, mits ≥ 8
  trades (daily-varianten van F1/F2/F4) of ≥ 30 trades (4h, 1h, 15m). Geen geldige
  variant → geen trades in dat test-jaar.
- Elke (variant, train-venster)-evaluatie telt als **1 trial** (zelfde telling als ronde 1).
  Verwacht: F1 135, F2 72, F3 144, F4 405 → 756 trials.
- Definitieve parameters (voor H2): dezelfde selectie op de laatste 4 jaar van R2 (2015–2018).
- Daarnaast (beschrijvend, geen selectie): de prestatie van **elke** variant over alle
  test-jaren, om te zien of een familie robuust is of alleen één toevalstreffer heeft.

## 6. Meetwaarden en toetsen

- **Primair:** gemiddelde R per trade na kosten (walk-forward test-jaren samen), met
  95%-bootstrap-interval (blokken per kalendermaand, 2000 trekkingen).
- **Secundair:** R per jaar, long en short apart, max drawdown, aantal trades, win rate
  naast break-even win rate, Sharpe (jaarlijks, uit maandrendementen) en Calmar t.o.v.
  buy-and-hold over dezelfde periode.
- **Random entries met exact dezelfde exits:** 200 replicaties; per jaar hetzelfde aantal
  entries en dezelfde long/short-verhouding als de strategie, op willekeurige candles;
  stop, target, trailing en tijdstop exact zoals de strategie (berekend op die candle).
  Bij F3 wordt de richting bepaald door de kant van het target (onder de SMA → long), omdat
  de exit-regel anders niet bestaat. Meetwaarde: percentiel van de strategie in de
  random-verdeling.
- **Kosten:** 1×, 2×, 3× met dezelfde gekozen parameters.

## 7. Correctie voor het aantal varianten

- N = 671 (trials ronde 1) + 1 (opening H1) + alle trials van ronde 2.
- **Primair:** deflated Sharpe ratio (per trade), zoals ronde 1: spreiding V uit de
  Sharpes van alle trials met voldoende trades (≥ 15 in ronde 1, ≥ 8 resp. 30 in ronde 2).
- **Gevoeligheid (geen beslisregel):** de "milde" DSR uit ronde 1 (meetruis uit V halen en
  omrekenen naar het aantal OOS-trades).

## 8. Statusregels ronde 2

**candidate**
- OOS-trades: ≥ 100 (4h/1h/15m-varianten). Voor trage daily-families (F1, F4, F2-daily)
  geldt ≥ 30, omdat 9 test-jaren met een trendsysteem niet meer trades opleveren; zo'n
  strategie krijgt het label **"traag"**, het interval weegt zwaarder en hij kan **nooit
  validated** worden zonder forward paper trading (wat akkoord van de gebruiker vereist).
- Gemiddelde R na kosten (1×) > 0 over de test-jaren samen.
- Zonder het beste jaar is de totale R nog > 0.

**validated** (bovenop candidate, en niet "traag")
- H2 één keer geopend: ≥ 30 trades en gemiddelde R > 0;
- DSR ≥ 0,95;
- gemiddelde R boven het 95e percentiel van random entries met dezelfde exits;
- gemiddelde R > 0 bij 2× kosten.

H2 wordt alleen geopend voor candidates, per strategie één keer, via de hold-out-bewaker
(log `research/round2/holdout_log.json`).

## 9. "Te mooi"-protocol

Bij > +0,3 R per trade na kosten, of hooguit één verliesjaar: eerst proberen het kapot te
maken vóór rapportage:
1. lookahead-test (signalen veranderen niet als de toekomst verandert);
2. fill-volgorde (entry volgende open; stop vóór target; gat voorbij stop);
3. kosten herberekenen en 3× kosten bekijken;
4. dubbeltellingen (overlappende trades, max. 1 open);
5. long-bias: long en short apart, en vergelijking met random met dezelfde exits en
   dezelfde long/short-verhouding.
Wat gecontroleerd is, staat in het rapport.

## 10. Wijzigingslog

- 2026-10-10, **ná** de walk-forward-resultaten van F1–F4 (alle rejected), **toevoeging,
  geen wijziging**: een verkennende analyse per variant van F1, F2 en F4 over alle
  test-jaren (2010–2018, zonder selectie), elk vergeleken met 200 random-entry-replicaties
  met exact dezelfde exits, plus voor F4 het verschil met en zonder macrofilter. Reden: bij
  F1 zijn 13/15 varianten positief, terwijl random entries met dezelfde trailing stop ook
  +0,13 R halen. De vraag "zit het in de entry of in de exit?" is de kern. Dit verandert
  geen status en telt niet als nieuwe trials (er wordt niets gekozen).
- 2026-10-10, **ná** de resultaten, verduidelijking zonder effect op de status: "F2-daily"
  in §8 is uitgevoerd als "alle gekozen varianten zijn daily". In de walk-forward koos F2
  in 2017–2018 een 4h-variant, dus geldt de grens van 100 trades (64 gehaald). Deze lezing
  stond al in de code vóór de run. Met de mildere lezing (≥ 30) zou F2 "candidate (traag)"
  zijn, maar nooit validated (DSR 0,00; 78e percentiel van random).
