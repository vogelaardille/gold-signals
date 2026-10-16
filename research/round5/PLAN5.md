# Ronde 5 – onderzoeksplan: intraday momentum in valuta

Vastgelegd **voordat** er één backtest van ronde 5 is gedraaid. De git-commit van dit
bestand is het bewijs. Wijzigingen achteraf staan in §11.

Parameters komen in `fx/config.yaml` (sectie `round5`), code in `fx/`, uitvoer in
`research/round5/`. Alleen onderzoek: niets naar de live workflow, Telegram of paper trading
zonder akkoord van de gebruiker. Uitvoering, kosten en data zijn **dezelfde als in ronde 4**
(PLAN4 §1 en §3). De engine van ronde 4 wordt hergebruikt en niet gewijzigd.

## 0. Vraag, aanleiding en wat al gezien is

**Vraag.** Bestaat er in valuta *intraday momentum*: voorspelt de beweging eerder op de dag
de richting later op de dag? En levert dat een voordeel op **na echte kosten**, als daytrade?

**Aanleiding.** De gebruiker vroeg naar strategieën die de afgelopen ~5 jaar het best werkten.
Intraday momentum heeft daarvan de sterkste recente onderbouwing:
- Gao, Han, Li & Zhou (JFE 2018): het rendement van het eerste halfuur voorspelt het laatste
  halfuur (SPY, 1993–2013).
- Baltussen, Da, Lammers & Martens (JFE 2021): hetzelfde in meer dan 60 futures, **ook
  valuta**, 1974–2020. Hun verklaring: partijen die opties verkocht hebben (short gamma),
  moeten indekken door mee te handelen met de beweging, en dat versterkt die.
- Zarattini, Aziz & Barbon (2024): de "noise area"-breakout op SPY (2007–2024), Sharpe 1,33
  na kosten volgens de auteurs.

**Waarom dit een probleem geeft voor de toetsing.** De strategie is gekozen *omdat* hij
recent goed werkte (2020–2024, aandelen). Data van na 2020 is daardoor geen onafhankelijke
toets meer. Bovendien is voor EUR/USD 2020–2026 al in ronde 4 bekeken (H4, F1-EU). Daarom:
- research op dezelfde jaren als ronde 4 (2005–2019): vóór de strategie bekend werd;
- bevestiging op **drie andere valutaparen** (AUD/USD, USD/CAD, USD/CHF), in dezelfde jaren,
  die in geen enkele ronde intraday bekeken zijn (§2);
- 2020–2026 telt alleen als beschrijving ("besmet"), nooit voor de status.

**Al gezien vóór dit plan** (eerlijk vermeld):
- R4-data (EUR/USD, GBP/USD, USD/JPY, 2005–2019) is in ronde 4 gebruikt voor andere
  hypotheses. De F1-placebo liet de **onvoorwaardelijke** bruto drift per tijdvenster zien
  (bijvoorbeeld een positieve drift in EUR/USD-vensters rond 11:00–17:00 NY). Over
  *voorwaardelijke* momentum (richting afhankelijk van eerder die dag) is niets bekeken. Het
  nulmodel van G1 (tekens husselen) haalt de onvoorwaardelijke drift er juist uit.
- Voor AUD/USD, USD/CAD, USD/CHF is alleen gekeken of Dukascopy data heeft (vanaf medio
  2003, bid en ask). Geen koersen en geen rendementen.

**Verwachting vooraf:** klein of afwezig na kosten. De onafhankelijke replicatie van de
verwante opening-range-breakout op indices vond netto nul. Voor spot-valuta bestaat geen
onafhankelijke test. "Het werkt niet" is een geldige uitkomst.

## 1. Data

- Zoals PLAN4 §1: Dukascopy 1h, bid én ask, signalen op mid, fills op bid/ask, opschonen bij
  het laden (sessie, ask ≥ bid, uitgesloten paar-jaren).
- **Research-paren:** EUR/USD, GBP/USD, USD/JPY (cache van ronde 4).
- **Bevestigingsparen:** AUD/USD, USD/CAD, USD/CHF. Pipgrootte 0,0001; AUD/USD noteert in
  USD, USD/CAD en USD/CHF hebben USD als basis (rendement omgerekend zoals bij USD/JPY).
  - Downloaden via `fx/data.py` naar dezelfde cache.
  - Vóór opening alleen beschikbaarheid: ontbrekende uren per jaar, de tijdstempelcontrole op
    banenrapport-vrijdagen, ask < bid. **Geen** spreads, geen rendementen. Dezelfde
    uitsluitingsregel (> 5% ontbrekende handelsuren → paar-jaar valt weg).
