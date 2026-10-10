We lopen alle begrippen langs aan de hand van één echte test: **{ex_time} UTC** (zie
de figuur hieronder).

- **Zone**: een prijsgebied waar de koers eerder vaak omdraaide. Deze daily-zone liep
  van **{ex_zlow} tot {ex_zhigh}** (confluence 6, 23 eerdere omkeerpunten).
- **Test**: de vorige candle sloot boven de zone en deze 1h-candle zakte erin. Een
  *support-test* dus.
- **ATR** (Average True Range): de gemiddelde beweging per uur. Hier was dat
  **{ex_atr} USD**. Alle afstanden drukken we uit in ATR, zodat een test bij een koers
  van 1.700 en een test bij 3.500 vergelijkbaar zijn.
- **Bounce**: de koers komt binnen 24 uur minstens 1 ATR boven de zone (hier:
  {ex_bounce_level}) voordat hij 0,5 ATR onder de zone sluit (*break*, hier:
  {ex_break_level}). Deze test was een **bounce**.
- **R**: winst of verlies uitgedrukt in je risico. Entry op de volgende open
  **{ex_entry}**, stop net onder de zone (**{ex_stop}**), target op 2× het risico.
  Raakt de stop, dan is het −1 R; raakt de target, dan ongeveer +2 R (minus kosten).
  **Deze trade eindigde op {ex_r} R**: de koers kwam eerst boven het bounce-niveau, viel
  daarna terug en raakte de stop. Een "bounce" is dus nog geen winnende trade. Daarom
  meten we allebei.
- **MFE/MAE**: hoe ver de koers maximaal mee- en tegenliep na de entry. Hier was dat
  {ex_mfe} en {ex_mae} ATR.
- **Kosten**: {cost} USD per ounce per trade (spread 0,40 + 2 × slippage 0,10).
- **Nulmodel**: we verschuiven álle zones een paar daily-ATR omhoog of omlaag en doen
  dezelfde meting opnieuw, 200 keer, steeds met een andere willekeurige verschuiving.
  Breedte, aantal en onderlinge afstand van de zones blijven gelijk, alleen liggen ze nu
  niet meer op echte omkeerpunten. Werken zones echt, dan moeten de echte zones beter
  scoren dan bijna alle verschoven versies.
- **Percentiel (pctl)**: hoeveel procent van de 200 verschoven versies slechter scoorde
  dan de echte zones. 50 = gewoon gemiddeld, 97,5 of hoger = duidelijk beter.
- **95%-interval** [laag; hoog]: het bereik waarbinnen de echte waarde waarschijnlijk
  ligt, gegeven hoeveel toeval er in de data zit. We berekenen het door hele weken
  opnieuw te trekken (bootstrap). Bevat het interval van een *verschil* de 0, dan kunnen
  we geen effect aantonen.
