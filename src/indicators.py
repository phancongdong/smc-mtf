"""Vectorized and point-in-time safe technical indicators for SMC strategy.

Provides EMA, SMA, ATR, and RSI implementations with zero lookahead bias.
"""

from __future__ import annotations

from typing import Union, List
import numpy as np

from src.types import BarSeries, Candle


def _extract_arrays(series: Union[BarSeries, List[Candle], np.ndarray]):
    """Extract OHLCV numpy arrays from BarSeries, Candle list, or arrays."""
    if isinstance(series, BarSeries):
        high = np.array(series.highs, dtype=float)
        low = np.array(series.lows, dtype=float)
        close = np.array(series.closes, dtype=float)
        volume = np.array(series.volumes, dtype=float)
        return high, low, close, volume
    elif isinstance(series, list) and len(series) > 0 and isinstance(series[0], Candle):
        high = np.array([c.high for c in series], dtype=float)
        low = np.array([c.low for c in series], dtype=float)
        close = np.array([c.close for c in series], dtype=float)
        volume = np.array([c.volume for c in series], dtype=float)
        return high, low, close, volume
    elif isinstance(series, np.ndarray):
        return None, None, series.astype(float), None
    else:
        raise ValueError(f"Unsupported data type for indicator input: {type(series)}")


# ──────────────────────────────────────────────────────────────────
# EMA
# ──────────────────────────────────────────────────────────────────

def compute_ema(values: np.ndarray, period: int) -> np.ndarray:
    """Calculate Exponential Moving Average (EMA)."""
    n = len(values)
    result = np.full(n, np.nan)
    if n < period:
        return result
    alpha = 2.0 / (period + 1)
    result[period - 1] = np.mean(values[:period])
    for i in range(period, n):
        result[i] = values[i] * alpha + result[i - 1] * (1.0 - alpha)
    return result


class EMA:
    """Exponential Moving Average indicator wrapper."""

    @staticmethod
    def compute(series: Union[BarSeries, List[Candle], np.ndarray], period: int = 14) -> np.ndarray:
        if isinstance(series, (BarSeries, list)):
            _, _, close, _ = _extract_arrays(series)
            return compute_ema(close, period)
        return compute_ema(np.asarray(series, dtype=float), period)

    @staticmethod
    def compute_at(series: Union[BarSeries, List[Candle], np.ndarray], idx: int, period: int = 14) -> float:
        arr = EMA.compute(series, period)
        if 0 <= idx < len(arr):
            val = arr[idx]
            return float(val) if np.isfinite(val) else np.nan
        return np.nan


# ──────────────────────────────────────────────────────────────────
# SMA
# ──────────────────────────────────────────────────────────────────

def compute_sma(values: np.ndarray, period: int) -> np.ndarray:
    """Calculate Simple Moving Average (SMA)."""
    n = len(values)
    result = np.full(n, np.nan)
    if n < period:
        return result
    cumsum = np.cumsum(values)
    result[period - 1:] = (cumsum[period - 1:] - np.concatenate([[0.0], cumsum[:n - period]])) / period
    return result


class SMA:
    """Simple Moving Average indicator wrapper."""

    @staticmethod
    def compute(series: Union[BarSeries, List[Candle], np.ndarray], period: int = 20) -> np.ndarray:
        if isinstance(series, (BarSeries, list)):
            _, _, close, _ = _extract_arrays(series)
            return compute_sma(close, period)
        return compute_sma(np.asarray(series, dtype=float), period)

    @staticmethod
    def compute_at(series: Union[BarSeries, List[Candle], np.ndarray], idx: int, period: int = 20) -> float:
        arr = SMA.compute(series, period)
        if 0 <= idx < len(arr):
            val = arr[idx]
            return float(val) if np.isfinite(val) else np.nan
        return np.nan


# ──────────────────────────────────────────────────────────────────
# ATR
# ──────────────────────────────────────────────────────────────────

def compute_true_range(high: np.ndarray, low: np.ndarray, close: np.ndarray) -> np.ndarray:
    """Compute Wilder's True Range (TR)."""
    n = len(high)
    tr = np.full(n, np.nan)
    if n == 0:
        return tr
    tr[0] = high[0] - low[0]
    for i in range(1, n):
        tr[i] = max(
            high[i] - low[i],
            abs(high[i] - close[i - 1]),
            abs(low[i] - close[i - 1]),
        )
    return tr


def compute_atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute Average True Range (ATR) using Wilder's smoothing."""
    n = len(close)
    tr = compute_true_range(high, low, close)
    result = np.full(n, np.nan)
    if n < period:
        return result
    result[period - 1] = np.mean(tr[:period])
    alpha = 1.0 / period
    for i in range(period, n):
        result[i] = tr[i] * alpha + result[i - 1] * (1.0 - alpha)
    return result


class ATR:
    """Average True Range indicator wrapper."""

    @staticmethod
    def compute(series: Union[BarSeries, List[Candle]], period: int = 14) -> np.ndarray:
        high, low, close, _ = _extract_arrays(series)
        return compute_atr(high, low, close, period)

    @staticmethod
    def compute_at(series: Union[BarSeries, List[Candle]], idx: int, period: int = 14) -> float:
        arr = ATR.compute(series, period)
        if 0 <= idx < len(arr):
            val = arr[idx]
            return float(val) if np.isfinite(val) else np.nan
        return np.nan


# ──────────────────────────────────────────────────────────────────
# RSI
# ──────────────────────────────────────────────────────────────────

def compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Compute Relative Strength Index (RSI) using Wilder's smoothing."""
    n = len(close)
    result = np.full(n, np.nan)
    if n < period + 1:
        return result
    deltas = np.diff(close)
    gains = np.maximum(deltas, 0.0)
    losses = np.maximum(-deltas, 0.0)
    avg_gain = np.mean(gains[:period])
    avg_loss = np.mean(losses[:period])

    if avg_loss == 0.0:
        result[period] = 50.0 if avg_gain == 0.0 else 100.0
    else:
        rs = avg_gain / avg_loss
        result[period] = 100.0 - 100.0 / (1.0 + rs)

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i - 1]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i - 1]) / period
        if avg_loss == 0.0:
            result[i] = 50.0 if avg_gain == 0.0 else 100.0
        else:
            rs = avg_gain / avg_loss
            result[i] = 100.0 - 100.0 / (1.0 + rs)
    return result


class RSI:
    """Relative Strength Index indicator wrapper."""

    @staticmethod
    def compute(series: Union[BarSeries, List[Candle], np.ndarray], period: int = 14) -> np.ndarray:
        if isinstance(series, (BarSeries, list)):
            _, _, close, _ = _extract_arrays(series)
            return compute_rsi(close, period)
        return compute_rsi(np.asarray(series, dtype=float), period)

    @staticmethod
    def compute_at(series: Union[BarSeries, List[Candle], np.ndarray], idx: int, period: int = 14) -> float:
        arr = RSI.compute(series, period)
        if 0 <= idx < len(arr):
            val = arr[idx]
            return float(val) if np.isfinite(val) else np.nan
        return np.nan
