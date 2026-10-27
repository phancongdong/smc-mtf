# Multi-Timeframe Alignment & Causal Signal Generation

A critical vulnerability in retail multi-timeframe strategies is **lookahead bias** caused by premature aggregation of higher-timeframe (HTF) bars into lower-timeframe (LTF) loops. This document details how `smc-mtf` guarantees 100% causal, point-in-time signal generation.

---

## 1. The Completed Bar Principle

In real-world live trading, an H4 bar that opens at 08:00 UTC only finishes forming at 12:00 UTC. An H1 decision bar evaluated at 09:00 UTC cannot observe the High, Low, or Close of the 08:00-12:00 H4 candle.

### Strict Causality Rule
An HTF candle is observable on an LTF timeline **if and only if** its close timestamp is strictly less than or equal to the LTF decision timestamp:

$$\text{HTF Close Timestamp} \le \text{LTF Decision Timestamp}$$

Where:
$$\text{LTF Decision Timestamp} = \text{LTF Candle Timestamp} + \text{Duration}(\text{LTF})$$

For example, when evaluating an H1 bar stamped `09:00`:
- The candle closes at `10:00`.
- The decision timestamp is `10:00`.
- The latest completed H4 candle is the one that closed at `08:00` (or `10:00` if aligned to an interval boundary).
- Under no circumstance can an uncompleted H4 candle be accessed.

---

## 2. Mathematical Indexing via `bisect_right`

To achieve $O(\log N)$ point-in-time synchronization without copying arrays on every bar:

1. **Precomputation**:
   For the HTF series, calculate the exact close time of every bar:
   $$\text{CloseTimes}_{\text{HTF}} = [c.\text{timestamp} + \Delta t_{\text{HTF}} \quad \forall c \in \text{HTF.candles}]$$

2. **Binary Search**:
   Given an LTF decision timestamp $t_{\text{decision}}$, the visible HTF index is determined by:
   $$\text{htf\_idx} = \text{bisect\_right}(\text{CloseTimes}_{\text{HTF}}, t_{\text{decision}}) - 1$$

- If $t_{\text{decision}} < \text{CloseTimes}_{\text{HTF}}[0]$, `htf_idx` returns $-1$ (insufficient data, signal blocked).
- Because `bisect_right` searches the precomputed monotonic close timestamps, any partial or unformed HTF bar is mathematically excluded.

---

## 3. Dynamic Risk & Target Geometry

When a signal is generated at bar close $t$, target levels are calculated with explicit Risk-to-Reward ($R:R$) constraints:

$$\text{TP}_{\text{long}} = \text{Entry} + (\text{Entry} - \text{Stop Loss}) \times R:R$$
$$\text{TP}_{\text{short}} = \text{Entry} - (\text{Stop Loss} - \text{Entry}) \times R:R$$

Where:
- $\text{Entry}$ is the reference price (current bar close or expected next fill).
- $\text{Stop Loss}$ is derived from the nearest confirmed Order Block extreme or structural swing point.
- $\text{Stop Distance}$ is guarded by a minimum volatility floor:
  $$\text{Distance} = |\text{Entry} - \text{Stop Loss}| \ge 0.05 \times \text{ATR}_{\text{HTF}}$$

---

## 4. Verification Suite

The synchronization and causal contracts are validated by explicit unit tests:
- `test_causal_htf_alignment_zero_lookahead`: Tests boundary timestamps across multi-hour intervals.
- `test_position_risk_reward_target_geometry`: Verifies target geometry and risk-to-reward alignment.
- `test_fvg_first_revisit_active_but_old_mitigation_is_not`: Verifies that historical mitigation state is calculated point-in-time without future leakage.
