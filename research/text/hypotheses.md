Uit de data volgt **geen** sterke S/R-hypothese. Wat ik in deel B test, en waarom:

1. **S/R-bounce (strategie a), zoals je hem opzette:** RSI, daily-trendfilter, stop
   onder de zone, target bij de volgende 4h/daily-zone, minimaal 1:2. Verwachting op
   basis van vraag 1, 2 en 6: **rejected**. Afwijkingen van jouw opzet, met reden:
   - optie *alleen eerste test* (vraag 2: +0,07 R, zwak/onzeker);
   - optie *afwijzingscandle vereist* (vraag 6: +0,06 R, maar niet zone-specifiek);
   - de RSI-drempel mag ook "uit" (vraag 6: RSI voegt niets toe);
   - de optimizer mag shorts uitzetten (vraag 5: shorts verliezen in deze trend), maar
     dan moet de strategie bij validatie beter zijn dan willekeurige longs.
2. **Breakout/retest (strategie b):** verwachting **rejected** (vraag 4).
3. **EMA-trend pullback (benchmark c):** test of een simpele trendregel zonder zones
   het beter doet. Vraag 5 suggereert dat de trend het enige echte signaal is.
4. **Baselines:** willekeurige entries met dezelfde stop/target-regels, en buy-and-hold.

**Concrete hypotheses (toetsbaar in deel B):**
- H-B1: "sr_bounce haalt na kosten geen positieve verwachting in de walk-forward."
- H-B2: "Als sr_bounce positief is, dan alleen long, en niet beter dan willekeurige
  longs (excess ≤ 0)."
- H-B3: "Geen enkele zone-strategie verslaat de EMA-benchmark."
- H-B4: "Buy-and-hold verslaat alle strategieën in rendement over de testperiode."

Elke extra optie vergroot het aantal geteste varianten. Dat telt mee in de deflated
Sharpe ratio, zodat ruimere opties niet vanzelf een mooier resultaat geven.
