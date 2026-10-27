# Smart Money Concepts (SMC) Mechanics Guide

This guide details the mathematical and algorithmic definitions of the Smart Money Concepts implemented in the `smc-mtf` quantitative trading system.

---

## 1. Market Structure & Swing Detection

### 1.1 Five-Bar Fractal Swings
Market structure is identified using point-in-time 5-bar fractal swings:
- **Swing High**: Candle $i$ has a higher high than the two bars to its left and the two bars to its right:
  $$\text{High}_i > \max(\text{High}_{i-2}, \text{High}_{i-1}, \text{High}_{i+1}, \text{High}_{i+2})$$
  - Labeled as **Higher High (HH)** if $\text{High}_i > \text{Previous Swing High}$, otherwise **Lower High (LH)**.
- **Swing Low**: Candle $i$ has a lower low than the two bars to its left and the two bars to its right:
  $$\text{Low}_i < \min(\text{Low}_{i-2}, \text{Low}_{i-1}, \text{Low}_{i+1}, \text{Low}_{i+2})$$
  - Labeled as **Higher Low (HL)** if $\text{Low}_i > \text{Previous Swing Low}$, otherwise **Lower Low (LL)**.

### 1.2 Trend Classification
A minimum of two swing highs and two swing lows are required to classify the macro regime:
- **UPTREND**: Both consecutive swing highs and consecutive swing lows are ascending:
  $$\text{High}_{-1} > \text{High}_{-2} \quad \text{and} \quad \text{Low}_{-1} > \text{Low}_{-2}$$
- **DOWNTREND**: Both consecutive swing highs and consecutive swing lows are descending:
  $$\text{High}_{-1} < \text{High}_{-2} \quad \text{and} \quad \text{Low}_{-1} < \text{Low}_{-2}$$
- **RANGE**: Divergent swings (e.g. HH with LL or LH with HL).

### 1.3 Break of Structure (BOS) vs Change of Character (CHoCH)
Crucially, a structural break requires a confirmed **close** beyond the most recent confirmed swing level. Wick-only excursions represent liquidity sweeps, not structural breaks.
- **BOS (Trend Continuation)**:
  - Bullish: In an uptrend, previous bar closed below latest swing high, and current bar closes strictly above:
    $$\text{Close}_{idx-1} \le \text{SwingHigh} \quad \text{and} \quad \text{Close}_{idx} > \text{SwingHigh}$$
  - Bearish: In a downtrend, previous bar closed above latest swing low, and current bar closes strictly below:
    $$\text{Close}_{idx-1} \ge \text{SwingLow} \quad \text{and} \quad \text{Close}_{idx} < \text{SwingLow}$$
- **CHoCH (Trend Reversal)**:
  - Bearish CHoCH: In an uptrend, price breaks and closes below the protected swing low. The trend immediately flips to `DOWNTREND`.
  - Bullish CHoCH: In a downtrend, price breaks and closes above the protected swing high. The trend immediately flips to `UPTREND`.

---

## 2. Institutional Points of Interest (POI)

### 2.1 Order Blocks (OB)
An Order Block marks where institutional participants placed aggressive resting inventory before a directional displacement:
- **Bullish Order Block**:
  1. Candle $i-1$ is bearish ($\text{Close} < \text{Open}$).
  2. Candle $i$ is bullish ($\text{Close} > \text{Open}$) with displacement body $\ge 1.3 \times$ previous body.
  3. Candle $i$ closes strictly above the highest high of the preceding 3 to 5 bars.
  4. The boundary of the Order Block is defined by the high and low of candle $i-1$:
     $$\text{Top} = \text{High}_{i-1}, \quad \text{Bottom} = \text{Low}_{i-1}$$
- **Bearish Order Block**:
  1. Candle $i-1$ is bullish ($\text{Close} > \text{Open}$).
  2. Candle $i$ is bearish ($\text{Close} < \text{Open}$) with displacement body $\ge 1.3 \times$ previous body.
  3. Candle $i$ closes strictly below the lowest low of the preceding 3 to 5 bars.
  4. The boundary of the Order Block is:
     $$\text{Top} = \text{High}_{i-1}, \quad \text{Bottom} = \text{Low}_{i-1}$$

### 2.2 Fair Value Gaps (FVG)
An FVG represents an imbalance between aggressive buying/selling across three consecutive bars:
- **Bullish FVG**: Bar 0 High is lower than Bar 2 Low. The unfilled gap spans:
  $$\text{Top} = \text{Low}_{\text{bar } 2}, \quad \text{Bottom} = \text{High}_{\text{bar } 0}$$
- **Bearish FVG**: Bar 0 Low is higher than Bar 2 High. The unfilled gap spans:
  $$\text{Top} = \text{Low}_{\text{bar } 0}, \quad \text{Bottom} = \text{High}_{\text{bar } 2}$$

