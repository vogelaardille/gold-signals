- **Eén zone-definitie.** Ik heb de fase-1-parameters gebruikt (pivotvensters,
  clustering, lookbacks), bewust zonder optimalisatie. Dat is eerlijk, maar betekent dat
  een andere definitie (bijv. alleen weekly-zones of volume-profielen) niet getest is.
- **Tests op 1h.** Een daily-zone wordt per uur getest. Wie op daily-candles handelt,
  kan andere uitkomsten zien.
- **Bid-data en vaste kosten.** De spread is als vaste kosten gemodelleerd (0,40 USD).
  In drukke momenten is de echte spread groter.
- **Het nulmodel is één keuze.** Verschuiven met 1-4 daily-ATR houdt de structuur van
  de zones intact, maar de verschoven zones worden minder vaak getest (~8.000 tegen
  ~12.400). De vergelijking gaat daarom over de kwaliteit per test, niet over het aantal.
- **Eén markt, één regime.** 2021-2025 was voor goud overwegend een sterke stijging. In
  een zijwaartse of dalende markt kan het beeld anders zijn. De hold-out (laatste 12
  maanden) is niet gebruikt.
- **"Eerste test" is een benadering**: geen test op een overlappende zone in de 120
  uur ervoor. Daardoor valt 95% van de tests onder "herhaald".