- Alleen 1h (kleiner pas vanaf 2012).

## 2. Data-indeling

| Blok | Paren | Periode | Gebruik | Keer geopend |
|---|---|---|---|---|
| Warm-up | alle | 2003-08 – 2004-12 | alleen terugkijken (σ van G2) | – |
| **Research R5** | EUR/USD, GBP/USD, USD/JPY | 2005-01 – 2019-12 | ontwerp, status | – |
| **Bevestiging C5** | AUD/USD, USD/CAD, USD/CHF | 2005-01 – 2019-12 | max. 1× per primaire configuratie, alleen als *candidate* | **0** |
| Besmet K5 | alle 6 | 2020-01 – 2026-10 | alleen beschrijvend, ná vastleggen van status en C5 | – |
| Forward | – | vanaf 2026-10 | eventueel paper trading, alleen met akkoord + FORWARD-plan | – |

- **Waarom andere paren als bevestiging?** Een tijdsblok na 2020 is niet onafhankelijk (§0).
  Andere paren in dezelfde jaren zijn dat wel, al hangen ze samen via de dollar. Dat is een
  zwakkere toets dan een echte toekomstperiode. Daarom blijft forward paper trading de
  laatste stap voor alles wat hier overeind blijft.
- C5 is alleen te openen via een bewaker (log `research/round5/holdout_log.json`).
  Research-code laadt alleen de research-paren, met `until = 2020-01-01`.

## 3. Uitvoering

Identiek aan PLAN4 §3:
- signaal op de close van een bar, entry op de open van de volgende bar;
- fills op ask (kopen) en bid (verkopen), plus 0,1 pip slippage per kant;
- nooit een positie over 17:00 NY: uiterlijk exit op de open van de 16:00 NY-bar; geen nieuwe
  entries tussen 14:00 en 18:00 NY (behalve vaste vensters van G1);
- max. 1 open trade per configuratie per paar;
- rendement in bp van de nominale waarde, dagreeks en bootstrap zoals PLAN4 §6.

## 4. Families (2) en grid

**Dag** = valutadag van 17:00 tot 17:00 NY. **Richting** = richting van de koers van het paar
(long = koers stijgt).

**G1 – Intraday momentum (Gao e.a. 2018; Baltussen e.a. 2021)**
- *Signaal:* het rendement van de dag tot nu toe: close van de bar vóór S gedeeld door de
  mid-open van de 17:00 NY-bar (begin van de dag), min 1.
  - Positief → long op de open van bar S; negatief → short.
- *Exit:* open van bar X. Geen stop, geen target.
- *Vensters (S → X, NY-tijd):* {12:00 → 16:00, 14:00 → 16:00}. Het tweede venster ligt het
  dichtst bij "het laatste deel van de dag" uit de papers. Het eerste begint na de Londense
  fix en het einde van de Londense sessie.
- Een dag valt weg als de 17:00-bar, bar S−1, S of X ontbreekt.
- *Trials:* 2, elk gemeten over de 3 research-paren samen. *Primair:* **G1: 12:00 → 16:00**
  (meer trades per uur venster en minder last van de dunne markt laat op de dag).
- *Nulmodel:* per paar de reeks tekens (long/short) over de dagen willekeurig husselen, met
  dezelfde vensters (200 replicaties, vaste seed). Zo blijven het aandeel long en de
  blootstelling aan de onvoorwaardelijke drift (§0) gelijk. Alleen het verband met het
  signaal verdwijnt.

**G2 – Noise-area breakout (Zarattini, Aziz & Barbon 2024)**
- *Anker A:* de open van een vaste bar, O = mid-open van die bar:
  {17:00 NY (begin valutadag), 08:00 Londen (opening Londen)}.
- *Bandbreedte:* voor elke bar k uur na het anker: σ_k = het gemiddelde van
  |close_k / O − 1| over de **14 voorgaande** dagen (zonder vandaag) op hetzelfde uur na het
  anker. Band: O × (1 ± m × σ_k).
- *Entry:* close van bar k boven de bovenband → long op de volgende open; onder de
  onderband → short. Alleen als er geen positie open is en het entry-uur is toegestaan (§3).
- *Exit:* de eerste latere bar waarvan de close weer binnen de band ligt (long: close ≤
  bovenband van die bar) → exit op de volgende open. Anders de geforceerde exit om 16:00 NY.
  Na een exit mag dezelfde dag een nieuwe entry (zoals in de paper).
