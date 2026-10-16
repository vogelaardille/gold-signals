# Ronde 4 – onderzoeksplan: daytrade-patronen in valuta (EUR/USD, GBP/USD, USD/JPY)

Vastgelegd **voordat** er één backtest van ronde 4 is gedraaid. De git-commit van dit
bestand is het bewijs. Vooraf bekeken: alleen of Dukascopy de data levert (welke jaren,
welke timeframes, bid en ask) en een steekproef van de spread op een paar dinsdagen (§1).
Er is geen rendement van een strategie berekend. Wijzigingen achteraf staan in §11.

Parameters komen in `fx/config.yaml`, code in `fx/`, uitvoer in `research/round4/`.
Dit is alleen onderzoek: niets gaat naar de live workflow, Telegram of paper trading zonder
akkoord van de gebruiker. Geen echt geld, geen broker. De goud-onderdelen (ema_pullback,
de forward-test vol_squeeze_4h, hun vingerafdrukken, de uurlijkse workflow) en de code van
ronde 2 en 3 worden niet aangeraakt.

## 0. Vraag en verwachting

**Vraag.** Leveren drie in de literatuur beschreven intraday-patronen in valuta een
voordeel op **na echte kosten** (gemeten bid/ask-spread plus slippage), als daytrade
(nooit een positie over de dagwissel van 17:00 New York)?

1. **Fix-reversal** (Krohn, Mueller & Whelan, *Journal of Finance* 2024): de dollar stijgt
   in de uren vóór de grote fixes (Tokio 9:55, ECB 14:15 Frankfurt, Londen 16:00) en daalt
   daarna. Waarom: dealers dekken de vraag naar dollars bij de fix af en bouwen die positie
   daarna weer af.
2. **Ronde getallen** (Osler, *Journal of Finance* 2003): take-profit-orders liggen vaak óp
   ronde koersen, dus daar keert de koers vaker. Stop-loss-orders liggen net *voorbij* ronde
   koersen, dus na een doorbraak versnelt de beweging.
3. **London breakout**: doorbraak van de Aziatische range bij de opening van Londen. Dit is
   een populaire strategie bij particuliere handelaren, maar ik heb er geen onafhankelijk
   onderzoek naar gevonden. Hij dient als **controle**: wat levert "wat iedereen gebruikt"
   op?

**Geldige uitkomsten:** (a) geen voordeel na kosten; (b) een patroon bestaat bruto, maar
verdwijnt door de kosten; (c) voordeel na kosten.

**Verwachting vooraf:**
- F1: bruto zichtbaar in het research-blok, want dat overlapt met de steekproef van de
  paper. Netto hooguit klein. Na de publicatie (H4) waarschijnlijk kleiner.
- F2: zwak, want de orderdata van Osler komt uit 1999–2000.
- F3: waarschijnlijk niets.

Gepubliceerde effecten worden na publicatie meestal kleiner. "Het werkt niet" is een
geldige uitkomst.

## 1. Data

- **Bron:** Dukascopy via `dukascopy_python`, **1h-candles, bid én ask**, voor EUR/USD,
  GBP/USD en USD/JPY. Dezelfde bron als bij goud. **Geen yfinance.**
- **Beschikbaarheid** (getest op 2026-10-16, steekproef van 2 handelsdagen per jaar):
  - 1h bid en ask: beschikbaar vanaf 2003 voor alle drie de paren.
  - 15m, 5m en 1m: via deze library pas vanaf **2012**. Daarom werkt ronde 4 **alleen met
    1h**. Alle tijdstippen in §4 vallen op hele uren of zijn daarop afgerond (zie daar).
  - Bij USD/JPY gaf één steekproefdag (juni 2010) 0 candles. De volledige kwaliteitscontrole
    moet uitwijzen of dat een gat in de bron is of een haperende download.
- **Spread-steekproef** EUR/USD (mediaan op een paar dinsdagen): ongeveer 1,0 pip in
  2003–2010 en 0,4 pip vanaf 2015. Dit is kosteninformatie, geen rendement.
