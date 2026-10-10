# Ronde 3 – onderzoeksplan: lage-frequentie regels op een gespreid ETF-universum

Vastgelegd **voordat** er één backtest van ronde 3 is gedraaid. De git-commit van dit
bestand is het bewijs. Vooraf bekeken: alleen beschikbaarheid en kwaliteit van de data
(startdata, ontbrekende dagen, dividendcorrectie; `results/data_quality.json`, §1). Er is
geen rendement van een strategie of baseline berekend. Wijzigingen achteraf staan in §11.

Parameters staan in `etf/config.yaml`. Code in `etf/`, uitvoer in `research/round3/`.
Dit is alleen onderzoek: niets gaat naar de live workflow, Telegram of paper trading. Geen
echt geld, geen broker. De goud-onderdelen (ema_pullback, de forward-test vol_squeeze_4h,
hun vingerafdrukken, FORWARD.md, de uurlijkse workflow) worden niet aangeraakt.

## 0. Vraag en verwachting

**Vraag.** Verbeteren eenvoudige trend-, momentum- of volatiliteitsregels op een gespreid
ETF-universum het **risico-gecorrigeerde** resultaat van een buy-and-hold-portefeuille
**na kosten**? En is dat stabiel over periodes?

**Geldige uitkomsten:**
- (a) geen verbetering;
- (b) vergelijkbaar rendement met een kleinere maximale daling;
- (c) beter.

We optimaliseren **niet** om buy-and-hold op totaalrendement te verslaan. In bullmarkten
lopen trendregels meestal achter. Succes betekent hier vooral: minder risico, zonder dat dat
alleen komt door minder te beleggen. Gepubliceerde effecten worden na publicatie meestal
kleiner (data-mining, crowding). We verwachten dus minder dan in de literatuur.

## 1. Data

- **Bron:** yfinance (Yahoo), dagelijkse **Adj Close**: gecorrigeerd voor dividend en
  splitsing, dus het totaalrendement. De ETF-kosten (TER) zitten al in de koers.
  **Belasting wordt niet meegenomen** (dividendbelasting, vermogensbelasting).
- **Cash:** FRED **TB3MS** (3-maands T-bill, maandgemiddelde), opgehaald via de
  publieke `fredgraph.csv`, zonder API-sleutel. Dat werkt, dus SHY is niet nodig.
  - Dagrendement = (1 + rente)^(1/252) − 1, met de rente van de eigen maand. Dat is een
    uitkomst en geen beslisinformatie.
  - Voor beslissingen (absolute momentum) gebruiken we op het slot van maand m de rentes van
    de maanden m−L … m−1. Reden: TB3MS van maand m verschijnt pas begin maand m+1.
- **Handelsdagen:** de dagen waarop SPY noteert (NYSE). Ontbreekt een koers binnen de
  historie van een ticker, dan geldt de vorige koers (rendement 0). In het research-blok komt
  dat 0× voor.
- **Universum** (vast, er komen geen assets bij na het zien van resultaten):

| ETF | Wat | Eerste dag (Yahoo) | Doet mee vanaf (signaal → houden) |
|---|---|---|---|
| SPY | Amerikaanse aandelen (S&P 500) | 1993-01-29 | begin research |
| EFA | aandelen ontwikkelde markten ex-VS/Canada (MSCI EAFE) | 2001-08-27 | begin research |
| EEM | aandelen opkomende markten (MSCI EM) | 2003-04-14 | begin research |
| TLT | Amerikaanse staatsobligaties 20+ jaar | 2002-07-30 | begin research |
| IEF | Amerikaanse staatsobligaties 7–10 jaar | 2002-07-30 | begin research |
| LQD | bedrijfsobligaties investment grade | 2002-07-30 | begin research |
| VNQ | vastgoed (REITs) | 2004-09-29 | eind sep 2005 → okt 2005 |
| GLD | goud (fysiek) | 2004-11-18 | eind nov 2005 → dec 2005 |
| DBC | grondstoffen (futures, gespreid) | 2006-02-06 | eind feb 2007 → mrt 2007 |

