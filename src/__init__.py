"""Smart Money Concepts (SMC) Multi-Timeframe Strategy Package.

A deterministic quantitative trading framework combining Higher-Timeframe (HTF)
market structure, Order Blocks (OB), Fair Value Gaps (FVG), Liquidity Sweeps,
and Fibonacci Premium/Discount levels with Lower-Timeframe (LTF) confirmation.
"""

from src.types import (
    AssetClass,
    BarSeries,
    Candle,
    Direction,
    ExitReason,
    MarketRegime,
    Position,
    Signal,
    Timeframe,
)
from src.strategy import SMCMultiTimeframeStrategy
from src.data_loader import load_parquet, parse_timeframe, infer_asset_class
from src.indicators import ATR, EMA, RSI, SMA
from src.market_structure import detect_market_structure
from src.zones import check_zone_rejection, detect_fvg, detect_order_blocks
from src.liquidity import calc_discount_premium, detect_liquidity_sweeps
from src.microstructure import check_ltf_momentum, detect_reversal_candle

__all__ = [
    "AssetClass",
    "BarSeries",
    "Candle",
    "Direction",
    "ExitReason",
    "MarketRegime",
    "Position",
    "Signal",
    "Timeframe",
    "SMCMultiTimeframeStrategy",
    "load_parquet",
    "parse_timeframe",
    "infer_asset_class",
    "ATR",
    "EMA",
    "RSI",
    "SMA",
    "detect_market_structure",
    "detect_order_blocks",
    "detect_fvg",
    "check_zone_rejection",
    "detect_liquidity_sweeps",
    "calc_discount_premium",
    "detect_reversal_candle",
    "check_ltf_momentum",
]

__version__ = "2.0.0"
