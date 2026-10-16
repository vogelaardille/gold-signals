# Ronde 5 – research-uitkomsten (R5: EUR/USD, GBP/USD, USD/JPY, 2005–2019)

Automatisch gemaakt door `python -m fx.run5`. Kosten: echte bid/ask-spread + 0,1 pip slippage per kant. Bevestigingsparen (C5) en 2020–2026 zijn **niet** geladen.

## Primaire configuraties

| | trial | trades | netto bp/trade | bruto bp | kosten bp | Sharpe | bootstrap > 0 | 3× slip | retail | nulmodel p95 | RC p | status | oordeel |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| G1 | `G1|12-16NY` | 11409 | -1.18 | -0.12 | 1.05 | -1.18 | 0% | -1.49 | -1.97 | -0.66 | 1.00 | **rejected** | (a) |
| G2 | `G2|london08|m1.0` | 14651 | -0.35 | 0.56 | 0.91 | -0.34 | 8% | -0.67 | -1.15 | -0.46 | 1.00 | **rejected** | (b) |

## Controles (PLAN5 §8)

- **G1**: subperiodes ['-1.66', '-1.12', '-0.74'] bp; zonder beste jaar (2018) -1.30 bp; per paar {'EUR/USD': '-0.86', 'GBP/USD': '-2.02', 'USD/JPY': '-0.61'}; long/short -0.10/-2.21 bp; echt op percentiel 26 van het nulmodel. Niet gehaald: 1_net_and_sharpe_positive, 2_boot_pos_ge_80pct, 4a_subperiods_2_of_3, 4b_without_best_year, 4c_net_positive_2_of_3_pairs, 5_slippage_3x, 6_above_null_p95, 7_plateau_half_grid.
- **G2**: subperiodes ['-0.10', '-0.76', '-0.22'] bp; zonder beste jaar (2007) -0.46 bp; per paar {'EUR/USD': '0.40', 'GBP/USD': '-0.44', 'USD/JPY': '-1.06'}; long/short -0.34/-0.36 bp; echt op percentiel 100 van het nulmodel. Niet gehaald: 1_net_and_sharpe_positive, 2_boot_pos_ge_80pct, 4a_subperiods_2_of_3, 4b_without_best_year, 4c_net_positive_2_of_3_pairs, 5_slippage_3x, 7_plateau_half_grid.

## Alle 6 trials

| # | trial | trades | netto bp | bruto bp | Sharpe | bootstrap > 0 |
|---:|---|---:|---:|---:|---:|---:|
| 1 | `G1|12-16NY` | 11409 | -1.18 | -0.12 | -1.18 | 0% |
| 2 | `G1|14-16NY` | 11417 | -1.19 | -0.12 | -1.68 | 0% |
| 3 | `G2|ny17|m1.0` | 25001 | -1.29 | -0.26 | -1.72 | 0% |
| 4 | `G2|ny17|m1.5` | 16770 | -1.30 | -0.28 | -1.54 | 0% |
| 5 | `G2|london08|m1.0` | 14651 | -0.35 | 0.56 | -0.34 | 8% |
| 6 | `G2|london08|m1.5` | 9780 | -0.07 | 0.84 | -0.06 | 40% |