- **Cache:** `data/cache/fx/{PAAR}_1h_{bid|ask}.parquet`, download per kalenderjaar (zoals
  ronde 2). De live-cache en de cache van ronde 2 blijven onaangeroerd.
  - De downloader van ronde 2 (`goldsignals/round2/data.py`) heeft `XAU/USD` vast in de
    code. Ronde 4 krijgt een eigen `fx/data.py` met het paar als parameter. Code van ronde 2
    verandert niet.
  - Gezien in de steekproef: bij een tijdloze (naive) start van 2019-03-07 00:00 begon de
    data op 2019-03-06 23:00 UTC. De library leest naive tijden dus als lokale tijd. `fx/data.py`
    geeft daarom altijd tijden in UTC door.
- **Kwaliteitscontrole vóór de eerste backtest** (`research/round4/data_quality.md`), per
  paar en per jaar:
  - ontbrekende handelsuren, candles zonder beweging, sprongen > 8× de mediane range;
  - ask < bid (mag niet voorkomen);
  - spreadverdeling per jaar en per uur van de dag (kosten, geen rendement);
  - **tijdstempelcontrole:** op vrijdagen met het Amerikaanse banenrapport (8:30 New York)
    moet de grootste gemiddelde absolute uurbeweging in de bar van 08:00 NY vallen. Klopt
    dat niet, dan **stoppen** we en zoeken eerst uit waarom. Een tijdsverschuiving van één
    uur zou F1 waardeloos maken.
  - Een paar-jaar met > 5% ontbrekende handelsuren valt weg voor dat paar. Dat staat in
    het rapport.
  - Voor H4 worden alleen ontbrekende uren en de tijdstempels bekeken, geen rendementen.
- **Prijzen:** signalen op **mid** (gemiddelde van bid- en ask-candle per veld). Fills op
  **ask bij kopen en bid bij verkopen** (§3).
- **Markturen:** valuta handelt van zondag 17:00 tot vrijdag 17:00 New York-tijd. Een
  feestdagenkalender gebruiken we niet. Ontbreekt de bar op een vereist entry- of exitmoment,
  dan wordt er die dag niet gehandeld (bij een ontbrekende exitbar: exit op de eerstvolgende
  open).

## 2. Data-indeling

| Blok | Periode | Gebruik | Keer geopend |
|---|---|---|---|
| Warm-up | 2003-06 – 2004-12 | alleen terugkijken (ATR, versheid van niveaus) | – |
| **Research R4** | 2005-01-01 – 2020-01-01 (15 jaar) | ontwerp, status | – |
| **Hold-out H4** | 2020-01-01 – 2026-10-01 (6,75 jaar) | max. 1× per primaire configuratie, alleen als die *candidate* is | **0** |
| Forward | vanaf 2026-10-01 | eventueel paper trading, alleen met akkoord | – |

- **Waarom deze grens?** De steekproef van Krohn e.a. loopt t/m 2019. R4 is voor F1 dus een
  **replicatie**: overlap met de paper. H4 is volledig ná die steekproef: een echte test of
  het patroon is blijven bestaan.
- Intraday-valutadata is in eerdere rondes niet gebruikt. Wel dagreeksen: de dollarindex
  DTWEXBGS (macrofilter in ronde 2) en DEXUSEU (EUR-omrekening in ronde 3). Daaruit zijn
  geen intraday-patronen af te lezen, dus H4 is voor deze vraag ongezien.
- Research-code laadt data altijd met `until = 2020-01-01`. H4 is alleen te openen via
  `fx/open_holdout.py`, en elke opening wordt gelogd in `research/round4/holdout_log.json`.

## 3. Uitvoeringsconventie (alle families)

- **Signaal** op de close van een 1h-bar. **Entry** op de open van de volgende bar. Bij
  tijdgestuurde regels (F1) is de entry de open van de genoemde bar. Nooit dezelfde bar.
- **Fills:** long = kopen op de **ask**-open, sluiten op de **bid**. Short andersom. Zo zit de
  echte spread van dát uur in elke trade, ook de bredere spread in rustige uren.
- **Slippage:** 0,1 pip per kant, bovenop de spread. Een pip is 0,0001 (EUR/USD, GBP/USD)
  of 0,01 (USD/JPY).
- **Stop en target** (F2, F3): getoetst op de bid-candle (long) of ask-candle (short).
  - De stop gaat vóór het target binnen één bar.
  - Gat voorbij de stop: exit op de open.
