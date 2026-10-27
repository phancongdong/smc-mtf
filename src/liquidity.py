"""Liquidity sweeps and Fibonacci premium/discount zone modeling."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np

from src.types import Candle


def detect_liquidity_sweeps(
    candles: List[Candle],
    idx: int,
    structure: Dict[str, Any],
) -> Dict[str, bool]:
    """Detect liquidity hunt events beyond swing extremes.

    A valid liquidity sweep requires price to penetrate a confirmed swing level,
    followed by at least two consecutive closes back inside the original range.

    Args:
        candles: Sequence of historical price candles.
        idx: Current decision bar index.
        structure: Market structure dictionary with swing highs/lows.

    Returns:
        Dict with boolean flags 'bullish_sweep' and 'bearish_sweep'.
    """
    effective_lookback = min(10, idx)
    if effective_lookback < 3:
        return {"bullish_sweep": False, "bearish_sweep": False}

    swing_lows = structure.get("swing_lows", [])
    swing_highs = structure.get("swing_highs", [])

    bullish_sweep = False
    bearish_sweep = False

    # Bullish sweep: breach below swing low, then snap back with 2 closes above
    if swing_lows:
        recent_low = swing_lows[-1]["price"]
        for i in range(max(0, idx - 5), idx - 1):
            if candles[i].low < recent_low:
                confirmations = candles[i + 1:idx + 1]
                confirmed = len(confirmations) >= 2 and all(
                    c.close > recent_low for c in confirmations[-2:]
                )
                if confirmed:
                    bullish_sweep = True
                    break

    # Bearish sweep: breach above swing high, then snap back with 2 closes below
    if swing_highs:
        recent_high = swing_highs[-1]["price"]
        for i in range(max(0, idx - 5), idx - 1):
            if candles[i].high > recent_high:
                confirmations = candles[i + 1:idx + 1]
                confirmed = len(confirmations) >= 2 and all(
                    c.close < recent_high for c in confirmations[-2:]
                )
                if confirmed:
                    bearish_sweep = True
                    break

    return {"bullish_sweep": bullish_sweep, "bearish_sweep": bearish_sweep}


def calc_discount_premium(
    candles: List[Candle],
    idx: int,
    structure: Optional[Dict[str, Any]] = None,
    lookback: int = 20,
) -> Dict[str, float]:
    """Calculate institutional Fibonacci premium and discount levels.

    Uses deep retracement bounds:
      - 61.8% to 78.6% retracement (remaining distance 38.2% to 21.4% from extreme).

    Args:
        candles: Sequence of price candles.
        idx: Current candle index.
        structure: Optional market structure dictionary.
        lookback: Fallback candle window if structure swings are unavailable.

    Returns:
        Dict of price levels: discount_618, premium_618, deep_discount, deep_premium, mid, high, low.
    """
    effective_lookback = min(lookback, idx)
    if effective_lookback < 5:
        return {"discount": 0.0, "premium": 0.0, "mid": 0.0}

    swing_highs = (structure or {}).get("swing_highs", [])
    swing_lows = (structure or {}).get("swing_lows", [])

    recent_high: Optional[float] = None
    recent_low: Optional[float] = None

    if swing_highs and swing_lows:
        trend = (structure or {}).get("trend", "UNKNOWN")
        indexed_swings = all("idx" in s for s in swing_highs + swing_lows)

        if trend == "UPTREND" and indexed_swings:
            high = swing_highs[-1]
            prior_lows = [s for s in swing_lows if s["idx"] < high["idx"]]
            if prior_lows:
                recent_high, recent_low = high["price"], prior_lows[-1]["price"]
        elif trend == "DOWNTREND" and indexed_swings:
            low = swing_lows[-1]
            prior_highs = [s for s in swing_highs if s["idx"] < low["idx"]]
            if prior_highs:
                recent_high, recent_low = prior_highs[-1]["price"], low["price"]
        elif not indexed_swings:
            recent_high, recent_low = swing_highs[-1]["price"], swing_lows[-1]["price"]

    if recent_high is None or recent_low is None:
        sub_candles = candles[idx - effective_lookback: idx + 1]
        recent_high = max(c.high for c in sub_candles)
        recent_low = min(c.low for c in sub_candles)

    if recent_high <= recent_low:
        return {"discount": 0.0, "premium": 0.0, "mid": 0.0}

    range_px = recent_high - recent_low

    return {
        "discount_618": recent_low + range_px * 0.382,
        "discount_618_buy": recent_low + range_px * 0.382,
        "premium_618": recent_high - range_px * 0.382,
        "premium_618_sell": recent_high - range_px * 0.382,
        "deep_discount": recent_low + range_px * 0.214,
        "deep_premium": recent_high - range_px * 0.214,
        "mid": recent_low + range_px * 0.5,
        "high": recent_high,
        "low": recent_low,
    }
