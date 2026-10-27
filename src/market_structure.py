"""Market structure analysis for SMC strategy.

Detects 5-bar fractal swings (HH, HL, LH, LL), evaluates trend regimes,
and detects directional Break of Structure (BOS) and Change of Character (CHoCH).
"""

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np

from src.types import Candle


def detect_market_structure(
    candles: List[Candle],
    idx: int,
    lookback: int = 30,
) -> Dict[str, Any]:
    """Detect fractal swings, trend regime, and directional BOS/CHoCH transitions.

    Args:
        candles: Sequence of historical price candles.
        idx: Target candle index for point-in-time analysis.
        lookback: Maximum number of trailing candles to evaluate for swings.

    Returns:
        Dict containing trend, swing_highs, swing_lows, bos, choch,
        bos_direction, and choch_direction.
    """
    effective_lookback = min(lookback, idx)
    if effective_lookback < 5:
        return {
            "trend": "UNKNOWN",
            "swing_highs": [],
            "swing_lows": [],
            "bos": False,
            "choch": False,
            "bos_direction": "NONE",
            "choch_direction": "NONE",
        }

    sub_candles = candles[idx - effective_lookback: idx + 1]
    highs = np.array([c.high for c in sub_candles], dtype=float)
    lows = np.array([c.low for c in sub_candles], dtype=float)

    swing_highs: List[Dict[str, Any]] = []
    swing_lows: List[Dict[str, Any]] = []

    # 5-bar fractal check: center bar must exceed 2 bars left and 2 bars right
    for i in range(2, len(highs) - 2):
        if (
            highs[i] > highs[i - 1]
            and highs[i] > highs[i - 2]
            and highs[i] > highs[i + 1]
            and highs[i] > highs[i + 2]
        ):
            label = "HH" if not swing_highs or highs[i] > swing_highs[-1]["price"] else "LH"
            swing_highs.append({
                "idx": idx - effective_lookback + i,
                "price": float(highs[i]),
                "type": label,
            })

        if (
            lows[i] < lows[i - 1]
            and lows[i] < lows[i - 2]
            and lows[i] < lows[i + 1]
            and lows[i] < lows[i + 2]
        ):
            label = "HL" if not swing_lows or lows[i] > swing_lows[-1]["price"] else "LL"
            swing_lows.append({
                "idx": idx - effective_lookback + i,
                "price": float(lows[i]),
                "type": label,
            })

    trend = "UNKNOWN"
    bos_direction = "NONE"
    choch_direction = "NONE"

    if len(swing_highs) >= 2 and len(swing_lows) >= 2:
        higher_structure = (
            swing_highs[-1]["price"] > swing_highs[-2]["price"]
            and swing_lows[-1]["price"] > swing_lows[-2]["price"]
        )
        lower_structure = (
            swing_highs[-1]["price"] < swing_highs[-2]["price"]
            and swing_lows[-1]["price"] < swing_lows[-2]["price"]
        )
        prior_trend = "UPTREND" if higher_structure else "DOWNTREND" if lower_structure else "RANGE"

        # A structural break requires a confirmed CLOSE beyond the most recent swing.
        # Wick-only penetration is a liquidity sweep, not a structure break.
        previous_close = candles[idx - 1].close
        current_close = candles[idx].close

        breaks_high = (
            previous_close <= swing_highs[-1]["price"]
            and current_close > swing_highs[-1]["price"]
        )
        breaks_low = (
            previous_close >= swing_lows[-1]["price"]
            and current_close < swing_lows[-1]["price"]
        )

        if prior_trend == "UPTREND":
            if breaks_low:
                choch_direction = "BEARISH"
                trend = "DOWNTREND"
            else:
                trend = prior_trend
                if breaks_high:
                    bos_direction = "BULLISH"
        elif prior_trend == "DOWNTREND":
            if breaks_high:
                choch_direction = "BULLISH"
                trend = "UPTREND"
            else:
                trend = prior_trend
                if breaks_low:
                    bos_direction = "BEARISH"
        else:
            trend = prior_trend
            if breaks_high:
                bos_direction = "BULLISH"
                trend = "UPTREND"
            elif breaks_low:
                bos_direction = "BEARISH"
                trend = "DOWNTREND"

    return {
        "trend": trend,
        "swing_highs": swing_highs,
        "swing_lows": swing_lows,
        "bos": bos_direction != "NONE",
        "choch": choch_direction != "NONE",
        "bos_direction": bos_direction,
        "choch_direction": choch_direction,
    }