### 2.3 Point-in-Time Zone Lifecycle Tracking
Every OB and FVG tracks its state through time without lookahead:
- **Active**: Zone is untouched or revisited for the first time on the current bar.
- **Mitigated**: Zone was penetrated by price prior to the immediately preceding bar. Once mitigated, it is disqualified from future setups.
- **Invalidated**: Price closed through the zone boundary (below bottom for bullish, above top for bearish).

### 2.4 Rejection Wick Trigger
Price merely entering a zone is insufficient to trigger an order. Price must test the zone and display a rejection response on the current bar:
- **Long Rejection**: Bullish candle where lower wick is at least 50% of the body:
  $$\text{Lower Wick} = \min(\text{Open}, \text{Close}) - \text{Low} \ge 0.5 \times (\text{Close} - \text{Open})$$
- **Short Rejection**: Bearish candle where upper wick is at least 50% of the body:
  $$\text{Upper Wick} = \text{High} - \max(\text{Open}, \text{Close}) \ge 0.5 \times (\text{Open} - \text{Close})$$
- **Self-Rejection Guard**: A zone cannot trigger a rejection on the bar of its own creation ($\text{zone\_idx} < \text{current\_idx}$).

---

## 3. Liquidity Sweeps & Retracement Levels

### 3.1 Two-Bar Close Liquidity Sweeps
False breakouts and liquidity grabs are modeled with multi-bar confirmation:
- **Bullish Sweep**: Price breaches below a swing low ($\text{Low} < \text{SwingLow}$), followed by at least two consecutive candles closing back above the swing low level.
- **Bearish Sweep**: Price breaches above a swing high ($\text{High} > \text{SwingHigh}$), followed by at least two consecutive candles closing back below the swing high level.

### 3.2 Fibonacci Premium & Discount
To maintain favorable risk-to-reward ratios, institutional entries are restricted to deep retracement zones:
- Calculated between the active structural swing high and swing low:
  $$\text{Range} = \text{Recent High} - \text{Recent Low}$$
- **Discount 61.8% Level (Long Entry Zone)**:
  $$\text{Discount}_{61.8} = \text{Low} + 0.382 \times \text{Range}$$
- **Premium 61.8% Level (Short Entry Zone)**:
  $$\text{Premium}_{61.8} = \text{High} - 0.382 \times \text{Range}$$
- **Deep Discount / Premium (78.6% Retracement)**:
  $$\text{Deep Discount} = \text{Low} + 0.214 \times \text{Range}$$
  $$\text{Deep Premium} = \text{High} - 0.214 \times \text{Range}$$

---

## 4. Lower Timeframe (LTF) Microstructure & Triggers

### 4.1 Reversal Candlesticks
- **Pin Bar**: One wick $\ge 2.0 \times \text{Body}$ while opposing wick $\le 0.3 \times \text{Body}$.
- **Engulfing**: Opposing direction, body $\ge 1.5 \times \text{Previous Body}$, and fully engulfing the previous bar's body.

### 4.2 Momentum Confluence
Confluence is scored across:
1. **RSI(7)**: $> 65$ (bullish, +1) or $< 35$ (bearish, -1).
2. **EMA(10) / EMA(20)**: EMA(10) > EMA(20) (+1) or EMA(10) < EMA(20) (-1).
3. **Volume Surge**: Current bar volume $> 1.3 \times 20\text{-bar SMA volume}$.
- LTF Momentum triggers when cumulative score $\ge +2$ (bullish) or $\le -2$ (bearish).

---

## 5. Confluence Scoring & Confirmation Gates

Signals are synthesized using an additive scoring model:

| Component | Weight | Condition |
|---|---:|---|
| HTF Trend | 20 pts | UPTREND (Long) or DOWNTREND (Short) |
| HTF BOS | 10 pts | Same-direction Break of Structure |
| HTF CHoCH | 5 pts | Same-direction Change of Character |
| HTF Order Block | 20 pts | Touch + active rejection wick |
| HTF Fair Value Gap | 15 pts | Touch + active rejection wick |
| HTF Fibonacci | 5 pts | Price within 61.8% - 78.6% discount/premium |
| LTF Liquidity Sweep | 15 pts | 2-bar close confirmed sweep |
| LTF Reversal Candle | 15 pts | Confirmed Pin Bar or Engulfing |
| LTF Momentum | 10 pts | Score $\ge 2$ with volume surge |

### Confirmation Modes
- `both`: Requires both structural confirmation (BOS or CHoCH) AND institutional POI rejection (OB or FVG).
- `either`: Requires at least one confirmation (BOS/CHoCH OR POI rejection).
- `structure`: Requires BOS or CHoCH confirmation; POI rejection is optional.
- `poi`: Requires POI rejection; structure confirmation is optional.