- **Wanneer doet een asset mee?** Pas als hij **13 maandslotkoersen** heeft, inclusief de
  eerste (gedeeltelijke) maand. Dat is genoeg voor elke regel in het grid (12-maands
  gemiddelde en 12-maands rendement).
  - Dezelfde regel geldt voor de baselines. Zo vergelijken strategie en baseline altijd
    hetzelfde universum.
  - Het universum groeit dus van 6 assets (2005) naar 9 (vanaf maart 2007).
- **Datakwaliteit** (research-blok, t/m 2020-12; `results/data_quality.json`):
  - 0 ontbrekende handelsdagen, 0 lege of nul-koersen;
  - de verhouding Adj Close / Close verspringt **alleen** rond een dag met een uitkering of
    splitsing (0 sprongen zonder gebeurtenis), dus de dividendcorrectie is consistent;
  - splitsingen: EFA 1×, EEM 2× (correct verwerkt);
  - grote dagbewegingen (> 15%) alleen in oktober 2008 – maart 2009 en maart 2020 (EFA, EEM,
    VNQ). Die zijn echt.
  - Voor H3 en de fondsen van P zijn **alleen** de begindatum en ontbrekende dagen bekeken,
    geen rendementen.
- **Fondswijzigingen** (uit mijn kennis, niet uit de data; zelf controleren):
  - TLT en IEF: indexaanbieder Lehman → Barclays → ICE (2016), zelfde looptijdsegment;
  - LQD: andere benchmark in 2006 (iBoxx $ Liquid Investment Grade);
  - VNQ: van MSCI US REIT naar MSCI US IMI Real Estate 25/50 (rond 2013 en 2018, ook
    niet-REIT-vastgoed);
  - DBC: sponsor Deutsche Bank → Invesco (2015), index DBIQ Optimum Yield Diversified; het
    rendement op het onderpand (T-bills) zit in de koers;
  - EFA, EEM, SPY, GLD: geen wezenlijke wijziging. Wel verandert MSCI de samenstelling (o.a.
    China A-aandelen in EEM vanaf 2018).
- **Overlevingsbias:** het universum is achteraf gekozen. Het is het bekende
  9-klassen-universum uit de literatuur (Faber 2007), en alle 9 ETF's bestaan nog en zijn
  groot. Dat is een bias in het voordeel van élke strategie op dit universum, ook
  buy-and-hold. We meten daarom altijd *verschillen* met een baseline op hetzelfde universum.
- **Valuta:** basis in USD. Robuustheid in EUR met FRED **DEXUSEU** (USD per EUR); zie §7.

## 2. Data-indeling

| Blok | Periode (rendementen) | Gebruik | Keer geopend |
|---|---|---|---|
| Warm-up | t/m 2004-12 (ETF-koersen) | alleen terugkijken voor signalen (max. 13 maanden) | – |
| **Research** | 2005-01 – 2020-12 (16 jaar, 192 maanden) | ontwerp, grid, status | – |
| **Hold-out H3** | 2021-01 – 2026-09 (5,75 jaar) | max. 1× per eindconfiguratie, alleen als die *candidate* is | **0** |
| **Pre-sample P** | 1996-01 – 2004-12 (9 jaar, fondsen als proxy) | eenmalige bevestiging, max. 1× per candidate | **0** |

- **Waarom research vanaf 2005-01** en niet eerder? P loopt t/m 2004. Begint research
  eerder, dan overlappen research en P in tijd, en is P geen onafhankelijke bevestiging meer.
  - Op het slot van december 2004 hebben 6 ETF's (SPY, EFA, EEM, TLT, IEF, LQD) volledige
    signaaldata.
  - De koersen van 2004 worden alleen gebruikt om de eerste signalen te berekenen (warm-up),
    niet om iets te beoordelen.
- **H3** eindigt op 2026-09-30, de laatste volledige maand bij het vastleggen. Code leest
  research-data altijd met einddatum 2021-01-01. H3 en P zijn alleen via `etf/holdout.py` te
  openen, dat elke opening logt in `research/round3/holdout_log.json`.
- **Gevolg voor het rapport:** 2022 ligt in H3. Gedrag in 2022 (en in 2000–2002, in P) wordt
  alleen getoond voor configuraties waarvoor H3 (resp. P) volgens de regels geopend is. Is
  geen enkele configuratie candidate, dan staat er in het rapport níets over 2022 voor deze
  regels, en dat zeggen we er dan expliciet bij.

