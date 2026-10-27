# SMC Revalidation - Current Live Code, 6.5 Years

Period: `2020-01-01T00:00:00+00:00` to `2026-07-14T00:00:00+00:00` (end exclusive).
This study validates the six SMC routes that were live-approved when the experiment was frozen. It does not itself change the VPS or live settings.

## Critical Configuration Mismatch

The stored SMC reports do not represent the current live profile:

| Component | Stored MTF backtest | Current live MTF |
|---|---|---|
| Confirmation | legacy `require_poi_confirmation=True`; exact pre-gate semantics are no longer present | `either` |
| Time exit | 24 H1 bars | 72 H1 bars |
| Trailing | none | A1.5R/D0.5R |
| Costs | fixed 1.0/0.4/0.5 bps slippage/commission/spread | realistic asset-class costs and P75 FX spread |
| Test period | one year for MTF | 6.5 years |

BTC/ETH D1 artifacts were generated before the current structure plus POI gate was added. Their 64/79 trades are therefore historical artifacts, not reproducible current-code results.

## Frozen Live Baseline

| Route | Mode | Score | Signals | Full trades | Full PF | Sharpe | DD% | OOS trades | OOS PF | Positive folds | Bootstrap P(mean>0) | Verdict |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|:---:|
| SMC_D1:BTCUSDT | both | 50 | 7 | 7 | 0.16 | -5.02 | 2.12 | 4 | 0.20 | 1/4 | 4.5% | NO_SAMPLE |
| SMC_D1:ETHUSDT | both | 50 | 8 | 7 | 0.27 | -5.09 | 1.68 | 3 | 0.29 | 1/4 | 15.1% | NO_SAMPLE |
| SMC_MTF_H1:GBPUSD | either | 40 | 4249 | 507 | 0.30 | -22.35 | 1.98 | 280 | 0.09 | 0/4 | 0.0% | FAIL |
| SMC_MTF_H1:SOLUSDT | either | 50 | 1269 | 442 | 1.30 | 0.39 | 3.99 | 268 | 1.23 | 3/4 | 91.9% | WATCH |
| SMC_MTF_H1:USDCAD | either | 50 | 1186 | 360 | 0.12 | -40.11 | 1.56 | 185 | 0.04 | 0/4 | 0.0% | FAIL |
| SMC_MTF_H1:USDJPY | either | 50 | 1231 | 361 | 0.79 | -1.32 | 16.81 | 193 | 0.68 | 1/4 | 1.2% | FAIL |

## Grouped SMC Result

The pooled rows combine independent route trade returns; they are not a shared-capital portfolio replay.

| Group | Full trades | Full PF | Full return sum% | OOS trades | OOS PF | OOS return sum% |
|---|---:|---:|---:|---:|---:|---:|
| SMC MTF H4/H1 | 1670 | 1.03 | 5.10 | 926 | 0.94 | -5.41 |
| SMC D1 | 14 | 0.21 | -3.82 | 7 | 0.23 | -1.79 |
| All live SMC | 1684 | 1.01 | 1.28 | 933 | 0.93 | -7.20 |

## Fixed-Parameter OOS Folds

