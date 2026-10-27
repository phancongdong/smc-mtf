"""High-performance parquet and dataset loader for SMC backtesting."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
import pandas as pd

from src.types import AssetClass, BarSeries, Candle, Timeframe


def parse_timeframe(tf_str: str) -> Timeframe:
    """Normalize string into Timeframe enum."""
    normalized = tf_str.upper().strip()
    mapping = {
        "1M": Timeframe.M1,
        "M1": Timeframe.M1,
        "5M": Timeframe.M5,
        "M5": Timeframe.M5,
        "15M": Timeframe.M15,
        "M15": Timeframe.M15,
        "30M": Timeframe.M30,
        "M30": Timeframe.M30,
        "1H": Timeframe.H1,
        "H1": Timeframe.H1,
        "4H": Timeframe.H4,
        "H4": Timeframe.H4,
        "8H": Timeframe.H8,
        "H8": Timeframe.H8,
        "1D": Timeframe.D1,
        "D1": Timeframe.D1,
        "1W": Timeframe.W1,
        "W1": Timeframe.W1,
    }
    if normalized in mapping:
        return mapping[normalized]
    raise ValueError(f"Unknown timeframe identifier: {tf_str}")


def infer_asset_class(symbol: str) -> AssetClass:
    """Infer asset class category from ticker name."""
    sym = symbol.upper()
    if any(sym.endswith(quote) for quote in ("USDT", "BUSD", "USDC", "BTC", "ETH")):
        return AssetClass.CRYPTO
    if any(sym.startswith(comm) for comm in ("XAU", "XAG", "WTI", "BRENT")):
        return AssetClass.COMMODITY
    if any(fx in sym for fx in ("EUR", "GBP", "JPY", "AUD", "CAD", "CHF", "NZD")):
        return AssetClass.FOREX
    return AssetClass.CRYPTO


def load_parquet(
    file_path: Union[str, Path],
    symbol: Optional[str] = None,
    timeframe: Optional[Union[Timeframe, str]] = None,
    asset_class: Optional[AssetClass] = None,
) -> BarSeries:
    """Load historical OHLCV parquet file into a validated BarSeries.

    Args:
        file_path: Path to .parquet file.
        symbol: Ticker symbol (inferred from filename if None).
        timeframe: Bar timeframe (inferred from filename if None).
        asset_class: Asset class category (inferred from symbol if None).

    Returns:
        BarSeries populated with validated Candle objects.
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Parquet file not found: {path}")

    # Infer symbol and timeframe from filename if not supplied (e.g. binance_spot_SOLUSDT_H1.parquet)
    stem = path.stem
    parts = stem.split("_")

    inferred_symbol = symbol or (parts[2] if len(parts) >= 4 else parts[0])
    inferred_tf_str = str(timeframe) if timeframe is not None else (parts[3] if len(parts) >= 4 else "H1")
    inferred_timeframe = parse_timeframe(inferred_tf_str) if not isinstance(inferred_tf_str, Timeframe) else inferred_tf_str
    inferred_asset_class = asset_class or infer_asset_class(inferred_symbol)

    df = pd.read_parquet(path)

    # Standardize timestamp column
    if "timestamp_ms" in df.columns:
        dt_series = pd.to_datetime(df["timestamp_ms"], unit="ms", utc=True)
    elif "timestamp" in df.columns:
        if pd.api.types.is_integer_dtype(df["timestamp"]):
            unit = "ms" if df["timestamp"].iloc[0] > 1e11 else "s"
            dt_series = pd.to_datetime(df["timestamp"], unit=unit, utc=True)
        else:
            dt_series = pd.to_datetime(df["timestamp"], utc=True)
    elif "datetime" in df.columns:
        dt_series = pd.to_datetime(df["datetime"], utc=True)
    else:
        raise ValueError(f"No recognized timestamp column found in {path.name}")

    opens = df["open"].astype(float).values
    highs = df["high"].astype(float).values
    lows = df["low"].astype(float).values
    closes = df["close"].astype(float).values
    volumes = df["volume"].astype(float).values if "volume" in df.columns else np.zeros(len(df), dtype=float)

    # Convert timestamps to python datetime
    timestamps = [ts.to_pydatetime() for ts in dt_series]

    candles: list[Candle] = []
    for i in range(len(df)):
        candles.append(
            Candle(
                timestamp=timestamps[i],
                open=float(opens[i]),
                high=float(highs[i]),
                low=float(lows[i]),
                close=float(closes[i]),
                volume=float(volumes[i]),
            )
        )

    # Filter out duplicate or non-monotonic timestamps if any exist
    clean_candles: list[Candle] = []
    for c in candles:
        if not clean_candles or c.timestamp > clean_candles[-1].timestamp:
            clean_candles.append(c)

    return BarSeries(
        candles=clean_candles,
        symbol=inferred_symbol,
        timeframe=inferred_timeframe,
        asset_class=inferred_asset_class,
    )


def load_dataset(
    symbol: str,
    timeframe: str,
    data_dir: Optional[Union[str, Path]] = None,
) -> BarSeries:
    """Find and load standard dataset from the data folder."""
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
    else:
        data_dir = Path(data_dir)

    target_name = f"binance_spot_{symbol}_{timeframe}.parquet"
    target_path = data_dir / target_name

    if not target_path.exists():
        # Search by partial match
        matches = list(data_dir.glob(f"*{symbol}*{timeframe}*.parquet"))
        if matches:
            target_path = matches[0]
        else:
            raise FileNotFoundError(f"No parquet found for {symbol} {timeframe} in {data_dir}")

    return load_parquet(target_path, symbol=symbol, timeframe=timeframe)
