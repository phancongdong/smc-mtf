"""Comprehensive test suite for SMC Multi-Timeframe Strategy mechanics and execution."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
import numpy as np

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.types import (
    AssetClass,
    BarSeries,
    Candle,
    Direction,
    MarketRegime,
    Position,
    Signal,
    Timeframe,
)
from src.strategy import SMCMultiTimeframeStrategy
from src.indicators import ATR, EMA, RSI, SMA
from src.market_structure import detect_market_structure
from src.zones import detect_order_blocks, detect_fvg, check_zone_rejection
from src.liquidity import detect_liquidity_sweeps, calc_discount_premium
from src.microstructure import detect_reversal_candle, check_ltf_momentum
from src.data_loader import load_parquet, parse_timeframe


T0 = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _c(i: int, o: float, h: float, l: float, close: float, v: float = 1000.0) -> Candle:
    """Helper to create test candle."""
    return Candle(T0 + timedelta(hours=i), float(o), float(h), float(l), float(close), float(v))


def _structure_fixture(final_close: float) -> list[Candle]:
    highs = [10, 11, 15, 12, 11, 13, 17, 14, 13, 14, 15, max(16, final_close + 0.2)]
    lows = [8, 9, 10, 9, 7, 10, 12, 11, 9, 11, 12, min(10, final_close - 0.2)]
    out = []
    for i, (h, l) in enumerate(zip(highs, lows)):
        close = final_close if i == len(highs) - 1 else (h + l) / 2
        out.append(_c(i, close, h, l, close))
    return out


# ─── Market Structure Tests ──────────────────────────────────────────

def test_market_structure_bos_requires_close_beyond_latest_confirmed_swing():
    below = detect_market_structure(_structure_fixture(16.5), 11)
    above = detect_market_structure(_structure_fixture(17.5), 11)
    assert below["trend"] == "UPTREND"
    assert below["bos_direction"] == "NONE"
    assert above["bos_direction"] == "BULLISH"


def test_bos_is_a_crossing_event_not_repeated_above_level():
    candles = _structure_fixture(18.0)
    candles[10] = _c(10, 17.5, 18, 12, 17.5)
    result = detect_market_structure(candles, 11)
    assert result["bos_direction"] == "NONE"


def test_market_structure_bearish_choch_has_direction():
    result = detect_market_structure(_structure_fixture(8.5), 11)
    assert result["choch"] is True
    assert result["choch_direction"] == "BEARISH"
    assert result["trend"] == "DOWNTREND"


# ─── Zones & Rejection Tests ─────────────────────────────────────────

def test_zone_rejection_requires_large_directional_wick():
    base = _c(0, 100, 101, 99.5, 100)
    prior = _c(1, 100, 101, 99.5, 100)
    long_wick = _c(2, 100, 101, 95, 100.8)
    small_wick = _c(2, 99.8, 101, 99.5, 100.8)
    assert check_zone_rejection([base, prior, long_wick], 2, 101, 99, "LONG") is True
    assert check_zone_rejection([base, prior, small_wick], 2, 101, 99, "LONG") is False


def test_newly_created_zone_cannot_reject_itself():
    candles = [_c(0, 100, 101, 99, 100), _c(1, 100, 101, 99, 100), _c(2, 100, 106, 99, 105)]
    assert check_zone_rejection(candles, 2, 105, 101, "LONG", zone_idx=2) is False


def test_fvg_first_revisit_active_but_old_mitigation_is_not():
    base = [
        _c(0, 99, 100, 98, 99),
        _c(1, 100, 104, 99, 103),
        _c(2, 105, 108, 105, 107),  # bullish FVG 100..105
        _c(3, 107, 109, 106, 108),
        _c(4, 108, 110, 106, 109),
        _c(5, 106, 108, 102, 107),  # first revisit now
    ]
    current = [z for z in detect_fvg(base, 5) if z["idx"] == 2][0]
    assert current["active"] is True and current["first_touch_idx"] == 5

    old = list(base)
    old[3] = _c(3, 106, 108, 103, 107)  # mitigated two bars before decision
    stale = [z for z in detect_fvg(old, 5) if z["idx"] == 2][0]
    assert stale["mitigated"] is True and stale["active"] is False


def test_order_block_requires_displacement_close_through_prior_range():
    candles = [
        _c(0, 100, 101, 99, 100),
        _c(1, 100, 102, 99, 101),
        _c(2, 101, 103, 100, 102),
        _c(3, 102, 103, 100, 100.5),  # last down candle
        _c(4, 100.5, 106, 100, 105),  # displacement closes > prior highs
        _c(5, 106, 107, 105.5, 106.5),
    ]
    obs = detect_order_blocks(candles, 5)
    bullish = [z for z in obs if z["type"] == "BULLISH"]
    assert bullish and bullish[-1]["idx"] == 3 and bullish[-1]["active"] is True

    no_break = list(candles)
    no_break[4] = _c(4, 100.5, 103, 100, 102.5)
    assert not [z for z in detect_order_blocks(no_break, 5) if z["idx"] == 3]


# ─── Liquidity & Retracement Tests ───────────────────────────────────

def test_liquidity_sweep_requires_two_closes_back_inside():
    candles = [_c(i, 100, 101, 99.5, 100) for i in range(5)]
    candles[1] = _c(1, 100, 100.5, 98, 99)
    candles[2] = _c(2, 99, 101, 98.8, 100.5)
    one = detect_liquidity_sweeps(candles, 2, {"swing_lows": [{"price": 99}], "swing_highs": []})
    two = detect_liquidity_sweeps(candles, 3, {"swing_lows": [{"price": 99}], "swing_highs": []})
    assert one["bullish_sweep"] is False
    assert two["bullish_sweep"] is True


def test_premium_discount_uses_structural_618_786_zones():
    structure = {"swing_highs": [{"price": 200}], "swing_lows": [{"price": 100}]}
    zones = calc_discount_premium([_c(i, 150, 160, 140, 150) for i in range(21)], 20, structure)
    assert zones["deep_discount"] == pytest.approx(121.4)
    assert zones["discount_618_buy"] == pytest.approx(138.2)
    assert zones["premium_618"] == pytest.approx(161.8)
    assert zones["deep_premium"] == pytest.approx(178.6)


def test_premium_discount_uses_chronological_impulse_pair():
    structure = {
        "trend": "UPTREND",
        "swing_highs": [{"idx": 10, "price": 200}],
        "swing_lows": [{"idx": 5, "price": 100}, {"idx": 15, "price": 150}],
    }
    zones = calc_discount_premium([_c(i, 150, 210, 90, 150) for i in range(21)], 20, structure)
    assert zones["low"] == 100
    assert zones["high"] == 200


# ─── Risk Geometry & Position Target Tests ─────────────────────────

def test_position_risk_reward_target_geometry():
    entry_price = 110.0
    stop_loss = 90.0
    risk_reward = 2.0
    take_profit = entry_price + risk_reward * (entry_price - stop_loss)
    pos = Position(
        symbol="TEST",
        direction=Direction.LONG,
        entry_time=T0,
        entry_price=entry_price,
        current_size=1.0,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )
    assert pos.take_profit == pytest.approx(150.0)
    assert pos.highest_since_entry == 110.0
    assert pos.lowest_since_entry == 110.0


def test_trend_label_without_bos_or_choch_cannot_emit_signal(monkeypatch):
    ltf = BarSeries([_c(i, 100, 102, 98, 101) for i in range(101)], "TEST", Timeframe.H1, AssetClass.CRYPTO)
    htf = BarSeries([Candle(T0 + timedelta(hours=4 * i), 100, 102, 98, 101, 1000) for i in range(20)],
                    "TEST", Timeframe.H4, AssetClass.CRYPTO)
    s = SMCMultiTimeframeStrategy()
    s._htf_series = htf
    s._htf_atr_cache = np.ones(len(htf))
    structure = {
        "trend": "UPTREND", "bos": False, "choch": False,
        "bos_direction": "NONE", "choch_direction": "NONE",
        "swing_highs": [{"price": 102}], "swing_lows": [{"price": 95}],
    }
    monkeypatch.setattr(s, "_detect_market_structure", lambda *a: structure)
    monkeypatch.setattr(s, "_detect_order_blocks", lambda *a: [
        {"type": "BULLISH", "idx": 1, "top": 100, "bottom": 95, "active": True}])
    monkeypatch.setattr(s, "_detect_fvg", lambda *a: [
        {"type": "BULLISH", "idx": 1, "top": 100, "bottom": 99, "active": True}])
    monkeypatch.setattr(s, "_check_zone_rejection", lambda *a: True)
    monkeypatch.setattr(s, "_calc_discount_premium", lambda *a: {
        "discount_618_buy": 102, "deep_discount": 90, "premium_618": 200, "deep_premium": 210})
    monkeypatch.setattr(s, "_detect_liquidity_sweeps", lambda *a: {"bullish_sweep": True, "bearish_sweep": False})
    monkeypatch.setattr(s, "_detect_reversal_candle", lambda *a: {"reversal": True, "bullish": True, "bearish": False, "rej_type": "PIN_BAR"})
    monkeypatch.setattr(s, "_check_ltf_momentum", lambda *a: 1)

    assert s.generate_signal(ltf, 100) is None
    blocked_preview = s.generate_signal(
        ltf,
        100,
        min_score_override=1,
        include_blocked_preview=True,
    )
    assert blocked_preview is not None
    assert blocked_preview.metadata["preview_only"] is True
    assert blocked_preview.indicator_values["effective_score"] == 0
    assert "NO_BOS_CHOCH" in blocked_preview.indicator_values["blocked_by"]

    structure["bos"] = True
    structure["bos_direction"] = "BULLISH"
    signal = s.generate_signal(ltf, 100)
    assert signal.direction is Direction.LONG
    assert signal.timestamp == ltf.candles[100].timestamp + timedelta(hours=1)
    assert signal.metadata["risk_reward"] == pytest.approx(2.0)

    monkeypatch.setattr(s, "_check_zone_rejection", lambda *a: False)
    assert s.generate_signal(ltf, 100) is None

    s.set_parameters({"require_poi_confirmation": False})
    signal_without_poi_gate = s.generate_signal(ltf, 100)
    assert signal_without_poi_gate is not None
    assert signal_without_poi_gate.direction is Direction.LONG
    assert signal_without_poi_gate.indicator_values["ob_rej"] == 0
    assert signal_without_poi_gate.indicator_values["fvg_rej"] == 0


def _confirmation_gate_fixture(monkeypatch, structure_confirmed: bool, poi_confirmed: bool):
    ltf = BarSeries(
        [_c(i, 100, 102, 98, 101) for i in range(101)],
        "TEST",
        Timeframe.H1,
        AssetClass.CRYPTO,
    )
    htf = BarSeries(
        [Candle(T0 + timedelta(hours=4 * i), 100, 102, 98, 101, 1000) for i in range(20)],
        "TEST",
        Timeframe.H4,
        AssetClass.CRYPTO,
    )
    strategy = SMCMultiTimeframeStrategy()
    strategy._htf_series = htf
    strategy._htf_atr_cache = np.ones(len(htf))
    monkeypatch.setattr(strategy, "_detect_market_structure", lambda *a: {
        "trend": "UPTREND",
        "bos": structure_confirmed,
        "choch": False,
        "bos_direction": "BULLISH" if structure_confirmed else "NONE",
        "choch_direction": "NONE",
        "swing_highs": [{"price": 102}],
        "swing_lows": [{"price": 95}],
    })
    monkeypatch.setattr(strategy, "_detect_order_blocks", lambda *a: [{
        "type": "BULLISH",
        "idx": 1,
        "top": 100,
        "bottom": 95,
        "active": True,
    }])
    monkeypatch.setattr(strategy, "_detect_fvg", lambda *a: [])
    monkeypatch.setattr(strategy, "_check_zone_rejection", lambda *a: poi_confirmed)
    monkeypatch.setattr(strategy, "_calc_discount_premium", lambda *a: {
        "discount_618_buy": 102,
        "deep_discount": 90,
        "premium_618": 200,
        "deep_premium": 210,
    })
    monkeypatch.setattr(strategy, "_detect_liquidity_sweeps", lambda *a: {
        "bullish_sweep": False,
        "bearish_sweep": False,
    })
    monkeypatch.setattr(strategy, "_detect_reversal_candle", lambda *a: {
        "reversal": True,
        "bullish": True,
        "bearish": False,
        "rej_type": "PIN_BAR",
    })
    monkeypatch.setattr(strategy, "_check_ltf_momentum", lambda *a: 1)
    return strategy, ltf


@pytest.mark.parametrize(
    ("structure_confirmed", "poi_confirmed"),
    [(True, False), (False, True)],
)
def test_either_confirmation_mode_accepts_one_gate(
    monkeypatch, structure_confirmed, poi_confirmed,
):
    strategy, ltf = _confirmation_gate_fixture(
        monkeypatch, structure_confirmed, poi_confirmed,
    )
    strategy.set_parameters({"confirmation_mode": "either"})

    signal = strategy.generate_signal(ltf, 100)
    assert signal is not None
    assert signal.direction is Direction.LONG
    assert signal.indicator_values["confirmation_mode"] == "either"


def test_either_confirmation_mode_blocks_when_both_gates_are_missing(monkeypatch):
    strategy, ltf = _confirmation_gate_fixture(monkeypatch, False, False)
    strategy.set_parameters({"confirmation_mode": "either"})

    assert strategy.generate_signal(ltf, 100) is None
    preview = strategy.generate_signal(
        ltf,
        100,
        min_score_override=1,
        include_blocked_preview=True,
    )
    assert preview is not None
    assert preview.indicator_values["effective_score"] == 0
    assert preview.indicator_values["blocked_by"] == "NO_BOS_CHOCH;NO_POI_REJECTION"


def test_confirmation_mode_rejects_unknown_value():
    with pytest.raises(ValueError, match="confirmation_mode"):
        SMCMultiTimeframeStrategy().set_parameters({"confirmation_mode": "unknown"})


def test_tp_atr_multiplier_controls_risk_reward(monkeypatch):
    ltf = BarSeries([_c(i, 100, 102, 98, 101) for i in range(101)], "TEST", Timeframe.H1, AssetClass.CRYPTO)
    htf = BarSeries([Candle(T0 + timedelta(hours=4 * i), 100, 102, 98, 101, 1000) for i in range(30)],
                    "TEST", Timeframe.H4, AssetClass.CRYPTO)
    s = SMCMultiTimeframeStrategy()
    s._htf_series = htf
    s._htf_atr_cache = np.ones(len(htf))
    s.set_parameters({"sl_atr_mult": 1.5, "tp_atr_mult": 6.0})
    monkeypatch.setattr(s, "_detect_market_structure", lambda *a: {
        "trend": "UPTREND", "bos": True, "choch": False,
        "bos_direction": "BULLISH", "choch_direction": "NONE",
        "swing_highs": [{"price": 102}], "swing_lows": [{"price": 95}],
    })
    monkeypatch.setattr(s, "_detect_order_blocks", lambda *a: [
        {"type": "BULLISH", "idx": 1, "top": 100, "bottom": 95, "active": True}])
    monkeypatch.setattr(s, "_detect_fvg", lambda *a: [])
    monkeypatch.setattr(s, "_check_zone_rejection", lambda *a: True)
    monkeypatch.setattr(s, "_calc_discount_premium", lambda *a: {})
    monkeypatch.setattr(s, "_detect_liquidity_sweeps", lambda *a: {"bullish_sweep": True, "bearish_sweep": False})
    monkeypatch.setattr(s, "_detect_reversal_candle", lambda *a: {"reversal": True, "bullish": True, "bearish": False, "rej_type": "PIN_BAR"})
    monkeypatch.setattr(s, "_check_ltf_momentum", lambda *a: 1)
    assert s.generate_signal(ltf, 100).metadata["risk_reward"] == pytest.approx(4.0)


# ─── Indicators & Point-in-Time Synchronization Tests ────────────────

def test_indicators_ema_sma_atr_rsi_vectorized():
    closes = np.array([10.0, 11.0, 12.0, 13.0, 14.0, 15.0, 16.0, 15.0, 14.0, 13.0, 12.0])
    ema_vals = EMA.compute(closes, period=5)
    sma_vals = SMA.compute(closes, period=5)
    assert np.isnan(ema_vals[0])
    assert ema_vals[4] == pytest.approx(12.0)
    assert sma_vals[4] == pytest.approx(12.0)

    rsi_vals = RSI.compute(closes, period=5)
    assert not np.isnan(rsi_vals[-1])
    assert 0 <= rsi_vals[-1] <= 100


def test_causal_htf_alignment_zero_lookahead():
    # 4h candles start at hour 0, 4, 8, 12...
    htf_candles = [Candle(T0 + timedelta(hours=4 * i), 100, 105, 95, 100, 1000) for i in range(10)]
    htf = BarSeries(htf_candles, "BTC", Timeframe.H4, AssetClass.CRYPTO)
    s = SMCMultiTimeframeStrategy()
    s.set_htf_data(htf)

    # At hour 3.99, candle 0 (hours 0-4) is NOT closed yet -> index is -1
    assert s._find_htf_idx(T0 + timedelta(hours=3, minutes=59)) == -1
    # At hour 4.00, candle 0 is closed -> index is 0
    assert s._find_htf_idx(T0 + timedelta(hours=4)) == 0
    # At hour 7.59, candle 0 is still the latest closed candle -> index is 0
    assert s._find_htf_idx(T0 + timedelta(hours=7, minutes=59)) == 0
    # At hour 8.00, candle 1 is closed -> index is 1
    assert s._find_htf_idx(T0 + timedelta(hours=8)) == 1