## 3. Uitvoeringsconventie (alle regels en baselines)

- **Signaal** op de laatste handelsdag van maand m, met alleen slotkoersen t/m die dag.
- **Uitvoering** op de **slotkoers van de eerste handelsdag van maand m+1**. Nooit dezelfde
  bar.
  - Het rendement van die eerste dag (slot vorige dag → slot uitvoeringsdag) valt nog onder
    de oude gewichten.
  - De nieuwe gewichten gelden vanaf de dag erna.
- **Tussen twee uitvoeringen** wordt er niets verhandeld: de gewichten drijven mee met de
  koersen.
  - Bij de uitvoering wordt teruggezet naar het doelgewicht.
  - Het verhandelde bedrag = Σ |doelgewicht − meegedreven gewicht| over de risicovolle
    assets (cash is gratis).
- **Kosten** = tarief × verhandeld bedrag, afgeboekt op de uitvoeringsdag. Standaard
  **0,10%**, met gevoeligheid **0%, 0,10% en 0,30%**.
  - Elke portefeuille, ook elke baseline, begint in cash op de eerste uitvoeringsdag
    (2005-01-03) en betaalt de eerste aankoop.
- **Maandrendement** = rendement per kalendermaand uit de dagelijkse waarde.
- Lookahead-tests in `tests/test_etf.py`:
  - signalen veranderen niet als koersen ná het signaalmoment veranderen;
  - het rendement op de uitvoeringsdag valt onder de oude gewichten;
  - herbalanceren, meedrijven en kosten kloppen in handberekende voorbeelden;
  - research-data bevat nooit data van 2021 of later.

## 4. Families (3) en grid

Gewichten worden bepaald over de assets die op dat moment meedoen (K = aantal, 6 tot 9).
Elke combinatie is **één trial**. Vooraf gekozen **primaire configuratie** per familie: die
bepaalt de status. Het grid is er om te zien of dat een plateau is. **We kiezen niet de
beste cel.**

**F1 – Trendfilter per asset.**
- *Waarom:* tijdreeks-momentum: prijstrends houden aan door trage informatieverwerking en
  kuddegedrag. Uit een dalende trend stappen beperkt lange dalingen (Faber 2007, Moskowitz
  e.a. 2012).
- *Regel:* elke asset krijgt 1/K als zijn maandslot boven het gemiddelde van de laatste N
  maandsloten ligt (inclusief deze); anders gaat dat deel naar cash.
- *Grid:* N ∈ {6, 8, 10, 12}, **4 trials**. Primair: **N = 10** (literatuur).

**F2 – Dual momentum.**
- *Waarom:* relatieve momentum (wat de laatste maanden het best deed, doet het vaak nog even
  goed) plus absolute momentum (alleen beleggen als het rendement boven cash ligt) (Antonacci
  2014).
- *Regel:* rangschik de assets op het totaalrendement over L maanden (slot m−L → slot m).
  Neem de top k, elk met gewicht 1/k, maar alleen als dat rendement hoger is dan het
  cashrendement over dezelfde L maanden (zoals bekend op het slot; §1). Anders gaat dat deel
  naar cash.
- *Grid:* k ∈ {2, 3, 4} × L ∈ {6, 9, 12}, **9 trials**. Primair: **k = 3, L = 12**.

**F3 – Volatility targeting.**
- *Waarom:* volatiliteit is goed te voorspellen (ze clustert), rendement nauwelijks. Minder
  beleggen als de volatiliteit hoog is, kan het risico-gecorrigeerde rendement verbeteren
  (Moreira & Muir 2017).
- *Regel:* basisportefeuille B ∈ {gelijk gewicht over het universum, 60/40 SPY/IEF}.
  - Gerealiseerde volatiliteit σ = standaardafwijking van de dagrendementen van B (met de
    huidige basisgewichten) over de laatste W handelsdagen t/m het signaal, × √252.
  - Blootstelling e = min(1, doel / σ), **zonder hefboom**. Gewichten = e × B, de rest gaat
    naar cash.
