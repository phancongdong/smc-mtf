# Multi-Timeframe Alignment & Causal Execution

A critical vulnerability in retail multi-timeframe strategies is **lookahead bias** caused by premature aggregation of higher-timeframe (HTF) bars into lower-timeframe (LTF) loops. This document details how `smc-mtf` guarantees 100% causal, point-in-time execution.

---

## 1. The Completed Bar Principle

In real-world live trading, an H4 bar that opens at 08:00 UTC only finishes forming at 12:00 UTC. An H1 decision bar evaluated at 09:00 UTC cannot observe the High, Low, or Close of the 08:00-12:00 H4 candle.

### Strict Causality Rule
An HTF candle is tradable on an LTF timeline **if and only if** its close timestamp is strictly less than or equal to the LTF decision timestamp:

$$\text{HTF Close Timestamp} \le \text{LTF Decision Timestamp}$$

Where:
$$\text{LTF Decision Timestamp} = \text{LTF Candle Timestamp} + \text{Duration}(\text{LTF})$$

For example, when evaluating an H1 bar stamped `09:00`:
- The candle closes at `10:00`.
- The decision timestamp is `10:00`.
- The latest completed H4 candle is the one that closed at `08:00` (or `10:00` if aligned to an interval boundary).
- Under no circumstance can the H4 candle closing at `12:00` be accessed.

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

## 3. Order Execution Mechanics

### 3.1 Next-Bar Open Execution
Signals are calculated at the close of candle $i$ using only information available through candle $i$. The fill is executed at the **Open** of candle $i+1$:

$$\text{Fill Price} = \text{Open}_{i+1} \times \left(1 \pm \frac{\text{Spread}_{\text{bps}} / 2 + \text{Slippage}_{\text{bps}}}{10{,}000}\right)$$

### 3.2 Dynamic Take-Profit Reanchoring
When an order fills at $\text{Open}_{i+1}$, market gaps or slippage may cause $\text{Fill Price} \ne \text{Close}_i$. To guarantee the target Risk-to-Reward ($R:R$) ratio, Take Profit is reanchored to the realized fill price:

$$\text{TP}_{\text{long}} = \text{Fill Price} + (\text{Fill Price} - \text{Stop Loss}) \times R:R$$
$$\text{TP}_{\text{short}} = \text{Fill Price} - (\text{Stop Loss} - \text{Fill Price}) \times R:R$$

### 3.3 Conservative Stop-First Intrabar Priority
When a price candle's range touches both the Stop Loss and Take Profit within the same bar, standard retail backtesters often register a win. In institutional backtesting, the simulator enforces **Stop-First Priority**:
- If $\text{Low} \le \text{SL}$ and $\text{High} \ge \text{TP}$ on the same bar, the trade is marked as a **Stop Loss exit**.

---

## 4. Verification Suite

The synchronization and execution contracts are validated by explicit unit tests:
- `test_causal_htf_alignment_zero_lookahead`: Tests boundary timestamps across 4-hour intervals.
- `test_rr_target_is_reanchored_to_actual_next_open_fill`: Verifies that gapped next-bar open fills correctly recompute target take profit.
- `test_fvg_first_revisit_active_but_old_mitigation_is_not`: Verifies that historical mitigation state is calculated point-in-time without future leakage.
