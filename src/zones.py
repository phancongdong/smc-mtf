"""Order Block (OB) and Fair Value Gap (FVG) point-in-time detection and lifecycle tracking."""

from __future__ import annotations

from typing import Any, Dict, List
import numpy as np

from src.types import Candle


def annotate_zone_lifecycle(
    zone: Dict[str, Any],
    candles: List[Candle],
    start: int,
    idx: int,
) -> None:
    """Track point-in-time zone mitigation and invalidation.

    Args:
        zone: Zone dictionary with keys type, top, bottom.
        candles: Full historical candle sequence.
        start: Starting bar index after the formation bar.
        idx: Current decision bar index.
    """
    first_touch = None
    invalidated = False

    for k in range(start, idx + 1):
        c = candles[k]
        if c.low <= zone["top"] and c.high >= zone["bottom"] and first_touch is None:
            first_touch = k

        # Invalidation occurs when candle body closes entirely through the zone
        if zone["type"] == "BULLISH" and c.close < zone["bottom"]:
            invalidated = True
            break
        if zone["type"] == "BEARISH" and c.close > zone["top"]:
            invalidated = True
            break

    zone["first_touch_idx"] = first_touch
    # A zone is considered stale/mitigated if touched before the immediately preceding bar
    zone["mitigated"] = first_touch is not None and first_touch < idx - 1
    zone["invalidated"] = invalidated
    zone["active"] = not invalidated and not zone["mitigated"]


def detect_order_blocks(
    candles: List[Candle],
    idx: int,
    lookback: int = 20,
) -> List[Dict[str, Any]]:
    """Detect institutional Order Blocks with displacement confirmation.

    Args:
        candles: Sequence of historical price candles.
        idx: Current candle index.
        lookback: Maximum bars to search backwards.

    Returns:
        List of Order Block zone dictionaries.
    """
    effective_lookback = min(lookback, idx)
    if effective_lookback < 5:
        return []

    obs: List[Dict[str, Any]] = []
    for i in range(idx - effective_lookback + 2, idx + 1):
        c1 = candles[i - 1]
        c2 = candles[i]
        prior = candles[max(0, i - 6):i - 1]
        if len(prior) < 3:
            continue

        # Bullish Order Block: down candle followed by explosive displacement closing above prior range highs
        if (
            c1.close < c1.open
            and c2.close > c2.open
            and (c2.close - c2.open) > (c1.open - c1.close) * 1.3
        ):
            if c2.close > max(c.high for c in prior):
                body_c1 = c1.open - c1.close
                body_c2 = c2.close - c2.open
                strength = body_c2 / body_c1 if body_c1 > 0 else 1.0
                zone = {
                    "type": "BULLISH",
                    "idx": i - 1,
                    "displacement_idx": i,
                    "top": float(c1.high),
                    "bottom": float(c1.low),
                    "strength": float(strength),
                }
                annotate_zone_lifecycle(zone, candles, i + 1, idx)
                obs.append(zone)

        # Bearish Order Block: up candle followed by explosive displacement closing below prior range lows
        if (
            c1.close > c1.open
            and c2.close < c2.open
            and (c2.open - c2.close) > (c1.close - c1.open) * 1.3
        ):
            if c2.close < min(c.low for c in prior):
                body_c1 = c1.close - c1.open
                body_c2 = c2.open - c2.close
                strength = body_c2 / body_c1 if body_c1 > 0 else 1.0
                zone = {
                    "type": "BEARISH",
                    "idx": i - 1,
                    "displacement_idx": i,
                    "top": float(c1.high),
                    "bottom": float(c1.low),
                    "strength": float(strength),
                }
                annotate_zone_lifecycle(zone, candles, i + 1, idx)
                obs.append(zone)

    return obs


def detect_fvg(
    candles: List[Candle],
    idx: int,
    lookback: int = 10,
) -> List[Dict[str, Any]]:
    """Detect Fair Value Gaps (3-bar imbalance).

    Args:
        candles: Sequence of historical price candles.
        idx: Current candle index.
        lookback: Maximum bars to search backwards.

    Returns:
        List of FVG zone dictionaries.
    """
    effective_lookback = min(lookback, idx)
    if effective_lookback < 5:
        return []

    fvgs: List[Dict[str, Any]] = []
    for i in range(idx - effective_lookback + 2, idx + 1):
        c0 = candles[i - 2]
        c2 = candles[i]

        # Bullish FVG: Bar 0 High is lower than Bar 2 Low (unfilled imbalance gap)
        if c0.high < c2.low:
            zone = {
                "type": "BULLISH",
                "idx": i,
                "top": float(c2.low),
                "bottom": float(c0.high),
            }
            annotate_zone_lifecycle(zone, candles, i + 1, idx)
            fvgs.append(zone)

        # Bearish FVG: Bar 0 Low is higher than Bar 2 High (unfilled imbalance gap)
        if c0.low > c2.high:
            zone = {
                "type": "BEARISH",
                "idx": i,
                "top": float(c0.low),
                "bottom": float(c2.high),
            }
            annotate_zone_lifecycle(zone, candles, i + 1, idx)
            fvgs.append(zone)

    return fvgs


def check_zone_rejection(
    candles: List[Candle],
    idx: int,
    zone_top: float,
    zone_bottom: float,
    direction: str,
    zone_idx: int = -1,
) -> bool:
    """Verify price touch and rejection wick response at Point of Interest (POI).

    Args:
        candles: Sequence of candles.
        idx: Current candle index.
        zone_top: Upper boundary of zone.
        zone_bottom: Lower boundary of zone.
        direction: Expected trade direction ('LONG' or 'SHORT').
        zone_idx: Bar index where zone was created (prevent self-rejection on formation bar).

    Returns:
        True if price touched the zone and current bar produced a directional rejection wick.
    """
    if idx < 2:
        return False
    if zone_idx >= idx:
        return False

    c0 = candles[idx - 1]
    c1 = candles[idx]

    # Zone must have been penetrated within the last 2 bars
    touched_zone = any(c.low <= zone_top and c.high >= zone_bottom for c in (c0, c1))
    if not touched_zone:
        return False

    # Long rejection: bullish close with lower wick >= 50% of candle body
    if direction == "LONG":
        body = c1.close - c1.open
        lower_wick = min(c1.open, c1.close) - c1.low
        return body > 0 and lower_wick >= abs(body) * 0.5
    else:
        # Short rejection: bearish close with upper wick >= 50% of candle body
        body = c1.open - c1.close
        upper_wick = c1.high - max(c1.open, c1.close)
        return body > 0 and upper_wick >= abs(body) * 0.5
