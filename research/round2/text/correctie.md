In totaal zijn **{n_trials_total} varianten** geprobeerd: 671 in ronde 1, 1 opening van
de verbrande hold-out (H1) en {n_trials_r2} in ronde 2 (elke variant in elk train-venster
telt als één). Hoe meer je probeert, hoe beter de beste er bij toeval uitziet. De
deflated Sharpe ratio schat hoe goed die beste-door-toeval zou zijn en vraagt of de
strategie daar duidelijk boven zit. Met zoveel varianten en de grote spreiding tussen
trials (veel trials hebben maar 8–50 trades) ligt die lat hoog: per trade een Sharpe
van ~0,9. Geen enkele familie of variant komt daar in de buurt (DSR 0,00), ook niet in
de mildere variant die de meetruis eruit haalt.

In gewone taal: zelfs het beste resultaat van ronde 2 is niet beter dan wat je mag
verwachten als je ~1.400 keer iets willekeurigs probeert. Dat betekent niet dat het
zeker toeval is, maar wel dat deze data het niet kunnen bewijzen.

**Verbrande hold-out.** De laatste 12 maanden (H1) zijn in ronde 1 één keer geopend
door ema_pullback. Ze tellen als één extra trial en worden in ronde 2 niet gebruikt. Het
blok 2020-10 t/m 2025-09 (K) is in ronde 1 uitgebreid bekeken en is daarom ook niet
gebruikt. De nieuwe hold-out H2 (2019-01 t/m 2020-09) is **niet geopend**, omdat geen
enkele strategie candidate werd.
