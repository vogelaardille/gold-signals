# Ronde 4 – research-uitkomsten (R4, 2005–2019)

Automatisch gemaakt door `python -m fx.run`. Kosten: echte bid/ask-spread + 0,1 pip slippage per kant. H4 (2020–2026) is **niet** geopend.

## Primaire configuraties

| | trial | trades | netto bp/trade | bruto bp | kosten bp | Sharpe | bootstrap > 0 | 3× slip | retail | RC p | status | oordeel |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| F1-EU | `F1|EUR/USD|Europe` | 7804 | 1.32 | 2.13 | 0.81 | 1.00 | 100% | 1.00 | 0.53 | 0.00 | **candidate** | (c) |
| F1-TK | `F1|USD/JPY|Tokyo` | 7291 | 0.24 | 1.45 | 1.21 | 0.22 | 83% | -0.15 | -0.73 | 0.97 | **rejected** | (b) |
| F2-B | `F2|00|bounce|1R` | 2906 | -2.01 | -0.98 | 1.03 | -1.35 | 0% | -2.33 | -2.83 | 1.00 | **rejected** | (a) |
| F2-D | `F2|00|breakout|2R` | 2847 | -0.94 | 0.11 | 1.05 | -0.45 | 2% | -1.24 | -1.75 | 1.00 | **rejected** | (a) |
| F3 | `F3|opposite|1R` | 8334 | -1.09 | -0.17 | 0.92 | -0.65 | 0% | -1.38 | -1.83 | 1.00 | **rejected** | (a) |

## Controles per primaire configuratie (PLAN4 §9)

- **F1-EU**: subperiodes ['0.85', '1.03', '2.08'] bp; zonder beste jaar (2015) 1.17 bp; per paar {'EUR/USD': '1.32', 'GBP/USD': '0.88', 'USD/JPY': '-0.69'}; bruto per paar {'EUR/USD': '2.13', 'GBP/USD': '1.91', 'USD/JPY': '0.36'}. Niet gehaald: geen.
- **F1-TK**: subperiodes ['0.26', '0.73', '-0.17'] bp; zonder beste jaar (2008) 0.09 bp; per paar {'EUR/USD': '0.55', 'GBP/USD': '-0.40', 'USD/JPY': '0.24'}; bruto per paar {'EUR/USD': '1.41', 'GBP/USD': '0.97', 'USD/JPY': '1.45'}. Niet gehaald: 5_slippage_3x.
- **F2-B**: subperiodes ['-3.12', '-0.78', '-1.80'] bp; zonder beste jaar (2012) -2.14 bp; per paar {'EUR/USD': '-2.13', 'GBP/USD': '-2.11', 'USD/JPY': '-1.73'}; nulmodel p95 0.01 bp (echt op percentiel 0). Niet gehaald: 1_net_and_sharpe_positive, 2_boot_pos_ge_80pct, 4a_subperiods_2_of_3, 4b_without_best_year, 5_slippage_3x, 4c_net_positive_2_of_3_pairs, 6_above_null_p95, 7_plateau_half_grid.
- **F2-D**: subperiodes ['-0.28', '-2.42', '-0.47'] bp; zonder beste jaar (2008) -1.14 bp; per paar {'EUR/USD': '-0.50', 'GBP/USD': '-1.26', 'USD/JPY': '-0.96'}; nulmodel p95 -0.44 bp (echt op percentiel 48). Niet gehaald: 1_net_and_sharpe_positive, 2_boot_pos_ge_80pct, 4a_subperiods_2_of_3, 4b_without_best_year, 5_slippage_3x, 4c_net_positive_2_of_3_pairs, 6_above_null_p95, 7_plateau_half_grid.
- **F3**: subperiodes ['-2.21', '-0.69', '-0.38'] bp; zonder beste jaar (2013) -1.39 bp; per paar {'EUR/USD': '-1.51', 'GBP/USD': '-1.47', 'USD/JPY': '0.11'}; nulmodel p95 -0.38 bp (echt op percentiel 46). Niet gehaald: 1_net_and_sharpe_positive, 2_boot_pos_ge_80pct, 4a_subperiods_2_of_3, 4b_without_best_year, 5_slippage_3x, 4c_net_positive_2_of_3_pairs, 6_above_null_p95, 7_plateau_half_grid.

## Alle 32 trials