- *Grid:* 2 bases × doel ∈ {8%, 10%, 12%} × W ∈ {20, 60} dagen, **12 trials**.
- Primair per basis: **doel 10%, W = 20** (één maand terug, zoals Moreira & Muir). F3
  levert dus **twee** eindconfiguraties (F3-EW en F3-60/40).

**Totaal: 25 trials.** Herberekeningen voor robuustheid (kosten, timing, leave-one-out, EUR)
zijn geen nieuwe trials: er wordt niets gekozen. De 1.429 trials van de goud-rondes horen bij
een andere vraag op andere data en tellen hier niet mee (§8).

## 5. Baselines

Elke regel wordt gemeten tegen de **passende baseline** op hetzelfde universum, met dezelfde
uitvoering en dezelfde kosten:

| Familie | Baseline voor Sharpe | Baseline voor maximale daling |
|---|---|---|
| F1, F2 | gelijk gewicht (EW), maandelijks herbalanceerd | EW met **dezelfde gemiddelde tijd in de markt** als de regel (ē × EW + rest cash) |
| F3-EW | EW | ē × EW + rest cash |
| F3-60/40 | 60/40 SPY/IEF | ē × 60/40 + rest cash |

- **Tijd in de markt** ē = gemiddelde van Σ doelgewichten (risicovol) over de uitvoeringen in
  de beoordeelde periode.
- **Waarom twee baselines?** Een kleinere daling krijg je ook door gewoon minder te
  beleggen. Telt een kleinere daling, dan moet die dus beter zijn dan een vaste mix met
  evenveel cash.
  - Sharpe (over het rendement boven cash) verandert nauwelijks als je bijmengt met cash.
  - Daarom meten we Sharpe tegen de volle baseline en de daling tegen de mix.
- **Daarnaast beschrijvend:** buy-and-hold per asset (één keer kopen, nooit herbalanceren)
  en 60/40.
- **Willekeurige timing** (1000 simulaties per primaire configuratie):
  - F1/F2: de reeks gewichten van elke asset wordt in de tijd **circulair verschoven** met
    een willekeurig aantal maanden (≥ 12 en ≤ lengte − 12), per asset onafhankelijk, binnen
    de maanden dat die asset meedoet. Komt de som daarna boven 100%, dan wordt alles naar
    rato verlaagd.
  - F3: de reeks blootstellingen e wordt als geheel verschoven.
  - Zo blijven de tijd in de markt, het aantal wissels (dus de kosten, zelfde tarief) en de
    lengte van de "aan"-periodes vrijwel gelijk. Alleen het *moment* wordt willekeurig.
  - Uitkomst: het percentiel van de regel (Sharpe en maximale daling) tussen de 1000
    simulaties. Gerapporteerd worden ook de gemiddelde tijd in de markt en de kosten van de
    simulaties.

## 6. Meetwaarden

**Primair** (maandrendementen, research 2005-01 – 2020-12, kosten 0,10%):
- **Sharpe-verschil** = Sharpe(regel) − Sharpe(baseline).
  - Sharpe = gemiddeld maandrendement boven cash ÷ standaardafwijking daarvan × √12.
- **Verschil in maximale daling** (MDD, op maandslotwaarden) = |MDD baseline| − |MDD regel|,
  in procentpunt. Positief = de regel daalt minder.
- **Onzekerheid:** stationaire block bootstrap (Politis & Romano).
  - Maanden worden in blokken getrokken met een willekeurige lengte, gemiddeld **12
    maanden**, 2000 trekkingen.
  - Alle reeksen worden met **dezelfde** getrokken maanden herberekend (gepaard).
  - Waarom blokken? Maandrendementen hangen samen (trends, volatiliteitsregimes). Losse
    maanden trekken zou te smalle intervallen geven.
  - Uitkomst: 95%-interval en het aandeel trekkingen met een verbetering.

**Secundair:**
- CAGR, volatiliteit en Sortino;
- Calmar (CAGR ÷ |MDD|);
- MDD op dagbasis;
- ergste kalenderjaar en rendement in 2008 en 2020;
- omloopsnelheid (verhandeld bedrag per jaar);
- aantal transacties per jaar (asset-transacties > 0,5% van de portefeuille);
- kosten per jaar en tijd in de markt;
- rolling 10-jaarsvensters (120 maanden, stap 1 maand) van Sharpe-verschil en MDD-verschil.

