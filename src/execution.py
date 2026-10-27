"""Realistic, deterministic execution simulator for multi-timeframe trading.

Enforces point-in-time constraints:
  1. Signal generation at bar close `idx` -> fill at next bar open `idx+1`.
  2. Transaction cost modeling: spread, slippage, and commission.
  3. Intrabar Stop-First execution ordering (conservative adverse fill).
  4. Real-time take-profit reanchoring to actual fill price.
  5. Dynamic trailing stop and max-hold horizon management.
"""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
import numpy as np

from src.types import (
    BarSeries,
    Candle,
    Direction,
    ExitReason,
    Position,
    Trade,
    BacktestMetrics,
    BacktestResult,
    Timeframe,
)
from src.constants import (
    DEFAULT_CAPITAL,
    DEFAULT_COMMISSION_BPS,
    DEFAULT_RISK_PER_TRADE,
    DEFAULT_SLIPPAGE_BPS,
    DEFAULT_SPREAD_BPS,
)


class BacktestEngine:
    """Quantitative backtest execution simulator."""

    def __init__(
        self,
        capital: float = DEFAULT_CAPITAL,
        slippage_bps: float = DEFAULT_SLIPPAGE_BPS,
        commission_bps: float = DEFAULT_COMMISSION_BPS,
        spread_bps: float = DEFAULT_SPREAD_BPS,
        risk_per_trade: float = DEFAULT_RISK_PER_TRADE,
        max_positions: int = 1,
        max_same_direction: int = 1,
        causal_trailing: bool = True,
        random_seed: int = 42,
    ):
        self.initial_capital = float(capital)
        self.equity = float(capital)
        self.slippage_bps = float(slippage_bps)
        self.commission_bps = float(commission_bps)
        self.spread_bps = float(spread_bps)
        self.risk_per_trade = float(risk_per_trade)
        self.max_positions = int(max_positions)
        self.max_same_direction = int(max_same_direction)
        self.causal_trailing = bool(causal_trailing)
        self.random_seed = int(random_seed)

        self.positions: List[Position] = []
        self.trades: List[Trade] = []
        self.equity_curve: List[float] = []
        self.equity_timestamps: List[datetime] = []

    def _apply_entry_cost(self, price: float, direction: Direction) -> float:
        """Apply one-way half-spread and adverse slippage to entry price."""
        total_adverse_bps = (self.spread_bps / 2.0) + self.slippage_bps
        multiplier = 1.0 + (total_adverse_bps / 10_000.0) if direction == Direction.LONG else 1.0 - (total_adverse_bps / 10_000.0)
        return price * multiplier

    def _apply_exit_cost(self, price: float, direction: Direction) -> float:
        """Apply one-way half-spread and adverse slippage to exit price."""
        total_adverse_bps = (self.spread_bps / 2.0) + self.slippage_bps
        # Exiting LONG is a SELL (price decreases), exiting SHORT is a BUY (price increases)
        multiplier = 1.0 - (total_adverse_bps / 10_000.0) if direction == Direction.LONG else 1.0 + (total_adverse_bps / 10_000.0)
        return price * multiplier

    def _close_position(
        self,
        pos: Position,
        exit_base_price: float,
        exit_time: datetime,
        reason: str,
    ) -> None:
        """Close an active position, charge commission, update equity, and record Trade."""
        fill_exit_price = self._apply_exit_cost(exit_base_price, pos.direction)
        direction_sign = 1.0 if pos.direction == Direction.LONG else -1.0

        gross_pnl = (fill_exit_price - pos.entry_price) * pos.current_size * direction_sign
        entry_notional = pos.entry_price * pos.current_size
        exit_notional = fill_exit_price * pos.current_size

        roundtrip_commission = (entry_notional + exit_notional) * (self.commission_bps / 10_000.0)
        net_pnl = gross_pnl - roundtrip_commission

        self.equity += net_pnl
        return_pct = net_pnl / self.initial_capital

        trade = Trade(
            symbol=pos.symbol,
            direction=pos.direction,
            entry_time=pos.entry_time,
            entry_price=pos.entry_price,
            exit_time=exit_time,
            exit_price=fill_exit_price,
            sl=pos.stop_loss,
            tp=pos.take_profit,
            pnl=net_pnl,
            return_pct=return_pct,
            exit_reason=reason,
            hold_bars=pos.bars_held,
            size=pos.current_size,
        )
        self.trades.append(trade)

    def _update_trailing_stops(self, candle: Candle) -> None:
        """Update trailing stops based on the newly formed candle."""
        for pos in self.positions:
            if pos.direction == Direction.LONG:
                if candle.high > pos.highest_since_entry:
                    pos.highest_since_entry = candle.high
                if (
                    pos.trail_activation_price is not None
                    and pos.trail_distance is not None
                    and candle.high >= pos.trail_activation_price
                ):
                    new_sl = candle.high - pos.trail_distance
                    if new_sl > pos.stop_loss:
                        pos.stop_loss = new_sl
                        pos.trailing_stop_active = True
            else:
                if candle.low < pos.lowest_since_entry:
                    pos.lowest_since_entry = candle.low
                if (
                    pos.trail_activation_price is not None
                    and pos.trail_distance is not None
                    and candle.low <= pos.trail_activation_price
                ):
                    new_sl = candle.low + pos.trail_distance
                    if new_sl < pos.stop_loss:
                        pos.stop_loss = new_sl
                        pos.trailing_stop_active = True

    def _check_exits(self, candle: Candle) -> None:
        """Evaluate Stop-Loss (with Stop-First priority), Take-Profit, and Time Exits."""
        remaining: List[Position] = []

        for pos in self.positions:
            pos.bars_held += 1
            is_closed = False

            if pos.direction == Direction.LONG:
                stop_hit = candle.low <= pos.stop_loss
                tp_hit = candle.high >= pos.take_profit

                # Conservative Stop-First intrabar priority
                if stop_hit:
                    base_price = candle.open if candle.open <= pos.stop_loss else pos.stop_loss
                    reason = ExitReason.TRAILING_STOP.value if pos.trailing_stop_active else ExitReason.STOP_LOSS.value
                    self._close_position(pos, base_price, candle.timestamp, reason)
                    is_closed = True
                elif tp_hit:
                    self._close_position(pos, pos.take_profit, candle.timestamp, ExitReason.TAKE_PROFIT.value)
                    is_closed = True

            elif pos.direction == Direction.SHORT:
                stop_hit = candle.high >= pos.stop_loss
                tp_hit = candle.low <= pos.take_profit

                if stop_hit:
                    base_price = candle.open if candle.open >= pos.stop_loss else pos.stop_loss
                    reason = ExitReason.TRAILING_STOP.value if pos.trailing_stop_active else ExitReason.STOP_LOSS.value
                    self._close_position(pos, base_price, candle.timestamp, reason)
                    is_closed = True
                elif tp_hit:
                    self._close_position(pos, pos.take_profit, candle.timestamp, ExitReason.TAKE_PROFIT.value)
                    is_closed = True

            # Max hold time exit if still open
            if not is_closed:
                if pos.bars_held >= pos.max_hold:
                    self._close_position(pos, candle.close, candle.timestamp, ExitReason.TIME_EXIT.value)
                    is_closed = True

            if not is_closed:
                remaining.append(pos)

        self.positions = remaining

    def run(
        self,
        series: BarSeries,
        signal_fn: Callable[[BarSeries, int], Any],
        warmup_bars: int = 50,
        on_entry: Optional[Callable[[BarSeries, int, Position, Any], None]] = None,
    ) -> BacktestResult:
        """Run point-in-time sequential backtest."""
        candles = series.candles
        n = len(candles)
        if n < warmup_bars + 2:
            raise ValueError(f"Insufficient bars for backtest: {n} < {warmup_bars + 2}")

        self.equity = self.initial_capital
        self.positions = []
        self.trades = []
        self.equity_curve = [self.initial_capital]
        self.equity_timestamps = [candles[warmup_bars].timestamp]

        for idx in range(warmup_bars, n):
            current = candles[idx]

            # 1. Update position state and check exits for current bar
            if self.causal_trailing:
                self._check_exits(current)
                self._update_trailing_stops(current)
            else:
                self._update_trailing_stops(current)
                self._check_exits(current)

            # 2. Check for new signals if capacity exists
            if len(self.positions) < self.max_positions and idx + 1 < n:
                signal = signal_fn(series, idx)

                if signal is not None and signal.direction != Direction.NEUTRAL:
                    if not signal.metadata.get("preview_only", False):
                        entry_candle = candles[idx + 1]
                        fill_price = self._apply_entry_cost(entry_candle.open, signal.direction)

                        sl = signal.metadata.get("sl")
                        risk_reward = signal.metadata.get("risk_reward", 2.0)
                        max_hold = signal.metadata.get("max_hold", 20)

                        if sl is not None:
                            valid_sl = (
                                (signal.direction == Direction.LONG and fill_price > sl)
                                or (signal.direction == Direction.SHORT and fill_price < sl)
                            )
                            if valid_sl:
                                # Re-anchor Take Profit to actual entry fill price
                                if signal.direction == Direction.LONG:
                                    tp = fill_price + (fill_price - sl) * risk_reward
                                else:
                                    tp = fill_price - (sl - fill_price) * risk_reward

                                # Risk-based position sizing
                                stop_distance = abs(fill_price - sl)
                                risk_amount = self.equity * self.risk_per_trade
                                size_units = risk_amount / stop_distance if stop_distance > 1e-12 else 0.0

                                if size_units > 0:
                                    pos = Position(
                                        symbol=series.symbol,
                                        direction=signal.direction,
                                        entry_time=entry_candle.timestamp,
                                        entry_price=fill_price,
                                        current_size=size_units,
                                        stop_loss=float(sl),
                                        take_profit=float(tp),
                                        entry_score=signal.score,
                                        strategy_name=signal.strategy_name,
                                        max_hold=max_hold,
                                    )
                                    self.positions.append(pos)
                                    if on_entry is not None:
                                        on_entry(series, idx, pos, None)

            # 3. Mark to market equity
            unrealized_pnl = 0.0
            for pos in self.positions:
                dir_mult = 1.0 if pos.direction == Direction.LONG else -1.0
                unrealized_pnl += (current.close - pos.entry_price) * pos.current_size * dir_mult

            self.equity_curve.append(self.equity + unrealized_pnl)
            self.equity_timestamps.append(current.timestamp)

        # Close any lingering positions on the final bar
        final_candle = candles[-1]
        for pos in list(self.positions):
            self._close_position(pos, final_candle.close, final_candle.timestamp, ExitReason.END_OF_DATA.value)
        self.positions.clear()

        # Compile metrics
        metrics = self._calculate_metrics(series.timeframe)
        return BacktestResult(
            metrics=metrics,
            trades=self.trades,
            equity_curve=self.equity_curve,
            equity_timestamps=self.equity_timestamps,
        )

    def _calculate_metrics(self, timeframe: Timeframe) -> BacktestMetrics:
        """Compute performance and risk metrics."""
        total_trades = len(self.trades)
        if total_trades == 0:
            return BacktestMetrics(
                total_trades=0,
                win_rate=0.0,
                profit_factor=0.0,
                net_pnl=0.0,
                return_pct=0.0,
                max_drawdown_pct=0.0,
                sharpe_ratio=0.0,
                avg_trade_return=0.0,
                expectancy=0.0,
            )

        pnls = [t.pnl for t in self.trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        win_rate = len(wins) / total_trades
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (99.0 if gross_profit > 0 else 0.0)
        net_pnl = sum(pnls)
        return_pct = net_pnl / self.initial_capital

        # Maximum Drawdown
        peak = self.initial_capital
        max_dd = 0.0
        for eq in self.equity_curve:
            if eq > peak:
                peak = eq
            dd = (peak - eq) / peak if peak > 0 else 0.0
            if dd > max_dd:
                max_dd = dd

        # Annualized Sharpe Ratio
        eq_arr = np.array(self.equity_curve, dtype=float)
        bar_returns = np.diff(eq_arr) / eq_arr[:-1]
        if len(bar_returns) > 1 and np.std(bar_returns) > 1e-12:
            minutes = timeframe.minutes()
            bars_per_year = (365.25 * 24 * 60) / minutes
            sharpe_ratio = float((np.mean(bar_returns) / np.std(bar_returns)) * math.sqrt(bars_per_year))
        else:
            sharpe_ratio = 0.0

        avg_trade_return = float(np.mean([t.return_pct for t in self.trades]))
        expectancy = float(np.mean(pnls))

        return BacktestMetrics(
            total_trades=total_trades,
            win_rate=win_rate,
            profit_factor=profit_factor,
            net_pnl=net_pnl,
            return_pct=return_pct,
            max_drawdown_pct=max_dd,
            sharpe_ratio=sharpe_ratio,
            avg_trade_return=avg_trade_return,
            expectancy=expectancy,
        )