| Route | Fold | OOS trades | OOS PF | OOS return sum% |
|---|:---:|---:|---:|---:|
| SMC_D1:BTCUSDT | F1 | 0 | 0.00 | 0.00 |
| SMC_D1:BTCUSDT | F2 | 1 | 99.00 | 0.30 |
| SMC_D1:BTCUSDT | F3 | 3 | 0.00 | -1.54 |
| SMC_D1:BTCUSDT | F4 | 0 | 0.00 | 0.00 |
| SMC_D1:ETHUSDT | F1 | 1 | 0.00 | -0.28 |
| SMC_D1:ETHUSDT | F2 | 1 | 0.00 | -0.50 |
| SMC_D1:ETHUSDT | F3 | 1 | 99.00 | 0.23 |
| SMC_D1:ETHUSDT | F4 | 0 | 0.00 | 0.00 |
| SMC_MTF_H1:GBPUSD | F1 | 75 | 0.10 | -0.34 |
| SMC_MTF_H1:GBPUSD | F2 | 82 | 0.06 | -0.34 |
| SMC_MTF_H1:GBPUSD | F3 | 81 | 0.14 | -0.30 |
| SMC_MTF_H1:GBPUSD | F4 | 42 | 0.07 | -0.19 |
| SMC_MTF_H1:SOLUSDT | F1 | 71 | 1.31 | 4.13 |
| SMC_MTF_H1:SOLUSDT | F2 | 75 | 1.55 | 6.79 |
| SMC_MTF_H1:SOLUSDT | F3 | 83 | 1.03 | 0.51 |
| SMC_MTF_H1:SOLUSDT | F4 | 39 | 0.96 | -0.38 |
| SMC_MTF_H1:USDCAD | F1 | 53 | 0.08 | -0.19 |
| SMC_MTF_H1:USDCAD | F2 | 59 | 0.02 | -0.26 |
| SMC_MTF_H1:USDCAD | F3 | 47 | 0.03 | -0.25 |
| SMC_MTF_H1:USDCAD | F4 | 26 | 0.05 | -0.12 |
| SMC_MTF_H1:USDJPY | F1 | 54 | 0.43 | -8.64 |
| SMC_MTF_H1:USDJPY | F2 | 57 | 1.09 | 1.02 |
| SMC_MTF_H1:USDJPY | F3 | 52 | 0.73 | -3.33 |
| SMC_MTF_H1:USDJPY | F4 | 30 | 0.49 | -3.51 |

## Confirmation-Mode Ablation

These rows are diagnostics only. `none_legacy` bypasses the current confirmation gate solely to identify pre-gate behavior.

| Route | Mode | Signals | Full trades | Full PF | OOS trades | OOS PF | Positive folds |
|---|---|---:|---:|---:|---:|---:|---:|
| SMC_D1:BTCUSDT | both | 7 | 7 | 0.16 | 4 | 0.20 | 1/4 |
| SMC_D1:BTCUSDT | either | 81 | 52 | 1.43 | 26 | 1.52 | 3/4 |
| SMC_D1:BTCUSDT | structure | 45 | 36 | 1.67 | 17 | 1.30 | 2/4 |
| SMC_D1:BTCUSDT | poi | 43 | 34 | 1.12 | 20 | 1.80 | 3/4 |
| SMC_D1:BTCUSDT | none_legacy | 84 | 53 | 1.36 | 27 | 1.40 | 3/4 |
| SMC_D1:ETHUSDT | both | 8 | 7 | 0.27 | 3 | 0.29 | 1/4 |
| SMC_D1:ETHUSDT | either | 77 | 48 | 1.16 | 22 | 1.37 | 3/4 |
| SMC_D1:ETHUSDT | structure | 45 | 34 | 1.40 | 14 | 1.53 | 3/4 |
| SMC_D1:ETHUSDT | poi | 40 | 31 | 0.88 | 15 | 1.49 | 2/4 |
| SMC_D1:ETHUSDT | none_legacy | 83 | 51 | 1.29 | 25 | 1.62 | 3/4 |
| SMC_MTF_H1:GBPUSD | both | 376 | 85 | 0.36 | 49 | 0.03 | 0/4 |
| SMC_MTF_H1:GBPUSD | either | 4249 | 507 | 0.30 | 280 | 0.09 | 0/4 |
| SMC_MTF_H1:GBPUSD | structure | 2625 | 443 | 0.29 | 247 | 0.09 | 0/4 |
| SMC_MTF_H1:GBPUSD | poi | 2000 | 339 | 0.40 | 188 | 0.11 | 0/4 |
| SMC_MTF_H1:GBPUSD | none_legacy | 5499 | 610 | 0.25 | 335 | 0.08 | 0/4 |
| SMC_MTF_H1:SOLUSDT | both | 241 | 77 | 0.78 | 42 | 0.72 | 1/4 |
| SMC_MTF_H1:SOLUSDT | either | 1269 | 442 | 1.30 | 268 | 1.23 | 3/4 |
| SMC_MTF_H1:SOLUSDT | structure | 631 | 319 | 1.11 | 205 | 1.05 | 2/4 |
| SMC_MTF_H1:SOLUSDT | poi | 879 | 287 | 1.24 | 165 | 1.16 | 2/4 |
| SMC_MTF_H1:SOLUSDT | none_legacy | 1402 | 478 | 1.31 | 292 | 1.19 | 3/4 |
| SMC_MTF_H1:USDCAD | both | 249 | 66 | 0.44 | 30 | 0.27 | 0/4 |
| SMC_MTF_H1:USDCAD | either | 1186 | 360 | 0.12 | 185 | 0.04 | 0/4 |
| SMC_MTF_H1:USDCAD | structure | 625 | 272 | 0.15 | 138 | 0.09 | 0/4 |
| SMC_MTF_H1:USDCAD | poi | 810 | 241 | 0.13 | 124 | 0.03 | 0/4 |
| SMC_MTF_H1:USDCAD | none_legacy | 1325 | 394 | 0.11 | 207 | 0.03 | 0/4 |
| SMC_MTF_H1:USDJPY | both | 228 | 59 | 0.66 | 30 | 0.77 | 1/4 |
| SMC_MTF_H1:USDJPY | either | 1231 | 361 | 0.79 | 193 | 0.68 | 1/4 |
| SMC_MTF_H1:USDJPY | structure | 570 | 248 | 0.80 | 128 | 0.81 | 2/4 |
| SMC_MTF_H1:USDJPY | poi | 889 | 258 | 0.73 | 145 | 0.65 | 1/4 |
| SMC_MTF_H1:USDJPY | none_legacy | 1328 | 390 | 0.76 | 212 | 0.67 | 0/4 |