**Statistisch vermogen** (vooraf, benadering van Jobson-Korkie/Memmel):
- Met 16 jaar data en Sharpe ≈ 0,5 is de standaardfout van een Sharpe-verschil ≈ 0,12 bij
  een correlatie van 0,9 tussen regel en baseline, en ≈ 0,21 bij 0,7.
- Met 80% kans aantoonbaar (tweezijdig 5%) is dan een Sharpe-verschil van ongeveer **+0,35
  resp. +0,60**.
- In de literatuur gaat het om +0,1 tot +0,3. **Een echt, bescheiden effect is met deze data
  dus waarschijnlijk niet aan te tonen.** Daarom eisen we voor *candidate* geen
  significantie (§9).
- Na de run berekenen we de MDE ook met de bootstrap-standaardfout en wegen de uitkomsten
  daarop.

## 7. Robuustheid

- **Heel het grid** als heatmap (Sharpe-verschil en MDD-verschil), niet alleen de primaire
  cel.
- **Breedte:**
  - F1 per asset (trendfilter vs buy-and-hold van die asset).
  - Leave-one-asset-out voor F1, F2 en F3-EW: de primaire configuratie opnieuw, telkens
    zonder één asset (ook uit de baseline).
- **Subperiodes:** 2005–2009, 2010–2014, 2015–2020.
- **Zonder de twee beste jaren:** de twee kalenderjaren met het grootste rendementsverschil
  in het voordeel van de regel (t.o.v. de baseline van de geclaimde maatstaf) worden uit beide
  reeksen gehaald; daarna opnieuw meten.
- **Kosten** 0%, 0,10% en 0,30%.
- **Timing:**
  - uitvoering een handelsdag later (tweede handelsdag van de maand);
  - ter controle ook op het slot van de signaaldag zelf. Dat laatste is *niet* realistisch:
    het laat alleen zien hoe gevoelig de uitkomst is voor timing.
- **Dividendcontrole:** voor elke ETF het totaalrendement uit Adj Close vergeleken met slot +
  zelf herbelegde dividenden (uit de uitkeringsdata).
- **EUR:**
  - (i) alle USD-rendementen, cash inbegrepen, omgerekend naar EUR met DEXUSEU, zonder
    afdekking;
  - (ii) idem, maar het cash-deel in euro tegen de 3-maands eurorente (FRED
    IR3TIB01EZM156N), zoals een Nederlandse belegger zou doen;
  - Sharpe in EUR boven die eurorente. De signalen blijven op USD-koersen.
  - Gemeld wordt het verschil met USD voor de primaire configuraties.

## 8. Correctie voor het aantal trials (voor *validated*)

**Methode: bootstrap-max-toets (White's Reality Check, in de vorm van Romano–Wolf voor één
hypothese).**
- In gewone taal: stel dat géén van de 25 regels echt iets toevoegt. Dan levert toeval toch
  bij één van de 25 een verschil op, en het grootste daarvan kan flink zijn. We schatten met
  de bootstrap hoe groot dat grootste toevalsverschil is. Pas als het verschil van onze
  primaire configuratie in ≥ 95% van de gevallen groter is dan dat grootste toevalsverschil,
  telt het.
- Technisch:
  - per trekking b en per trial j: d_j^b − d_j (gecentreerd);
  - p = aandeel trekkingen met max_j (d_j^b − d_j) ≥ d_primair;
  - drempel p < 0,05;
  - dit gebeurt op dezelfde maatstaf als de claim (Sharpe- of MDD-verschil), met elke trial
    tegen zijn eigen passende baseline.
- **Waarom niet de deflated Sharpe ratio?**
  - De DSR toetst of de Sharpe van één reeks boven nul ligt, na correctie voor het aantal
    pogingen. Onze vraag is of een regel *beter is dan een baseline*. Buy-and-hold heeft zelf
    al een positieve Sharpe, dus de DSR zou bijna alles "goed" vinden.
  - De Reality Check toetst precies het verschil, gebruikt dezelfde bootstrap als de
    intervallen en telt alle 25 trials mee.
- Trials uit de goud-rondes tellen niet mee: andere vraag, andere markt, en geen selectie
  over die trials heen.

## 9. Statusregels