- **Daytrade-regel:** geen positie over 17:00 New York (dagwissel en rollover: brede spread,
  swap). Elke positie sluit **uiterlijk op de open van de bar van 16:00 NY**. Tussen 14:00
  en 18:00 NY geen nieuwe entries (behalve de vaste vensters van F1).
- **Max. 1 open trade** per configuratie per paar.
- **Rendement per trade** = winst in USD als fractie van de nominale waarde bij entry, in
  **basispunten (bp)**. Voor F2/F3 ook in **R** (winst gedeeld door het stopverlies bij
  entry).
- **Dagreeks:** per configuratie de som van de netto bp per handelsdag (0 op dagen zonder
  trade). Die reeks gebruiken we voor Sharpe, bootstrap en de Reality Check.
- **Lookahead-tests** in `tests/test_fx.py`:
  - signalen veranderen niet als koersen ná het signaalmoment veranderen;
  - fills altijd op de volgende open, met de juiste kant (bid of ask);
  - de tijdvensters kloppen rond zomertijdwissels (NY, Londen en Frankfurt wisselen niet
    tegelijk; Tokio heeft geen zomertijd);
  - research-data bevat nooit data van 2020 of later.

## 4. Families (3) en grid

Alle tijden zijn lokale kloktijd, omgerekend naar UTC per dag (zomertijd-bewust). Elke
configuratie is **één trial**. Vooraf gekozen **primaire configuraties** bepalen de status.
Het grid is er om te zien of dat een plateau is. **We kiezen niet de beste cel.**

**F1 – Fix-reversal** (Krohn e.a. 2024; verwant: Breedon & Ranaldo 2011)
- *Benen*, elk een vaste tijdsexit, zonder stop of target. "Long USD" = short EUR/USD,
  short GBP/USD en long USD/JPY.

| Been | Positie | Entry (open van bar) | Exit (open van bar) | Afwijking van de paper |
|---|---|---|---|---|
| T-pre | long USD | 18:00 NY | 10:00 Tokio | paper start 17:00 NY; wij één uur later vanwege de rollover-spread. Exit 5 min na de fix van 9:55 |
| T-post | short USD | 10:00 Tokio | 08:00 Frankfurt | – |
| E-pre | long USD | 08:00 Frankfurt | 14:00 Frankfurt | paper tot 14:15 (fix); 1h-data dwingt 14:00 |
| L-post | short USD | 16:00 Londen | 16:00 NY | paper tot 17:00 NY; wij stoppen vóór de rollover |

- Het venster tussen de ECB- en de Londen-fix wordt niet verhandeld: de paper vindt daar
  geen consistente beweging.
- *Combinaties:* **Tokio** = T-pre + T-post; **Europa** = E-pre + L-post. Dat is de som van
  twee benen, er komt dus niets nieuws bij. Ze tellen toch als trial (voorzichtig).
- *Trials:* (4 benen + 2 combinaties) × 3 paren = **18**. Er zijn geen parameters, dus er
  is ook niets te optimaliseren.
- *Primair* (de sterkste voorspellingen uit de paper, vóór onze data vastgelegd):
  - **F1-EU: Europa op EUR/USD;**
  - **F1-TK: Tokio op USD/JPY.**
- Londen-fix: sinds 15-02-2015 is het fixvenster 5 minuten (15:57:30–16:02:30), daarvoor 1
  minuut. Subperiode 2015–2019 laat zien of dat uitmaakt.

**F2 – Ronde getallen** (Osler 2003)
- *Niveaus:* "00" = veelvouden van 0,0100 (EUR/USD, GBP/USD) en van 1,00 (USD/JPY).
  "00+50" = veelvouden van 0,0050 resp. 0,50.
- *Vers niveau:* in de 24 bars ervoor heeft geen bar het niveau geraakt
  (mid-low ≤ L ≤ mid-high). Zo tellen we alleen de eerste aanraking en niet het heen-en-weer
  rond een niveau.
- *Bounce* (take-profit-hypothese): vorige close onder L, deze bar high ≥ L maar close < L,
  bij een vers niveau → **short** op de volgende open. Spiegelbeeld voor steun (long).