## Score Sensitivity

| Route | Score | Signals | Full trades | Full PF | OOS trades | OOS PF | Positive folds |
|---|---:|---:|---:|---:|---:|---:|---:|
| SMC_D1:BTCUSDT | 40 | 12 | 12 | 0.35 | 4 | 0.20 | 1/4 |
| SMC_D1:BTCUSDT | 45 | 8 | 8 | 0.13 | 4 | 0.20 | 1/4 |
| SMC_D1:BTCUSDT | 50 (live) | 7 | 7 | 0.16 | 4 | 0.20 | 1/4 |
| SMC_D1:BTCUSDT | 55 | 7 | 7 | 0.16 | 4 | 0.20 | 1/4 |
| SMC_D1:BTCUSDT | 60 | 6 | 6 | 0.20 | 3 | 0.29 | 1/4 |
| SMC_D1:ETHUSDT | 40 | 13 | 11 | 0.39 | 5 | 0.37 | 1/4 |
| SMC_D1:ETHUSDT | 45 | 10 | 9 | 0.18 | 4 | 0.18 | 1/4 |
| SMC_D1:ETHUSDT | 50 (live) | 8 | 7 | 0.27 | 3 | 0.29 | 1/4 |
| SMC_D1:ETHUSDT | 55 | 7 | 6 | 0.10 | 3 | 0.29 | 1/4 |
| SMC_D1:ETHUSDT | 60 | 4 | 3 | 0.00 | 1 | 0.00 | 0/4 |
| SMC_MTF_H1:GBPUSD | 40 (live) | 4249 | 507 | 0.30 | 280 | 0.09 | 0/4 |
| SMC_MTF_H1:GBPUSD | 45 | 1962 | 400 | 0.37 | 224 | 0.15 | 0/4 |
| SMC_MTF_H1:GBPUSD | 50 | 1239 | 361 | 0.34 | 199 | 0.14 | 0/4 |
| SMC_MTF_H1:GBPUSD | 55 | 799 | 279 | 0.37 | 159 | 0.15 | 0/4 |
| SMC_MTF_H1:GBPUSD | 60 | 318 | 129 | 0.17 | 65 | 0.12 | 0/4 |
| SMC_MTF_H1:SOLUSDT | 40 | 4969 | 721 | 1.20 | 436 | 1.17 | 4/4 |
| SMC_MTF_H1:SOLUSDT | 45 | 1924 | 491 | 1.31 | 298 | 1.22 | 4/4 |
| SMC_MTF_H1:SOLUSDT | 50 (live) | 1269 | 442 | 1.30 | 268 | 1.23 | 3/4 |
| SMC_MTF_H1:SOLUSDT | 55 | 829 | 330 | 1.18 | 205 | 1.04 | 2/4 |
| SMC_MTF_H1:SOLUSDT | 60 | 287 | 137 | 1.40 | 81 | 1.44 | 3/4 |
| SMC_MTF_H1:USDCAD | 40 | 4134 | 530 | 0.09 | 278 | 0.06 | 0/4 |
| SMC_MTF_H1:USDCAD | 45 | 1838 | 404 | 0.12 | 210 | 0.04 | 0/4 |
| SMC_MTF_H1:USDCAD | 50 (live) | 1186 | 360 | 0.12 | 185 | 0.04 | 0/4 |
| SMC_MTF_H1:USDCAD | 55 | 751 | 276 | 0.12 | 146 | 0.04 | 0/4 |
| SMC_MTF_H1:USDCAD | 60 | 267 | 121 | 0.19 | 60 | 0.04 | 0/4 |
| SMC_MTF_H1:USDJPY | 40 | 4399 | 528 | 0.94 | 282 | 0.89 | 1/4 |
| SMC_MTF_H1:USDJPY | 45 | 2010 | 412 | 0.88 | 216 | 0.81 | 1/4 |
| SMC_MTF_H1:USDJPY | 50 (live) | 1231 | 361 | 0.79 | 193 | 0.68 | 1/4 |
| SMC_MTF_H1:USDJPY | 55 | 823 | 271 | 0.75 | 148 | 0.71 | 1/4 |
| SMC_MTF_H1:USDJPY | 60 | 341 | 142 | 0.75 | 78 | 0.70 | 1/4 |