- Een dag zonder ankerbar valt weg. σ_k vraagt minimaal 10 van de 14 dagen met die bar.
- *Grid:* anker {17:00 NY, 08:00 Londen} × m ∈ {1,0; 1,5} = **4 trials**, gemeten over de 3
  research-paren samen. *Primair:* **G2: anker 08:00 Londen, m = 1,0**. De paper gebruikt
  m = 1 en ankert op de opening van de belangrijkste sessie; voor valuta is dat Londen.
- De paper stuurt de positiegrootte op volatiliteit. Wij meten bp per trade bij een vaste
  nominale waarde, zoals ronde 4.
- *Nulmodel:* dezelfde entrymomenten en dezelfde houdduur (aantal bars), maar een
  willekeurige richting (200 replicaties). Zo toetsen we of de **richting** van de doorbraak
  iets toevoegt, bij dezelfde kosten en hetzelfde moment.

**Totaal: 6 trials.** Robuustheidsberekeningen zijn geen trials. Ter informatie: alle rondes
samen komen op 1.485 + 6 = 1.491.

## 5. Meetwaarden

Zoals PLAN4 §6: primair het gemiddelde netto rendement per trade in bp en de Sharpe van de
dagreeks (× √252), met een stationaire block bootstrap (blokken van gemiddeld 20 dagen, 2000
trekkingen). Secundair: bruto bp, kosten, trefkans, per paar, per jaar, long/short.

**Statistisch vermogen** (ruwe schatting vooraf):
- G1 12→16: ~24 bp spreiding per trade (4 uur), ~11.000 trades → standaardfout ≈ 0,23 bp,
  aantoonbaar vanaf **~0,65 bp** netto. De kosten zijn ~0,8–1,2 bp per trade, dus bruto is
  ≳ 1,5–2 bp per trade nodig.
- G2: hangt af van het aantal doorbraken. Bij ~5.000–10.000 trades vergelijkbaar.

## 6. Robuustheid

Heel het grid; per paar; subperiodes 2005–2009, 2010–2014, 2015–2019; zonder het beste
jaar; slippage 0×, 1× en 3×; een beschrijvend retail-scenario (+0,5 pip per kant); long en
short apart.

## 7. Correctie voor het aantal trials

Reality Check (bootstrap-max) op de Sharpe van de dagreeks over de **6** trials, zoals PLAN4
§8. Drempel p < 0,05.

## 8. Statusregels

Per **primaire configuratie** (G1 en G2).

**candidate** (in R5, basiskosten) – alle punten:
1. netto bp per trade > 0 **en** Sharpe > 0;
2. ≥ **80%** van de bootstrap-trekkingen > 0;
3. ≥ **300** trades;
4. > 0 in ≥ **2 van 3** subperiodes, > 0 zonder het beste jaar, > 0 in ≥ **2 van 3** paren;
5. > 0 bij **3× slippage**;
6. boven het **95e percentiel** van het nulmodel (§4);
7. plateau: ≥ de helft van het grid van die familie netto > 0.

**validated:** candidate, **plus** C5 één keer geopend, met daarin:
- ≥ 300 trades, netto > 0 en ≥ **80%** van de bootstrap-trekkingen > 0;
- > 0 bij 2× slippage;
- > 0 in ≥ 2 van de 3 bevestigingsparen;
- boven het 95e percentiel van het nulmodel;
- en de Reality Check p < 0,05 in R5.

*Les uit ronde 4:* bij H4 was "puntschatting > 0" genoeg. F1-EU werd daardoor formeel
validated, terwijl het H4-resultaat statistisch niet van nul te onderscheiden was. Daarom
eist C5 hier ook ≥ 80% positieve bootstrap-trekkingen.

Ook validated krijgt het label **"gekozen op recente bekendheid; alleen bevestigd op andere
paren in 2005–2019"**. Het gaat pas naar paper trading na akkoord en een apart FORWARD-plan.

**Oordeel:** (c) voordeel na kosten = candidate of beter; (b) bruto wel (≥ 95% van de
trekkingen > 0), netto niet; (a) geen voordeel.

## 9. Besmet blok K5 (beschrijvend)

Pas nadat de status en C5 gecommit zijn: de primaire configuraties op alle 6 paren in
2020-01 – 2026-10, met dezelfde metingen. Dit verandert niets aan de status. Het laat alleen
zien of het effect er recent ook was, met de kanttekening dat de keuze voor deze strategie
juist op recente prestaties berustte.

## 10. "Te mooi"-protocol

Zoals PLAN4 §10, met drempels > 3 bp netto per trade of een Sharpe van de dagreeks > 1,5.
De lookahead-tests (signaal gebruikt alleen bars t/m S−1; σ_k alleen eerdere dagen) en de
kostencontrole per trade draaien altijd.

## 11. Wijzigingslog

(leeg)
