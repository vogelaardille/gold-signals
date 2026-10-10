- **R**: winst of verlies in eenheden van het risico. Bij een stop verlies je 1 R. Met
  kosten is een stop precies −1 R en is een winst iets kleiner.
- **Walk-forward**: elk jaar kiezen we de beste variant op de vier jaar ervóór (train)
  en meten we die op het jaar erna (test). Alleen de test-jaren tellen. Zo kan de keuze
  nooit op het testresultaat leunen.
- **Random entries met dezelfde exits**: we vervangen het instapmoment door een
  willekeurige candle in hetzelfde jaar, met evenveel trades en dezelfde long/short-
  verhouding, en houden stop, target en trailing exact gelijk. Wint de strategie niet van
  vrijwel al die random versies (95e percentiel), dan zit er geen waarde in het
  instapmoment. Dit vangt ook de "long-bias" van goud.
- **Win rate en break-even win rate**: hoeveel procent van de trades winst gaf, en hoeveel
  dat bij deze verhouding tussen gemiddelde winst en verlies minimaal moet zijn. Alleen
  ter informatie: een hoge win rate zegt niets als de verliezen groter zijn.
- **Sharpe** (per jaar, uit maandrendementen) en **Calmar** (jaarrendement / grootste
  daling): rendement gecorrigeerd voor risico, vergelijkbaar met buy-and-hold.
- **DSR** (deflated Sharpe): hoe zeker is het dat dit beter is dan de beste van alle
  geprobeerde varianten bij puur toeval? Lat: 0,95.
