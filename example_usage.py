#!/usr/bin/env python3
"""Example demonstration of SMC Multi-Timeframe Strategy signal generation.

Shows how to feed multi-timeframe candle data into SMCMultiTimeframeStrategy
to generate high-confluence institutional signals with dynamic SL/TP levels.
"""

from datetime import datetime, timedelta, timezone
from src.types import AssetClass, BarSeries, Candle, Direction, Timeframe
from src.strategy import SMCMultiTimeframeStrategy

T0 = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)


def generate_sample_candles(n_bars: int, interval_hours: int, base_price: float = 100.0) -> list[Candle]:
    """Generate synthetic trending bar data for demonstration."""
    candles = []
    price = base_price
    for i in range(n_bars):
        ts = T0 + timedelta(hours=i * interval_hours)
        change = 0.5 * (1 if (i % 8) < 5 else -1)
        o = price
        c = price + change
        h = max(o, c) + 0.3
        l = min(o, c) - 0.3
        v = 1500.0 + (i % 5) * 100.0
        candles.append(Candle(ts, o, h, l, c, v))
        price = c
    return candles


def main():
    print("=" * 65)
    print("  Smart Money Concepts (SMC) Multi-Timeframe Strategy Demo")
    print("=" * 65)

    # 1. Create Higher Timeframe (H4) and Lower Timeframe (H1) bar series
    htf_candles = generate_sample_candles(n_bars=80, interval_hours=4, base_price=100.0)
    ltf_candles = generate_sample_candles(n_bars=320, interval_hours=1, base_price=100.0)

    htf_series = BarSeries(htf_candles, symbol="SOLUSDT", timeframe=Timeframe.H4, asset_class=AssetClass.CRYPTO)
    ltf_series = BarSeries(ltf_candles, symbol="SOLUSDT", timeframe=Timeframe.H1, asset_class=AssetClass.CRYPTO)

    print(f"[+] Loaded HTF ({htf_series.timeframe.value}) Bars : {len(htf_series)}")
    print(f"[+] Loaded LTF ({ltf_series.timeframe.value}) Bars : {len(ltf_series)}")

    # 2. Instantiate and configure Strategy
    strategy = SMCMultiTimeframeStrategy(
        confirmation_mode="either",
        min_score=40,
        sl_atr_mult=1.5,
        tp_atr_mult=3.0,
        max_hold_bars=20,
    )
    strategy.set_htf_data(htf_series)
    strategy.set_ltf_data(ltf_series)

    # 3. Evaluate signals point-in-time
    print("\n[+] Evaluating latest decision bar for trading signal...")
    eval_idx = len(ltf_series) - 1
    signal = strategy.generate_signal(ltf_series, eval_idx, include_blocked_preview=True)

    if signal is not None:
        print(f"\n    Signal Direction  : {signal.direction.label}")
        print(f"    Confidence Score  : {signal.score:.1f} / 100 (Threshold >= {strategy.get_parameters()['min_score']})")
        print(f"    Reference Price   : ${ltf_series[eval_idx].close:,.2f}")
        if signal.sl:
            print(f"    Stop Loss (SL)    : ${signal.sl:,.2f}")
        if signal.tp:
            print(f"    Take Profit (TP)  : ${signal.tp:,.2f}")
        if signal.risk_reward:
            print(f"    Risk-Reward (R:R) : {signal.risk_reward:.2f}")
        print(f"    Confluence Factors: {', '.join(signal.reasons)}")
        if signal.metadata.get("preview_only"):
            print(f"    Status            : Filtered ({signal.indicator_values.get('blocked_by')})")
        else:
            print("    Status            : TRADE ELIGIBLE")
    else:
        print("    No signal emitted at target bar.")

    print("\n" + "=" * 65)


if __name__ == "__main__":
    main()