## Cost Stress

| Route | Costs | Full PF | OOS PF |
|---|---:|---:|---:|
| SMC_D1:BTCUSDT | 1.0x | 0.16 | 0.20 |
| SMC_D1:BTCUSDT | 1.5x | 0.16 | 0.19 |
| SMC_D1:BTCUSDT | 2.0x | 0.15 | 0.19 |
| SMC_D1:ETHUSDT | 1.0x | 0.27 | 0.29 |
| SMC_D1:ETHUSDT | 1.5x | 0.26 | 0.29 |
| SMC_D1:ETHUSDT | 2.0x | 0.26 | 0.28 |
| SMC_MTF_H1:GBPUSD | 1.0x | 0.30 | 0.09 |
| SMC_MTF_H1:GBPUSD | 1.5x | 0.29 | 0.09 |
| SMC_MTF_H1:GBPUSD | 2.0x | 0.29 | 0.09 |
| SMC_MTF_H1:SOLUSDT | 1.0x | 1.30 | 1.23 |
| SMC_MTF_H1:SOLUSDT | 1.5x | 1.27 | 1.19 |
| SMC_MTF_H1:SOLUSDT | 2.0x | 1.25 | 1.16 |
| SMC_MTF_H1:USDCAD | 1.0x | 0.12 | 0.04 |
| SMC_MTF_H1:USDCAD | 1.5x | 0.12 | 0.04 |
| SMC_MTF_H1:USDCAD | 2.0x | 0.11 | 0.04 |
| SMC_MTF_H1:USDJPY | 1.0x | 0.79 | 0.68 |
| SMC_MTF_H1:USDJPY | 1.5x | 0.78 | 0.67 |
| SMC_MTF_H1:USDJPY | 2.0x | 0.76 | 0.65 |

## Signal Funnel

| Route | Evaluated bars | Raw scored bars | Confirmation pass | Live-score eligible | Main blocks |
|---|---:|---:|---:|---:|---|
| SMC_D1:BTCUSDT | 2284 | 2284 | 12 | 7 | NO_POI_REJECTION=2069, NO_BOS_CHOCH=2058, HTF_TREND=32 |
| SMC_D1:ETHUSDT | 2284 | 2284 | 13 | 8 | NO_POI_REJECTION=2072, NO_BOS_CHOCH=2067, HTF_TREND=40 |
| SMC_MTF_H1:GBPUSD | 40594 | 40594 | 7547 | 4249 | NO_BOS_CHOCH=32429, NO_POI_REJECTION=32429, HTF_TREND=1357 |
| SMC_MTF_H1:SOLUSDT | 51772 | 51772 | 9404 | 1269 | NO_BOS_CHOCH=41721, NO_POI_REJECTION=41721, HTF_TREND=1460 |
| SMC_MTF_H1:USDCAD | 40600 | 40600 | 7570 | 1186 | NO_BOS_CHOCH=32502, NO_POI_REJECTION=32502, HTF_TREND=1261 |
| SMC_MTF_H1:USDJPY | 40611 | 40611 | 7768 | 1231 | NO_BOS_CHOCH=32286, NO_POI_REJECTION=32286, HTF_TREND=1222 |