- *Breakout* (stop-loss-hypothese): vorige close onder L, deze close boven L, bij een vers
  niveau → **long** op de volgende open. Spiegelbeeld short.
- Liggen er meerdere niveaus in één bar, dan geldt het niveau het dichtst bij de close.
- *Exit:* stop op 1 × ATR(14) (1h, mid) vanaf de entry; target 1R of 2R; uiterlijk 16:00 NY.
- *Grid:* niveaus {00, 00+50} × variant {bounce, breakout} × target {1R, 2R} = **8
  trials**. Elke trial wordt **samen over de 3 paren** gemeten. Per paar is alleen een
  breedtecontrole, geen nieuwe trial.
- *Primair:* **F2-B: bounce, 00, 1R** en **F2-D: breakout, 00, 2R**. Bij 00 is de clustering
  van orders het sterkst; terugkeer past bij een kort target en doorbraak bij een lang
  target.
- *Nulmodel (het belangrijkste deel):* dezelfde regels op **verschoven niveaus**
  L + δ·G, met G de afstand tussen niveaus. Er zijn 200 replicaties, elk met één
  willekeurige δ (vaste seed).
  - Bij "00": δ uniform in [0,1; 0,4] ∪ [0,6; 0,9], zodat we niet op 50-niveaus belanden.
  - Bij "00+50": δ in [0,1; 0,9].
  - Dit toetst of het om **ronde** getallen gaat, en niet om bounce of breakout in het
    algemeen. Het is dezelfde aanpak als de zone-toets van ronde 1.

**F3 – London breakout** (controle)
- *Range:* hoogste high en laagste low (mid) van de bars van 00:00 t/m 06:00 Londen
  (7 bars). De range is bekend om 07:00 Londen.
- *Signaal:* de eerste bar tussen 07:00 en 10:00 Londen (open) met een close boven de
  range-high (long) of onder de range-low (short). Entry op de volgende open, max. 1 trade
  per dag per paar.
- *Stop:* {andere kant van de range, midden van de range}. *Target:* {1R, 2R, geen (alleen
  tijdsexit)}. Uiterlijk exit om 16:00 NY.
- *Grid:* 2 × 3 = **6 trials**, gemeten over de 3 paren samen.
- *Primair:* **F3: stop aan de andere kant, target 1R**. Dat is het gangbare sjabloon in de
  scripts voor particuliere handelaren.
- *Nulmodel:* op dezelfde dagen een willekeurige richting en een willekeurige entrybar
  binnen 07:00–10:00 Londen, met dezelfde stopafstand (in prijs) en dezelfde exits. 200
  replicaties.

**Totaal: 32 trials** (18 + 8 + 6). Herberekeningen voor robuustheid (kosten, subperiodes,
per paar) zijn geen trials. De 1.428 goud-trials en 25 ETF-trials horen bij andere vragen op
andere markten en tellen hier niet mee (§8). Ter informatie: na deze ronde zijn het in totaal
1.485 trials.

**Vooraf bewust niet getest** (zodat we ze later niet stilletjes toevoegen):
- *Rebalancing aan het einde van de maand* (Melvin & Prins): vraagt aandelendata (yfinance,
  alleen met toestemming) en geeft maar 12 trades per jaar.
- *Ommekeer na een abnormale dag* (Caporale & Plastun): wordt eventueel een aparte, later
  vooraf vastgelegde ronde.
- *Nieuwshandel (banenrapport e.d.):* het effect zit in de eerste 15–60 minuten en vraagt
  data van minder dan een uur.
- *Klassieke MA- en filterregels:* volgens Neely, Weller & Ulrich (2009) verdwenen begin
  jaren '90.

## 5. Baselines en nulmodellen

| Familie | Nulhypothese | Toets |
|---|---|---|
| F1 | geen voordeel: netto rendement ≤ 0 | bootstrap van het gemiddelde (§6) |
| F2 | ronde niveaus zijn niet beter dan verschoven niveaus | percentiel tussen 200 verschoven replicaties |
| F3 | het signaal is niet beter dan willekeurige entries met dezelfde exits | percentiel tussen 200 random replicaties |

- **F1-placebo (beschrijvend):** hetzelfde been (zelfde lengte) op elk ander startuur van de
  dag. Dat laat zien of het fixvenster bijzonder is of dat elk venster toevallig iets geeft.
  Met ~20 vensters is geen 95%-percentiel te maken, dus dit is geen beslisregel.
