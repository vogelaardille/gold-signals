- **Lookahead**: voor elke familie een test die alle data na een moment verandert. De
  signalen tot dat moment blijven gelijk (`tests/test_round2.py`). Donchian kijkt alleen
  naar vorige candles. Macro-data pas na een vaste publicatievertraging. Een 15m-candle
  gebruikt alleen zones van het laatst gesloten uur (eigen test).
- **Fill-volgorde**: entry op de open van de volgende candle; stop vóór target in
  dezelfde candle; gat voorbij de stop = exit op de open; trailing stop pas actief na het
  slot; tijdstop op het slot (tests).
- **Kosten**: R bij 1×, 2× en 3× kosten herberekend uit winst en risico per ounce (test
  dat een stop precies −1 R is bij elke kostenfactor).
- **Dubbeltellingen**: max. 1 open positie per variant (test); voor de F2-4h-varianten
  nagerekend: 0 overlappende trades.
- **Long-bias**: long en short apart gerapporteerd; elke vergelijking met random gebruikt
  dezelfde long/short-verhouding per jaar.
- **Sessie-wijziging 2013**: de F2-4h-varianten zijn vóór én na 2013 positief
  (squeeze 20/2R: +0,27 en +0,18 R).
- **Uitschieters**: F2-4h zonder de 5 beste trades nog steeds positief (2R-varianten +0,18
  tot +0,20 R; trailing-varianten maar +0,07 tot +0,09 R).