## Legacy Artifact Reproduction

The closest replay varies only confirmation mode while using the legacy 24-bar/no-trailing/low-cost profile. The original Yahoo FX cache has zero volume and weekend candles, so it is retained only for forensic reproduction, not validation. Code-version differences still remain.

| Route | Stored period | Stored trades/PF | Replay data | Closest mode | Replay trades/PF |
|---|---|---:|---|---|---:|
| SMC_D1:BTCUSDT | 2020-01-01_to_2026-07-13 | 64/1.87 | BINANCE_SPOT | none_legacy | 53/1.39 |
| SMC_D1:ETHUSDT | 2020-01-01_to_2026-07-13 | 79/2.03 | BINANCE_SPOT | none_legacy | 51/1.30 |
| SMC_MTF_H1:GBPUSD | 2025-07-12_to_2026-07-12 | 164/1.32 | YAHOO_LEGACY_CACHE | none_legacy | 180/0.44 |
| SMC_MTF_H1:SOLUSDT | 2025-07-12_to_2026-07-12 | 170/1.71 | BINANCE | none_legacy | 126/1.35 |
| SMC_MTF_H1:USDCAD | 2025-07-12_to_2026-07-12 | 64/1.57 | YAHOO_LEGACY_CACHE | either | 66/0.33 |
| SMC_MTF_H1:USDJPY | 2025-07-12_to_2026-07-12 | 85/1.49 | YAHOO_LEGACY_CACHE | none_legacy | 86/0.97 |

## Runtime Parity

| Route | Cache samples | Cache match | Rolling live-window samples | Window match rate |
|---|---:|---:|---:|---:|
| SMC_D1:BTCUSDT | 55 | 55/55 | 55 | 100.0% |
| SMC_D1:ETHUSDT | 56 | 56/56 | 56 | 100.0% |
| SMC_MTF_H1:GBPUSD | 63 | 63/63 | 62 | 100.0% |
| SMC_MTF_H1:SOLUSDT | 64 | 64/64 | 64 | 100.0% |
| SMC_MTF_H1:USDCAD | 64 | 64/64 | 63 | 100.0% |
| SMC_MTF_H1:USDJPY | 64 | 64/64 | 63 | 100.0% |

## Key Findings

1. The complete frozen live SMC set is OOS losing: 933 trades, PF=0.93, return sum=-7.20%.
2. SOL H4/H1 is the only surviving route, but remains WATCH: OOS PF=1.23, positive folds=3/4, bootstrap P(mean>0)=91.9%.
3. GBPUSD, USDJPY, and USDCAD fail every tested confirmation mode and every score from 40 through 60. Exit and threshold tuning do not restore their entry edge.
4. The current D1 `both` gate leaves only 7 BTC and 8 ETH signals. Looser diagnostic modes improve headline PF but remain below the 30-trade pooled OOS gate (BTC either: 26; ETH structure: 14).
5. Cache and production rolling-window parity are 100% on all deterministic samples, so the failure is not caused by the research caching shortcut.
6. Stored headline results remain unreproducible even when replaying the original Yahoo cache and legacy low-cost exit profile; they must not authorize current live routing.

## Decision

- PASS: none.
- WATCH: SMC_MTF_H1:SOLUSDT.
- FAIL: SMC_MTF_H1:GBPUSD, SMC_MTF_H1:USDCAD, SMC_MTF_H1:USDJPY.
- NO_SAMPLE: SMC_D1:BTCUSDT, SMC_D1:ETHUSDT.
- A legacy headline PF is rejected when it cannot be reproduced with the current code and live profile.
- No route or parameter is changed by this study.

## Artifacts

- Runner: `scripts/validate_smc_6y5.py`
- Spec: `research/SMC_REVALIDATION_6Y5_SPEC.md`
- Route JSON: `data/smc_revalidation_6y5/routes/`
- Baseline: `data/smc_revalidation_6y5/baseline.csv`
- Folds: `data/smc_revalidation_6y5/folds.csv`
- Confirmation modes: `data/smc_revalidation_6y5/confirmation_modes.csv`
- Score sensitivity: `data/smc_revalidation_6y5/score_sensitivity.csv`
- Cost stress: `data/smc_revalidation_6y5/cost_stress.csv`