Beoordeeld per **primaire configuratie** (4 stuks: F1, F2, F3-EW, F3-60/40), op de maatstaf
die hij claimt: **Sharpe-verschil** (vs volle baseline) en/of **MDD-verschil** (vs baseline
met dezelfde tijd in de markt).

**candidate** – alle punten gelden voor de geclaimde maatstaf, na kosten van 0,10%:
1. puntschatting > 0;
2. ≥ **80%** van de bootstrap-trekkingen laat een verbetering zien;
3. het 95%-interval is niet onzinnig breed: ≤ **1,0** Sharpe-eenheid, resp. ≤ **25
   procentpunt** bij MDD;
4. stabiel:
   - verbetering (puntschatting) in ≥ **2 van de 3** subperiodes, **én**
   - nog > 0 zonder de twee beste jaren, **én**
   - bij F1, F2 en F3-EW nog > 0 bij elke leave-one-asset-out;
5. nog > 0 bij **0,30%** kosten (3×);
6. plateau:
   - ≥ **2/3** van de directe buren in het grid verbetert ook, **én**
   - ≥ **de helft** van het hele grid van die familie (bij F3: per basis);
7. alleen bij een MDD-claim: het Sharpe-verschil is niet slechter dan **−0,10**.

**rejected:** niet aan deze punten voldaan, waaronder: alleen goed in een piek van het grid,
alleen door één asset of periode, of geen verbetering na kosten.

**validated:** candidate, **plus**:
- H3 één keer geopend en de geclaimde maatstaf > 0 (puntschatting, met ē uit H3);
- P één keer geopend en > 0;
- Reality Check p < 0,05 (§8).

Verwacht: weinig of niets wordt validated. Dat is een geldige uitkomst.

H3 en P worden alleen geopend voor candidates, per eindconfiguratie één keer, via
`etf/holdout.py`. Daarna wordt er niets meer aan de configuratie veranderd.

**P in detail:**
- Proxies: VFINX (SPY), VGTSX (EFA), VEIEX (EEM), VUSTX (TLT), VFITX (IEF), VFICX (LQD) en
  VGSIX (VNQ). Goud en grondstoffen hebben geen proxy en vallen weg (7 assets).
  - VGTSX doet mee vanaf mei 1997, VGSIX vanaf juni 1997 (13 maandsloten). Tot dan zijn het 5
    assets.
  - VGTSX bevat ook opkomende markten.
  - Afwijking van het voorbeeld in de opdracht: voor EEM bestaat wél een proxy (Vanguard
    Emerging Markets Stock Index, VEIEX, sinds 1994). Die doet daarom mee.
- 60/40 in P = VFINX/VFITX.
- Het universum is anders dan in research, dus vergelijkbaarheid is beperkt. Dat staat in het
  rapport.

**Oordeel voor het rapport** (per familie, en overall het best onderbouwde):
- **(c) beter:** candidate (of beter) op het Sharpe-verschil.
- **(b) kleinere daling bij vergelijkbaar rendement:** candidate op MDD, de MDD is ook
  kleiner dan van de volle baseline, en de CAGR ligt hooguit **1 procentpunt** onder de volle
  baseline.
- **(a) geen verbetering:** al het andere. Dat geldt ook voor "minder daling, maar alleen
  door minder te beleggen".

**Hoe zeker:**
- rejected → (a), met de intervallen;
- candidate zonder H3/P → "aanwijzing";
- validated → "aangetoond binnen de grenzen van deze data".

## 10. "Te mooi"-protocol

Bij een Sharpe-winst > **0,40**, of een MDD (maandslot) < **10%** bij een CAGR die niet lager
is dan die van de baseline: eerst proberen het kapot te maken, en pas daarna rapporteren.
1. lookahead-tests (§3) en de timingvarianten (§7);
2. overlevingsbias en de keuze van het universum (leave-one-asset-out);
3. dividendcontrole van Adj Close (§7);
4. leave-one-year-out: draagt één jaar alles?
5. kosten 3×.

De controles 1, 3 en 5 en leave-one-asset-out draaien we **altijd**, voor alle primaire
configuraties. Wat er gecontroleerd is, staat in het rapport.

## 11. Wijzigingslog

_(nog geen wijzigingen)_