- **Bruto vs netto:** voor F1 meten we ook bruto (mid → mid). Zo zien we of het patroon er
  is (replicatie) en of de kosten het opeten (uitkomst b).

## 6. Meetwaarden

**Primair** (research R4, basiskosten = echte spread + 0,1 pip slippage per kant):
- **Gemiddeld netto rendement per trade in bp**, en het **Sharpe-ratio van de dagreeks**
  (× √252).
- **Onzekerheid:** stationaire block bootstrap op de dagreeks, gemiddelde bloklengte **20
  handelsdagen**, 2000 trekkingen. Waarom blokken? Volatiliteit clustert, dus losse dagen
  trekken geeft te smalle intervallen. Uitkomst: 95%-interval en het aandeel trekkingen > 0.

**Secundair:** bruto bp per trade; R per trade (F2/F3); trefkans; aantal trades; gemiddelde
spread betaald; maximale daling van de cumulatieve bp; resultaat per jaar; resultaat
long vs short.

**Statistisch vermogen** (vooraf, ruwe schatting):
- F1: een venster van ~6 uur op EUR/USD heeft een spreiding van ongeveer 30 bp per trade
  (dagvolatiliteit ~0,6% × √(6/24)). Over 15 jaar zijn dat ~3.700 trades per been, dus de
  standaardfout is ≈ 0,5 bp. Met 80% kans aantoonbaar (tweezijdig 5%) is een netto effect van
  **~1,4 bp per trade**.
  - De paper meldt bruto ~2,5 bp per venster. De spread kost (EUR/USD, 1 pip ≈ 0,8 bp)
    ongeveer 0,8 bp in de vroege jaren en 0,3 bp later, plus slippage.
  - Een netto effect is dus **net** aantoonbaar als het patroon even sterk is als in de
    paper. Is het half zo sterk, dan waarschijnlijk niet.
- F2/F3: bij 1.000–3.000 trades en een spreiding van ~1 R per trade is ≈ **0,05–0,09 R**
  aantoonbaar.

## 7. Robuustheid

- **Heel het grid** in een tabel, niet alleen de primaire cel.
- **Per paar** (F2, F3) en **per paar en per been** (F1).
- **Subperiodes:** 2005–2009, 2010–2014, 2015–2019.
- **Zonder het beste jaar.**
- **Kosten:** slippage 0, 0,1 en 0,3 pip per kant (0×, 1× en 3×). Daarnaast een
  beschrijvend **"retail"-scenario**: +0,5 pip per kant extra (zoals een gewone broker met
  bredere spread of commissie). Dat telt niet mee voor de status, maar laat zien of het
  resultaat buiten Dukascopy-condities overeind blijft.
- **Long en short apart** (bij F1: elk been staat al voor één richting).

## 8. Correctie voor het aantal trials (voor *validated*)

