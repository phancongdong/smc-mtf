# SMC Revalidation 6.5-Year Specification

## Objective

Revalidate every SMC route that was live-approved when the study was frozen with the exact current
strategy code, entry gates, exits, data alignment, and realistic costs. The
study must explain why the current results differ from the legacy SMC reports
before any live routing decision is made.

## Frozen Live Routes

| Route | Analysis | Min score | Confirmation | Time exit | Trailing |
|---|---|---:|---|---:|---|
| SOLUSDT | H4/H1 | 50 | either | 72 H1 bars | A1.5R/D0.5R |
| GBPUSD | H4/H1 | 40 | either | 72 H1 bars | A1.5R/D0.5R |
| USDJPY | H4/H1 | 50 | either | 72 H1 bars | A1.5R/D0.5R |
| USDCAD | H4/H1 | 50 | either | 72 H1 bars | A1.5R/D0.5R |
| BTCUSDT | D1 single-TF | 50 | both (current default) | 24 D1 bars | none |
| ETHUSDT | D1 single-TF | 50 | both (current default) | 24 D1 bars | none |

The period is 2020-01-01 through 2026-07-13 inclusive. Assets start at their
real first available candle; no synthetic pre-listing history is allowed.

## Frozen Execution Assumptions

- Decision uses completed candles and entry occurs at the next bar open.
- Stop-first handling is used when SL and TP are touched in the same candle.
- Initial SL/TP are emitted by `SMCMultiTimeframe` without modification.
- Risk is 0.5% per independent route and only one position is open per route.
- The live 0.5 ATR minimum-stop guard remains enabled.
- Baseline crypto costs are 4 bps commission, 1 bp spread, and 1 bp slippage.
- Forex uses historical P75 spread plus 0.2 bps commission and 0.2 bps slippage.

## Validation Matrix

### Frozen Baseline

Run the exact live profile for each route and report full-sample, calendar-year,
and rolling OOS results.

### Confirmation Ablation

Run `both`, `either`, `structure`, and `poi` with every other live setting
frozen. A validation-only `none_legacy` ablation bypasses the confirmation gate
to diagnose pre-gate artifacts; it is not an accepted production mode. These
rows diagnose the entry gate and are not optimizer outputs.

### Score Sensitivity

Run min-score 40, 45, 50, 55, and 60 with the live confirmation mode and live
exits. Neighboring thresholds must preserve the sign of the edge for a route to
be considered stable.

### Cost Stress

Run the frozen live profile at 1.0x, 1.5x, and 2.0x all execution costs.

### Cache Parity

Compare cached and uncached indicator evaluation on deterministic sample bars.
Caching is allowed only when signal direction, score, SL, and TP remain equal.
Also compare full-history replay with the production rolling data windows (60
days H4 plus 7 days H1, or 730 days D1) on deterministic sample bars.

### Legacy Reproducibility

Compare the current results with the stored BTC/ETH D1 64/79-trade artifacts
and the prior one-year MTF summaries. Record differences in confirmation mode,
time exit, trailing, costs, data, and current code behavior. Where the original
Yahoo H1/H4 cache is still available, replay it separately from the verified
Dukascopy/ForexSB history to isolate data-source effects.

## Rolling Validation

Four fixed-parameter folds are used:

1. Train 2020-2022, OOS 2023.
2. Train 2021-2023, OOS 2024.
3. Train 2022-2024, OOS 2025.
4. Train 2023-2025, OOS 2026 through 2026-07-13.

Trades crossing a fold boundary are excluded from that fold. Score sensitivity
also records the train-best threshold and its following OOS result, but it does
not replace the frozen live threshold.

## Route Validation Gate

A route passes only when all of the following hold:

- At least 50 full-sample trades and 30 pooled OOS trades.
- Pooled OOS PF is at least 1.20 with positive expectancy.
- At least three of four OOS folds have PF above 1 and positive return.
- Full-sample PF remains above 1 at 1.5x costs.
- Bootstrap probability of positive OOS mean trade return is at least 95%.
- At least one adjacent score threshold also has OOS PF above 1.

Routes with fewer than 30 pooled OOS trades are `NO_SAMPLE`. Other failures are
`FAIL`; borderline profitable routes that miss one robustness gate are `WATCH`.

## Outputs

- `data/smc_revalidation_6y5/manifest.json`
- `data/smc_revalidation_6y5/baseline.csv`
- `data/smc_revalidation_6y5/folds.csv`
- `data/smc_revalidation_6y5/yearly.csv`
- `data/smc_revalidation_6y5/confirmation_modes.csv`
- `data/smc_revalidation_6y5/score_sensitivity.csv`
- `data/smc_revalidation_6y5/cost_stress.csv`
- `data/smc_revalidation_6y5/funnel.csv`
- `data/smc_revalidation_6y5/cache_parity.json`
- Per-route JSON also contains rolling live-window parity diagnostics.
- `research/SMC_REVALIDATION_6Y5_RESULTS.md`

This runner is research-only and must not modify the VPS or live settings.
