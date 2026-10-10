_Toegevoegd na de keuze van de gebruiker voor forward paper trading (H2 blijft dicht).
Berekend uit de research-periode; H2 zelf is niet geladen._

**Hoeveel trades had H2 opgeleverd?** De variant F2 · 4h · squeeze 20% · target 2R had in
2010–2018 gemiddeld {pw_per_year} trades per jaar (tussen {pw_min} en {pw_max}). H2 duurt
1,75 jaar, dus verwacht **~{pw_h2_n} trades** (afhankelijk van het jaar {pw_h2_lo}–{pw_h2_hi}).

**Wat kon je daarmee aantonen?** De spreiding per trade is groot (standaardafwijking
{pw_sd} R: bijna elke trade is −1 R of ongeveer +1,7 R). Met {pw_h2_n} trades:
- is het 95%-interval ongeveer **±{pw_h2_ci} R** breed;
- is het **kleinste effect dat je met 80% zekerheid zou vinden** (eenzijdige toets, 5%)
  ongeveer **+{pw_h2_mde} R per trade**;
- had een waar effect zo groot als in de research (+{pw_mean} R) maar **{pw_h2_power}%
  kans** om als positief bevestigd te worden.

H2 openen had dus vooral een grote kans op een onduidelijke uitkomst gegeven, en de
hold-out was daarna voorgoed verbruikt.

**Ter vergelijking, 100 forward-trades** (~{pw_years100} jaar): interval ±{pw_f_ci} R,
kleinste aantoonbare effect ~+{pw_f_mde} R, kans om +{pw_mean} R te bevestigen
**{pw_f_power}%**. Ook de forward-test is dus geen sluitend bewijs. Hij kan een groot effect
bevestigen of een duidelijk negatief effect stoppen, maar een klein positief effect blijft
waarschijnlijk onzeker.