**Methode:** bootstrap-max-toets (White's Reality Check, in de vorm van Romano–Wolf), zoals
ronde 3, nu op het **Sharpe-ratio van de dagreeks** van alle 32 trials.
- In gewone taal: als geen van de 32 configuraties echt iets oplevert, geeft toeval toch bij
  één ervan een mooi resultaat. De bootstrap schat hoe groot dat grootste toevalsresultaat
  is. Pas als onze primaire configuratie in ≥ 95% van de trekkingen daarboven ligt, telt het.
- Waarom Sharpe en niet bp? De trials hebben verschillende schalen (een been van 6 uur tegen
  een breakout-trade), en Sharpe heeft geen eenheid.
- Dezelfde getrokken dagen voor alle trials (gepaard). Drempel **p < 0,05**.

## 9. Statusregels

Per **primaire configuratie** (5 stuks: F1-EU, F1-TK, F2-B, F2-D, F3).

**candidate** – alle punten in R4, bij basiskosten:
1. gemiddeld netto bp per trade > 0 **en** Sharpe van de dagreeks > 0;
2. ≥ **80%** van de bootstrap-trekkingen > 0;
3. ≥ **300** trades;
4. stabiel:
   - > 0 in ≥ **2 van de 3** subperiodes, **én**
   - > 0 zonder het beste jaar, **én**
   - F1: hetzelfde teken bruto in ≥ 2 van de 3 paren voor dezelfde combinatie (het patroon
     moet dollarbreed zijn, zoals de paper claimt);
   - F2/F3: > 0 in ≥ 2 van de 3 paren;
5. nog > 0 bij **3× slippage** (0,3 pip per kant);
6. nulmodel:
   - F2/F3: netto bp per trade boven het **95e percentiel** van het nulmodel (§4);
   - F1: geen extra eis (het nulmodel is 0, al getoetst in punt 1–2);
7. plateau (F2/F3): ≥ **de helft** van het grid van die familie is netto > 0.

**rejected:** niet aan deze punten voldaan. Bijvoorbeeld: alleen bruto positief, alleen in
één paar of periode, of niet beter dan verschoven niveaus of random entries.

**validated:** candidate, **plus**:
- H4 één keer geopend: ≥ 300 trades, netto bp per trade > 0 en > 0 bij 2× slippage;
- bij F2/F3 in H4 ook boven het 95e percentiel van het nulmodel;
- Reality Check p < 0,05 (§8, over R4).

H4 wordt alleen geopend voor candidates, per primaire configuratie één keer, via
`fx/open_holdout.py`. Daarna wordt er niets meer aan die configuratie veranderd.

**Oordeel voor het rapport** (per familie):
- **(c) voordeel na kosten:** candidate of beter.
- **(b) bruto wel, netto niet:** bruto bp > 0 met ≥ 95% van de trekkingen > 0, maar
  rejected na kosten.
- **(a) geen voordeel:** al het andere.

**Hoe zeker:** rejected → (a)/(b) met intervallen; candidate zonder H4 → "aanwijzing";
validated → "aangetoond binnen de grenzen van deze data". Ook een validated configuratie gaat
pas naar paper trading na akkoord van de gebruiker en een apart, vooraf vastgelegd
FORWARD-plan (zoals vol_squeeze_4h).

## 10. "Te mooi"-protocol

Bij > **3 bp** netto per trade (F1), > **0,3 R** per trade (F2/F3), of een Sharpe van de
dagreeks > **1,5**: eerst proberen het kapot te maken, en pas daarna rapporteren.
1. lookahead-tests (§3) en de tijdstempelcontrole (§1);
2. fill-volgorde: entry op de volgende open, stop vóór target, gat voorbij de stop;
3. kosten: kloppen bid en ask per trade? Bekijk ook 3× slippage en het retail-scenario;
4. leave-one-year-out: draagt één jaar alles?
5. dubbeltellingen: overlappende trades, max. 1 open.

Controles 1 en 3 draaien **altijd**, voor alle primaire configuraties. Wat er gecontroleerd
is, staat in het rapport.

## 11. Wijzigingslog

- 2026-10-16, **na de kwaliteitscontrole en vóór elke backtest** (er is geen rendement van
  een strategie berekend). Uitwerking van §1, geen nieuwe keuze op basis van resultaten:
  1. *Tijdstempels:* de controle op banenrapport-vrijdagen is voor alle drie de paren
     geslaagd, in research én H4 (piek in de bar van 08:00 NY).
  2. *USD/JPY 2010 valt weg* volgens de regel van §1 (> 5% ontbrekende handelsuren). Opnieuw
     per maand gedownload: Dukascopy levert voor USD/JPY 1h geen data van januari t/m
     september 2010. Dat ligt dus aan de bron, niet aan de download. Vastgelegd in
     `fx/config.yaml` (`excluded_years`).
  3. *Opschonen bij het laden* (`fx/data.py: load_pair`):
     - candles buiten de handelssessie (zo 17:00 – vr 17:00 NY) vallen weg. In 2010–2014 vult
       de feed weekenden met vlakke candles (~2.400 per jaar). Die zouden ATR en
       barvensters (versheid van niveaus, F2) vertekenen.
     - uren waarin ask < bid (voor open, high, low of close) vallen weg. Dat zijn er
       hooguit enkele tientallen per paar.
     - Gevolg: per paar ~9.600–11.500 uren minder in warm-up + research, vrijwel allemaal
       weekend. In H4 vervalt niets.
  - Details: `research/round4/data_quality.md`.
