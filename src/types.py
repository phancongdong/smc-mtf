"""Core data types and domain models for SMC MTF strategy."""

from __future__ import annotations

import enum
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence


class Direction(enum.IntEnum):
    """Trading direction enum."""
    NEUTRAL = 0
    LONG = 1
    SHORT = -1

    @property
    def label(self) -> str:
        return {0: "NEUTRAL", 1: "LONG", -1: "SHORT"}[self.value]


class Timeframe(enum.Enum):
    """Standardized bar timeframe enum."""
    M1 = "1m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1h"
    H4 = "4h"
    H8 = "8h"
    D1 = "1d"
    W1 = "1w"

    def minutes(self) -> int:
        mapping = {
            "1m": 1,
            "5m": 5,
            "15m": 15,
            "30m": 30,
            "1h": 60,
            "4h": 240,
            "8h": 480,
            "1d": 1440,
            "1w": 10080,
        }
        return mapping[self.value]

    @property
    def duration(self) -> timedelta:
        return timedelta(minutes=self.minutes())


class AssetClass(enum.Enum):
    """Asset class category."""
    CRYPTO = "CRYPTO"
    FOREX = "FOREX"
    COMMODITY = "COMMODITY"
    INDEX = "INDEX"


class MarketRegime(enum.Enum):
    """Market regime classification."""
    UNKNOWN = "UNKNOWN"
    UPTREND = "UPTREND"
    DOWNTREND = "DOWNTREND"
    RANGE = "RANGE"


class ExitReason(enum.Enum):
    """Position exit reason."""
    TAKE_PROFIT = "TP"
    STOP_LOSS = "SL"
    TRAILING_STOP = "TRAIL"
    TIME_EXIT = "TIME"
    CONDITION_INVALIDATED = "CONDITION_INVALIDATED"
    MANUAL = "MANUAL"
    END_OF_DATA = "END"


@dataclass(frozen=True)
class Candle:
    """Immutable single price bar representation."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def validate(self) -> bool:
        if not all(math.isfinite(float(v)) for v in (self.open, self.high, self.low, self.close, self.volume)):
            return False
        if self.open <= 0 or self.high <= 0 or self.low <= 0 or self.close <= 0:
            return False
        if self.low > self.high or self.open > self.high or self.open < self.low:
            return False
        if self.close > self.high or self.close < self.low:
            return False
        return True


@dataclass
class BarSeries:
    """Chronological series of price bars."""
    candles: List[Candle]
    symbol: str
    timeframe: Timeframe
    asset_class: AssetClass = AssetClass.CRYPTO
    provider: str = "custom"
    is_synthetic: bool = False

    def __post_init__(self):
        if not self.candles:
            return
        timestamps = [c.timestamp for c in self.candles]
        for i in range(len(timestamps) - 1):
            if timestamps[i] >= timestamps[i + 1]:
                raise ValueError(
                    f"Non-monotonic timestamps at index {i}: {timestamps[i]} >= {timestamps[i + 1]}"
                )

    def __len__(self) -> int:
        return len(self.candles)

    def __getitem__(self, idx: int) -> Candle:
        return self.candles[idx]

    def validate(self) -> bool:
        return all(c.validate() for c in self.candles)

    def slice(self, start: int, end: Optional[int] = None) -> BarSeries:
        return BarSeries(
            candles=self.candles[start:end],
            symbol=self.symbol,
            timeframe=self.timeframe,
            asset_class=self.asset_class,
            provider=self.provider,
            is_synthetic=self.is_synthetic,
        )

    @property
    def timestamps(self) -> List[datetime]:
        return [c.timestamp for c in self.candles]

    @property
    def opens(self) -> List[float]:
        return [c.open for c in self.candles]

    @property
    def highs(self) -> List[float]:
        return [c.high for c in self.candles]

    @property
    def lows(self) -> List[float]:
        return [c.low for c in self.candles]

    @property
    def closes(self) -> List[float]:
        return [c.close for c in self.candles]

    @property
    def volumes(self) -> List[float]:
        return [c.volume for c in self.candles]

    def to_arrays(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamps,
            "open": self.opens,
            "high": self.highs,
            "low": self.lows,
            "close": self.closes,
            "volume": self.volumes,
        }


@dataclass
class Signal:
    """Strategy trade signal."""
    direction: Direction
    confidence: float
    score: float
    indicator_values: Dict[str, Any] = field(default_factory=dict)
    regime: MarketRegime = MarketRegime.UNKNOWN
    strategy_name: str = "SMC_MTF"
    timestamp: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def sl(self) -> Optional[float]:
        return self.metadata.get("sl")

    @property
    def tp(self) -> Optional[float]:
        return self.metadata.get("tp")

    @property
    def risk_reward(self) -> Optional[float]:
        return self.metadata.get("risk_reward")

    @property
    def max_hold(self) -> int:
        return self.metadata.get("max_hold", 20)

    @property
    def reasons(self) -> List[str]:
        raw = self.indicator_values.get("reasons", "")
        return raw.split(";") if raw else []


@dataclass
class Position:
    """Active in-flight trading position."""
    symbol: str
    direction: Direction
    entry_time: datetime
    entry_price: float
    current_size: float
    stop_loss: float
    take_profit: float
    entry_score: float = 0.0
    entry_regime: MarketRegime = MarketRegime.UNKNOWN
    strategy_name: str = "SMC_MTF"
    highest_since_entry: float = 0.0
    lowest_since_entry: float = 0.0
    bars_held: int = 0
    max_hold: int = 20
    trail_activation_price: Optional[float] = None
    trail_distance: Optional[float] = None
    trailing_stop_active: bool = False

    def __post_init__(self):
        if self.highest_since_entry == 0.0:
            self.highest_since_entry = self.entry_price
        if self.lowest_since_entry == 0.0:
            self.lowest_since_entry = self.entry_price

