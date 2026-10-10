**Kort: ik heb geen strategie gevonden die aantoonbaar werkt.** Geen van de vier
strategie-families haalde de vooraf vastgelegde eisen. De zone-toets op 15m bevestigt
dat support/resistance-zones niets voorspellen. Eén aanwijzing (volatiliteitscompressie op
4h) is interessant, maar vond ik achteraf en is na correctie voor alle geprobeerde
varianten niet significant. Hold-out H2 is niet geopend en dus nog schoon.

**Wat niet werkt**
- **Mean reversion op 15m/1h in rustige markten (F3):** duidelijk verlieslatend, {F3_r} R
  per trade na kosten, in elk jaar. Vóór kosten ongeveer nul: de spread eet het op.
- **S/R-zones op 15m (F5):** echte zones doen het niet beter dan willekeurige niveaus
  (bounce {z_bounce} tegen {z_bounce_null}). Hetzelfde als in ronde 1.
- **Daily trendvolgen (F1)** en **met een macrofilter (F4):** na walk-forward rond nul.
  Los bekeken zijn de meeste varianten licht positief, maar **willekeurige instappen met
  dezelfde trailing stop doen het even goed**. Het plusje zit in de exit, niet in het
  signaal. Het filter op reële rente of dollar helpt niet.

**Wat interessant maar onbewezen is**
- **Volatiliteitscompressie → breakout op 4h (F2):** alle vier de 4h-varianten liggen boven
  random met dezelfde exits, ongeveer +0,2 R per trade na kosten, nog positief bij 3×
  kosten, long en short allebei. Maar: de vooraf vastgelegde walk-forward koos ze bijna
  nooit (F2 werd rejected op te weinig trades). Het patroon zag ik pas achteraf, en na
  correctie voor {n_trials_total} geprobeerde varianten is het niet te onderscheiden van
  toeval.

**Wat onzeker is**
- Trage daily-strategieën leveren te weinig trades (9–90 per variant in 9 jaar) om iets
  zeker te zeggen.
- Alles is gemeten met vaste kosten (0,60 USD/oz per trade). Bij 15m/1h-strategieën is dat
  doorslaggevend.
- De periode 2010–2018 bevat een sterke stijging, een crash en zeven jaar zijwaarts/dalend:
  breder dan ronde 1, maar het blijft één markt.