| # | trial | trades | netto bp | bruto bp | Sharpe | bootstrap > 0 | R |
|---:|---|---:|---:|---:|---:|---:|---:|
| 1 | `F1|EUR/USD|T_pre` | 3908 | -0.11 | 0.85 | -0.13 | 31% | – |
| 2 | `F1|EUR/USD|T_post` | 3907 | 1.20 | 1.97 | 1.05 | 100% | – |
| 3 | `F1|EUR/USD|E_pre` | 3903 | 1.74 | 2.47 | 0.85 | 100% | – |
| 4 | `F1|EUR/USD|L_post` | 3901 | 0.90 | 1.80 | 0.53 | 98% | – |
| 5 | `F1|EUR/USD|Tokyo` | 7815 | 0.55 | 1.41 | 0.77 | 99% | – |
| 6 | `F1|EUR/USD|Europe` | 7804 | 1.32 | 2.13 | 1.00 | 100% | – |
| 7 | `F1|GBP/USD|T_pre` | 3908 | -0.80 | 0.79 | -0.92 | 0% | – |
| 8 | `F1|GBP/USD|T_post` | 3908 | 0.00 | 1.15 | 0.00 | 49% | – |
| 9 | `F1|GBP/USD|E_pre` | 3903 | 0.98 | 1.99 | 0.42 | 96% | – |
| 10 | `F1|GBP/USD|L_post` | 3901 | 0.78 | 1.82 | 0.48 | 98% | – |
| 11 | `F1|GBP/USD|Tokyo` | 7816 | -0.40 | 0.97 | -0.56 | 2% | – |
| 12 | `F1|GBP/USD|Europe` | 7804 | 0.88 | 1.91 | 0.60 | 99% | – |
| 13 | `F1|USD/JPY|T_pre` | 3645 | -0.93 | 0.42 | -0.74 | 1% | – |
| 14 | `F1|USD/JPY|T_post` | 3646 | 1.41 | 2.48 | 0.79 | 100% | – |
| 15 | `F1|USD/JPY|E_pre` | 3639 | 0.48 | 1.47 | 0.25 | 83% | – |
| 16 | `F1|USD/JPY|L_post` | 3638 | -1.85 | -0.74 | -1.04 | 0% | – |
| 17 | `F1|USD/JPY|Tokyo` | 7291 | 0.24 | 1.45 | 0.22 | 83% | – |
| 18 | `F1|USD/JPY|Europe` | 7277 | -0.69 | 0.36 | -0.53 | 2% | – |
| 19 | `F2|00|bounce|1R` | 2906 | -2.01 | -0.98 | -1.35 | 0% | -0.13 |
| 20 | `F2|00|bounce|2R` | 2906 | -2.09 | -1.04 | -1.08 | 0% | -0.13 |
| 21 | `F2|00|breakout|1R` | 2864 | -1.14 | -0.09 | -0.70 | 0% | -0.06 |
| 22 | `F2|00|breakout|2R` | 2847 | -0.94 | 0.11 | -0.45 | 2% | -0.04 |
| 23 | `F2|00+50|bounce|1R` | 5709 | -1.67 | -0.66 | -1.44 | 0% | -0.11 |
| 24 | `F2|00+50|bounce|2R` | 5706 | -1.54 | -0.51 | -1.08 | 0% | -0.09 |
| 25 | `F2|00+50|breakout|1R` | 5437 | -1.38 | -0.36 | -1.24 | 0% | -0.07 |
| 26 | `F2|00+50|breakout|2R` | 5236 | -1.28 | -0.25 | -0.88 | 0% | -0.06 |
| 27 | `F3|opposite|1R` | 8334 | -1.09 | -0.17 | -0.65 | 0% | -0.04 |
| 28 | `F3|opposite|2R` | 8334 | -1.13 | -0.19 | -0.60 | 0% | -0.04 |
| 29 | `F3|opposite|tijd` | 8334 | -0.94 | 0.01 | -0.47 | 2% | -0.02 |
| 30 | `F3|mid|1R` | 8336 | -0.89 | -0.01 | -0.74 | 0% | -0.06 |
| 31 | `F3|mid|2R` | 8336 | -0.84 | 0.06 | -0.55 | 0% | -0.06 |
| 32 | `F3|mid|tijd` | 8336 | -0.89 | 0.03 | -0.51 | 1% | -0.05 |
