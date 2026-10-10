**Kort: in deze data voorspellen S/R-zones op goud (1h) niets wat willekeurige niveaus
niet ook doen.** Dat is een geldige uitkomst. De meting is vooraf vastgelegd en niet
achteraf aangepast.

**Wat niet werkt**
- **Zones tegenover willekeurige niveaus (vraag 1).** Bij de echte zones ging de koers in
  {bounce} van de {n_events} tests 1 ATR terug ("bounce"). Bij precies dezelfde zones,
  verschoven naar willekeurige plekken, was dat {bounce_null}. De echte zones scoren
  dus niet beter, eerder iets slechter (percentiel {bounce_pct} van het nulmodel). Een
  vaste 1:2-trade op elke test leverde gemiddeld **{r} R** op na kosten. Bij
  willekeurige niveaus was dat {r_null} R. Vóór kosten is het ongeveer 0: je wint niets
  en betaalt spread.
- **Geen enkele eigenschap maakt het verschil (vraag 2).** Timeframe, confluence,
  leeftijd, sessie en volatiliteit leveren geen groep op waar echte zones aantoonbaar
  beter zijn dan willekeurige niveaus.
- **Methode B** (KDE) doet het niet beter dan A.
- **Na een doorbraak** komt de koers vaak terug naar de zone ({q4_retest}). Dat gebeurt
  echter bijna net zo vaak bij willekeurige niveaus ({q4_retest_null}), en handelen op
  die retest levert niets op.
- **Bevestigingen (RSI, afwijzingscandle, EMA-trend)** voegen niets toe dat specifiek
  met de zone te maken heeft.

**Wat wél zichtbaar is (maar niets met zones te maken heeft)**
- **De trend van goud domineert.** Goud steeg in de research-periode +121%.
  Willekeurige long-trades kwamen na kosten op ongeveer 0 R uit, willekeurige shorts op
  ongeveer −0,18 R. Een long-strategie ziet er daardoor al snel beter uit dan hij is.
- **Een afwijzingscandle helpt een beetje** (+0,06 R). Dat helpt even goed bij
  willekeurige niveaus, dus het is een candle-effect en geen zone-effect.

**Wat onzeker is**
- Kleine effecten kan deze data niet uitsluiten: over alle tests samen tot ongeveer
  ±0,03 R per trade, in kleinere subgroepen tot ±0,1 R.
- Een paar groepen wijzen voorzichtig de goede kant op, maar hun intervallen bevatten
  nul: de *eerste* test van een zone (+0,07 R t.o.v. het nulmodel), resistance-zones
  (+0,04 R) en daily/hoge-confluence-zones (+0,02 R). Bij ruim twintig opsplitsingen
  verwacht je zulke uitschieters ook door toeval.
- Alles hier gaat over deze zone-definitie (fase 1, niet geoptimaliseerd) en over
  1h-tests. Andere definities of timeframes kunnen anders uitpakken.

**Wat dit betekent:** een S/R-strategie moet in deel B laten zien dat hij beter is dan
willekeurige instappen met dezelfde regels. Op basis van dit onderzoek verwacht ik dat
de S/R-strategieën dat **niet** halen.
