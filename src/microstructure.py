"""Lower-Timeframe (LTF) microstructure and momentum confirmation triggers."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import numpy as np

from src.types import BarSeries, Candle
from src.indicators import RSI, EMA


def detect_reversal_candle(
    candles: List[Candle],
    idx: int,
) -> Dict[str, Any]:
    """Identify high-conviction candlestick reversal patterns (Pin Bar, Engulfing).

    Args:
        candles: Sequence of historical price candles.
        idx: Current decision candle index.

    Returns:
        Dict with flags pin_bar, engulfing, reversal, rej_type, bullish, bearish.
    """
    if idx < 2:
        return {
            "pin_bar": False,
            "engulfing": False,
            "reversal": False,
            "rej_type": "NONE",
            "bullish": False,
            "bearish": False,
        }

    c0 = candles[idx - 1]
    c1 = candles[idx]

    body0 = abs(c0.close - c0.open)
    body1 = abs(c1.close - c1.open)

    upper_wick1 = c1.high - max(c1.open, c1.close)
    lower_wick1 = min(c1.open, c1.close) - c1.low

    # Pin bar criteria: one long wick (> 2x body) and one small wick (< 0.3x body)
    pin_bar = (
        min(upper_wick1, lower_wick1) < body1 * 0.3
        and max(upper_wick1, lower_wick1) > body1 * 2.0
    )

    # Engulfing criteria: opposite colour, body > 1.5x previous, engulfs previous body
    opposite_colours = (
        (c0.close < c0.open and c1.close > c1.open)
        or (c0.close > c0.open and c1.close < c1.open)
    )
    body_engulfs = (
        max(c1.open, c1.close) >= max(c0.open, c0.close)
        and min(c1.open, c1.close) <= min(c0.open, c0.close)
    )
    engulfing = body1 > body0 * 1.5 and opposite_colours and body_engulfs

    reversal = pin_bar or engulfing

    rej_type = "NONE"
    if pin_bar:
        rej_type = "PIN_BAR"
    elif engulfing:
        rej_type = "ENGULFING"

    return {
        "pin_bar": pin_bar,
        "engulfing": engulfing,
        "reversal": reversal,
        "rej_type": rej_type,
        "bullish": (pin_bar and lower_wick1 > upper_wick1 * 2) or (engulfing and c1.close > c1.open),
        "bearish": (pin_bar and upper_wick1 > lower_wick1 * 2) or (engulfing and c1.close < c1.open),
    }


def check_ltf_momentum(
    candles: List[Candle],
    idx: int,
    ltf_series: Optional[BarSeries] = None,
    rsi_cache: Optional[np.ndarray] = None,
    ema10_cache: Optional[np.ndarray] = None,
    ema20_cache: Optional[np.ndarray] = None,
    vol_sma20_cache: Optional[np.ndarray] = None,
) -> int:
    """Evaluate LTF directional momentum confluence.

    Combines RSI(7), EMA(10)/EMA(20) cross/slope, and volume surge (> 1.3x 20-SMA).

    Returns:
        +1: Bullish momentum confluence
        -1: Bearish momentum confluence
         0: Neutral / insufficient confluence
    """
    if idx < 5:
        return 0

    # RSI(7)
    if rsi_cache is not None and idx < len(rsi_cache):
        rsi_val = rsi_cache[idx]
    elif ltf_series is not None:
        rsi_val = RSI.compute_at(ltf_series, idx, period=7)
    else:
        closes = np.array([c.close for c in candles[:idx + 1]], dtype=float)
        rsi_arr = RSI.compute(closes, period=7)
        rsi_val = rsi_arr[-1]

    if np.isnan(rsi_val):
        return 0

    # EMA(10) and EMA(20)
    if ema10_cache is not None and idx < len(ema10_cache):
        ema10 = ema10_cache[idx]
    elif ltf_series is not None:
        ema10 = EMA.compute_at(ltf_series, idx, period=10)
    else:
        closes = np.array([c.close for c in candles[:idx + 1]], dtype=float)
        ema10 = EMA.compute_at(closes, idx, period=10)

    if ema20_cache is not None and idx < len(ema20_cache):
        ema20 = ema20_cache[idx]
    elif ltf_series is not None:
        ema20 = EMA.compute_at(ltf_series, idx, period=20)
    else:
        closes = np.array([c.close for c in candles[:idx + 1]], dtype=float)
        ema20 = EMA.compute_at(closes, idx, period=20)

    if np.isnan(ema10) or np.isnan(ema20):
        return 0

    # Volume SMA(20)
    if vol_sma20_cache is not None and idx < len(vol_sma20_cache):
        vol_sma = vol_sma20_cache[idx]
    else:
        recent_volumes = [c.volume for c in candles[max(0, idx - 19):idx + 1]]
        vol_sma = float(np.mean(recent_volumes)) if len(recent_volumes) == 20 else np.nan

    vol_ratio = 1.0 if np.isnan(vol_sma) or vol_sma <= 0 else candles[idx].volume / vol_sma

    score = 0
    if rsi_val < 35:
        score -= 1
    elif rsi_val > 65:
        score += 1

    if ema10 > ema20:
        score += 1
    else:
        score -= 1

    if vol_ratio > 1.3:
        score += 1 if score > 0 else -1

    if score >= 2:
        return 1
    elif score <= -2:
        return -1
    return 0
