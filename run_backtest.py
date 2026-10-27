#!/usr/bin/env python3
"""Command-Line Interface for SMC Multi-Timeframe Strategy Backtest.

Executes point-in-time multi-timeframe backtesting across in-sample (IS)
and out-of-sample (OOS) splits with institutional transaction costs.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.constants import ASSET_FEES, DEFAULT_CAPITAL, DEFAULT_RISK_PER_TRADE
from src.data_loader import infer_asset_class, load_dataset, parse_timeframe
from src.execution import BacktestEngine
from src.strategy import SMCMultiTimeframeStrategy
from src.types import AssetClass, BarSeries, Timeframe


def format_metrics_table(title: str, metrics: Any, num_trades: int) -> str:
    """Format performance metrics into a clean terminal report."""
    lines = [
        f"\n{'='*65}",
        f"  {title}",
        f"{'='*65}",
        f"  Total Closed Trades    : {metrics.total_trades}",
        f"  Win Rate               : {metrics.win_rate * 100:.2f}%",
        f"  Profit Factor (PF)     : {metrics.profit_factor:.3f}",
        f"  Net Realized PnL       : ${metrics.net_pnl:,.2f}",
        f"  Total Return           : {metrics.return_pct * 100:.2f}%",
        f"  Max Drawdown (DD)      : {metrics.max_drawdown_pct * 100:.2f}%",
        f"  Annualized Sharpe      : {metrics.sharpe_ratio:.3f}",
        f"  Average Trade Return   : {metrics.avg_trade_return * 100:.2f}%",
        f"  Expectancy Per Trade   : ${metrics.expectancy:,.2f}",
        f"{'='*65}",
    ]
    return "\n".join(lines)


def run_cli():
    parser = argparse.ArgumentParser(
        description="Run institutional backtest for SMC Multi-Timeframe Strategy.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--symbol", type=str, default="SOLUSDT", help="Symbol to backtest (e.g. SOLUSDT, ETHUSDT)")
    parser.add_argument("--htf", type=str, default="H4", help="Higher Timeframe (e.g. H4, D1)")
    parser.add_argument("--ltf", type=str, default="H1", help="Lower Timeframe (e.g. H1, M15)")
    parser.add_argument(
        "--confirmation",
        type=str,
        default="both",
        choices=["both", "either", "structure", "poi"],
        help="Gate confirmation mode",
    )
    parser.add_argument("--min-score", type=int, default=50, help="Minimum confluence score (0-100)")
    parser.add_argument("--sl-atr", type=float, default=1.5, help="Stop loss ATR multiplier")
    parser.add_argument("--tp-atr", type=float, default=3.0, help="Take profit ATR multiplier")
    parser.add_argument("--max-hold", type=int, default=20, help="Maximum bars to hold position")
    parser.add_argument("--capital", type=float, default=DEFAULT_CAPITAL, help="Starting capital")
    parser.add_argument("--risk", type=float, default=DEFAULT_RISK_PER_TRADE, help="Risk fraction per trade")
    parser.add_argument("--split", type=float, default=0.8, help="In-sample fraction (0.0 - 1.0)")
    parser.add_argument("--output", type=str, default=None, help="Optional JSON output filepath")

    args = parser.parse_args()

    print(f"\n[+] Loading historical datasets for {args.symbol}...")
    htf_tf = parse_timeframe(args.htf)
    ltf_tf = parse_timeframe(args.ltf)

    try:
        htf_series = load_dataset(args.symbol, args.htf)
        ltf_series = load_dataset(args.symbol, args.ltf)
    except FileNotFoundError as err:
        print(f"[-] Data loading failed: {err}")
        sys.exit(1)

    print(f"    HTF ({htf_tf.value}) bars: {len(htf_series):,}")
    print(f"    LTF ({ltf_tf.value}) bars: {len(ltf_series):,}")

    asset_cat = infer_asset_class(args.symbol)
    fee_profile = ASSET_FEES.get(asset_cat.value, ASSET_FEES["CRYPTO"])
    print(f"    Asset Category : {asset_cat.value}")
    print(f"    Applied Costs  : Spread {fee_profile['spread_bps']} bps | Comm {fee_profile['commission_bps']} bps | Slip {fee_profile['slippage_bps']} bps")

    # Initialize Strategy
    strategy = SMCMultiTimeframeStrategy(
        confirmation_mode=args.confirmation,
        min_score=args.min_score,
        sl_atr_mult=args.sl_atr,
        tp_atr_mult=args.tp_atr,
        max_hold_bars=args.max_hold,
    )
    strategy.set_htf_data(htf_series)
    strategy.set_ltf_data(ltf_series)

    # In-Sample and Out-of-Sample Split
    total_bars = len(ltf_series)
    split_idx = int(total_bars * args.split)

    is_series = ltf_series.slice(0, split_idx)
    oos_series = ltf_series.slice(split_idx, total_bars)

    print(f"\n[+] Backtest Partition:")
    print(f"    In-Sample (IS)      : {len(is_series):,} bars ({is_series[0].timestamp.date()} to {is_series[-1].timestamp.date()})")
    print(f"    Out-of-Sample (OOS) : {len(oos_series):,} bars ({oos_series[0].timestamp.date()} to {oos_series[-1].timestamp.date()})")

    # Execute In-Sample
    strategy.set_ltf_data(is_series)
    engine_is = BacktestEngine(
        capital=args.capital,
        slippage_bps=fee_profile["slippage_bps"],
        commission_bps=fee_profile["commission_bps"],
        spread_bps=fee_profile["spread_bps"],
        risk_per_trade=args.risk,
    )
    result_is = engine_is.run(is_series, signal_fn=strategy.generate_signal, warmup_bars=strategy.get_warmup_bars())
    print(format_metrics_table(f"IN-SAMPLE (IS) RESULTS -- {args.symbol} {args.htf}/{args.ltf}", result_is.metrics, len(result_is.trades)))

    # Execute Out-of-Sample
    strategy.set_ltf_data(oos_series)
    engine_oos = BacktestEngine(
        capital=args.capital,
        slippage_bps=fee_profile["slippage_bps"],
        commission_bps=fee_profile["commission_bps"],
        spread_bps=fee_profile["spread_bps"],
        risk_per_trade=args.risk,
    )
    result_oos = engine_oos.run(oos_series, signal_fn=strategy.generate_signal, warmup_bars=strategy.get_warmup_bars())
    print(format_metrics_table(f"OUT-OF-SAMPLE (OOS) RESULTS -- {args.symbol} {args.htf}/{args.ltf}", result_oos.metrics, len(result_oos.trades)))

    # Save output if requested
    if args.output:
        out_payload = {
            "symbol": args.symbol,
            "htf": args.htf,
            "ltf": args.ltf,
            "confirmation_mode": args.confirmation,
            "parameters": strategy.get_parameters(),
            "in_sample": result_is.metrics.to_dict(),
            "out_of_sample": result_oos.metrics.to_dict(),
            "is_trade_count": len(result_is.trades),
            "oos_trade_count": len(result_oos.trades),
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(out_payload, f, indent=2)
        print(f"\n[+] Results saved to: {args.output}")


if __name__ == "__main__":
    run_cli()
