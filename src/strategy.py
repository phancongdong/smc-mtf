"""Smart Money Concepts (SMC) Multi-Timeframe Strategy Engine.

Integrates Higher-Timeframe (HTF) market structure, institutional zones,
liquidity sweeps, and Lower-Timeframe (LTF) confirmation gates.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import numpy as np

from src.types import (
    AssetClass,
    BarSeries,
    Candle,
    Direction,
    MarketRegime,
    Signal,
    Timeframe,
)
from src.constants import (
    DEFAULT_CONFIRMATION_MODE,
    DEFAULT_FVG_MAX_BARS,
    DEFAULT_HTF_BOS_WEIGHT,
    DEFAULT_HTF_DISCOUNT_WEIGHT,
    DEFAULT_HTF_FVG_WEIGHT,
    DEFAULT_HTF_OB_WEIGHT,
    DEFAULT_HTF_STRUCTURE_WEIGHT,
    DEFAULT_LOOKBACK_MSB,
    DEFAULT_LOOKBACK_OB,
    DEFAULT_LTF_MOMENTUM_WEIGHT,
    DEFAULT_LTF_REVERSAL_WEIGHT,
    DEFAULT_LTF_SWEEP_WEIGHT,
    DEFAULT_MAX_HOLD_BARS,
    DEFAULT_MIN_SCORE,
    DEFAULT_SL_ATR_MULT,
    DEFAULT_TP_ATR_MULT,
    DEFAULT_WARMUP_BARS,
    SMC_MAX_RISK_REWARD,
    SMC_MAX_SL_ATR_MULT,
    SMC_MAX_TP_ATR_MULT,
    SMC_MIN_RISK_REWARD,
    SMC_MIN_SL_ATR_MULT,
    SMC_MIN_STOP_DISTANCE_ATR,
    SMC_MIN_TP_ATR_MULT,
)
from src.indicators import ATR, EMA, RSI, SMA
from src.market_structure import detect_market_structure
from src.zones import detect_order_blocks, detect_fvg, check_zone_rejection
from src.liquidity import detect_liquidity_sweeps, calc_discount_premium
from src.microstructure import detect_reversal_candle, check_ltf_momentum


class SMCMultiTimeframeStrategy:
    """Smart Money Concepts Multi-Timeframe Strategy (v2).

    Operational rules:
      1. Structural trend & continuation (BOS) / reversal (CHoCH) point-in-time confirmation.
      2. POI (Order Block / Fair Value Gap) touch + directional rejection wick response.
      3. Deep institutional Fibonacci retracement (61.8% - 78.6%).
      4. Liquidity sweeps beyond swing points with 2-bar close confirmation.
      5. Lower-timeframe candlestick pattern and momentum alignment.
    """

    CONFIRMATION_MODES = {"both", "either", "structure", "poi"}

    def __init__(self, **params):
        # HTF & Lookback parameters
        self._htf_lookback_msb = params.get("htf_lookback_msb", DEFAULT_LOOKBACK_MSB)
        self._htf_lookback_ob = params.get("htf_lookback_ob", DEFAULT_LOOKBACK_OB)
        self._fvg_max_bars = params.get("fvg_max_bars", DEFAULT_FVG_MAX_BARS)
        self._min_score = params.get("min_score", DEFAULT_MIN_SCORE)
        self._max_hold_bars = params.get("max_hold_bars", DEFAULT_MAX_HOLD_BARS)
        self._sl_atr_mult = params.get("sl_atr_mult", DEFAULT_SL_ATR_MULT)
        self._tp_atr_mult = params.get("tp_atr_mult", DEFAULT_TP_ATR_MULT)
        self._require_poi_confirmation = params.get("require_poi_confirmation", True)
        self._confirmation_mode = params.get("confirmation_mode", DEFAULT_CONFIRMATION_MODE)

        # Confluence weights
        self._htf_structure_weight = params.get("htf_structure_weight", DEFAULT_HTF_STRUCTURE_WEIGHT)
        self._htf_bos_weight = params.get("htf_bos_weight", DEFAULT_HTF_BOS_WEIGHT)
        self._htf_ob_weight = params.get("htf_ob_weight", DEFAULT_HTF_OB_WEIGHT)
        self._htf_fvg_weight = params.get("htf_fvg_weight", DEFAULT_HTF_FVG_WEIGHT)
        self._htf_discount_weight = params.get("htf_discount_weight", DEFAULT_HTF_DISCOUNT_WEIGHT)
        self._ltf_sweep_weight = params.get("ltf_sweep_weight", DEFAULT_LTF_SWEEP_WEIGHT)
        self._ltf_reversal_weight = params.get("ltf_reversal_weight", DEFAULT_LTF_REVERSAL_WEIGHT)
        self._ltf_momentum_weight = params.get("ltf_momentum_weight", DEFAULT_LTF_MOMENTUM_WEIGHT)

        # HTF State & Cache
        self._htf_series: Optional[BarSeries] = None
        self._htf_atr_cache: Optional[np.ndarray] = None
        self._htf_close_times: List[datetime] = []

        # LTF Caches for sequential evaluation
        self._ltf_cache_timestamps: List[datetime] = []
        self._ltf_rsi7_cache: Optional[np.ndarray] = None
        self._ltf_ema10_cache: Optional[np.ndarray] = None
        self._ltf_ema20_cache: Optional[np.ndarray] = None
        self._ltf_volume_sma20_cache: Optional[np.ndarray] = None

    @property
    def name(self) -> str:
        return "SMC_MTF_V2"

    def get_warmup_bars(self) -> int:
        return DEFAULT_WARMUP_BARS

    def get_parameters(self) -> Dict[str, Any]:
        return {
            "htf_lookback_msb": self._htf_lookback_msb,
            "htf_lookback_ob": self._htf_lookback_ob,
            "fvg_max_bars": self._fvg_max_bars,
            "min_score": self._min_score,
            "max_hold_bars": self._max_hold_bars,
            "sl_atr_mult": self._sl_atr_mult,
            "tp_atr_mult": self._tp_atr_mult,
            "require_poi_confirmation": self._require_poi_confirmation,
            "confirmation_mode": self._confirmation_mode,
            "htf_structure_weight": self._htf_structure_weight,
            "htf_bos_weight": self._htf_bos_weight,
            "htf_ob_weight": self._htf_ob_weight,
            "htf_fvg_weight": self._htf_fvg_weight,
            "htf_discount_weight": self._htf_discount_weight,
            "ltf_sweep_weight": self._ltf_sweep_weight,
            "ltf_reversal_weight": self._ltf_reversal_weight,
            "ltf_momentum_weight": self._ltf_momentum_weight,
        }

    def set_parameters(self, params: Dict[str, Any]) -> None:
        """Update strategy parameters with strict validation."""
        confirmation_mode = params.get("confirmation_mode")
        if confirmation_mode is not None:
            confirmation_mode = str(confirmation_mode).lower()
            if confirmation_mode not in self.CONFIRMATION_MODES:
                raise ValueError(
                    f"confirmation_mode must be one of: {', '.join(sorted(self.CONFIRMATION_MODES))}"
                )

        normalized = dict(params)
        for key, lower, upper in (
            ("sl_atr_mult", SMC_MIN_SL_ATR_MULT, SMC_MAX_SL_ATR_MULT),
            ("tp_atr_mult", SMC_MIN_TP_ATR_MULT, SMC_MAX_TP_ATR_MULT),
        ):
            if key in params:
                val = float(params[key])
                if not np.isfinite(val) or not (lower <= val <= upper):
                    raise ValueError(f"{key} must be finite and within [{lower}, {upper}]")
                normalized[key] = val

        for key in [
            "htf_lookback_msb", "htf_lookback_ob", "fvg_max_bars",
            "min_score", "max_hold_bars", "sl_atr_mult", "tp_atr_mult",
            "require_poi_confirmation", "htf_structure_weight", "htf_bos_weight",
            "htf_ob_weight", "htf_fvg_weight", "htf_discount_weight",
            "ltf_sweep_weight", "ltf_reversal_weight", "ltf_momentum_weight",
        ]:
            if key in normalized:
                setattr(self, f"_{key}", normalized[key])

        if confirmation_mode is not None:
            self._confirmation_mode = confirmation_mode
        elif "require_poi_confirmation" in normalized:
            self._confirmation_mode = "both" if normalized["require_poi_confirmation"] else "structure"

    def set_htf_data(self, htf_series: BarSeries) -> None:
        """Register HTF series and precompute close timestamps and ATR."""
        self._htf_series = htf_series
        duration = htf_series.timeframe.duration
        self._htf_close_times = [c.timestamp + duration for c in htf_series.candles]
        self._htf_atr_cache = ATR.compute(htf_series, period=14)

    def set_ltf_data(self, ltf_series: BarSeries) -> None:
        """Precompute causal LTF indicator caches for rapid sequential iteration."""
        self._ltf_cache_timestamps = [c.timestamp for c in ltf_series.candles]
        self._ltf_rsi7_cache = RSI.compute(ltf_series, period=7)
        self._ltf_ema10_cache = EMA.compute(ltf_series, period=10)
        self._ltf_ema20_cache = EMA.compute(ltf_series, period=20)
        vol_arr = np.array(ltf_series.volumes, dtype=float)
        self._ltf_volume_sma20_cache = SMA.compute(vol_arr, period=20)

    def _find_htf_idx(self, ltf_timestamp: datetime) -> int:
        """Return the index of the latest strictly closed HTF candle before ltf_timestamp."""
        if self._htf_series is None:
            return -1
        series_len = len(self._htf_series.candles)
        if len(self._htf_close_times) != series_len:
            duration = self._htf_series.timeframe.duration
            self._htf_close_times = [c.timestamp + duration for c in self._htf_series.candles]
        if self._htf_atr_cache is None or len(self._htf_atr_cache) != series_len:
            self._htf_atr_cache = ATR.compute(self._htf_series, period=14)
        return bisect_right(self._htf_close_times, ltf_timestamp) - 1

    # Internal delegations to pure modules
    def _detect_market_structure(self, candles: List[Candle], idx: int) -> Dict[str, Any]:
        return detect_market_structure(candles, idx, lookback=self._htf_lookback_msb)

    def _detect_order_blocks(self, candles: List[Candle], idx: int) -> List[Dict[str, Any]]:
        return detect_order_blocks(candles, idx, lookback=self._htf_lookback_ob)

    def _detect_fvg(self, candles: List[Candle], idx: int) -> List[Dict[str, Any]]:
        return detect_fvg(candles, idx, lookback=self._fvg_max_bars)

    def _check_zone_rejection(
        self, candles: List[Candle], idx: int, zone_top: float, zone_bottom: float, direction: str, zone_idx: int = -1
    ) -> bool:
        return check_zone_rejection(candles, idx, zone_top, zone_bottom, direction, zone_idx)

    def _detect_liquidity_sweeps(self, candles: List[Candle], idx: int, structure: Dict) -> Dict[str, bool]:
        return detect_liquidity_sweeps(candles, idx, structure)

    def _calc_discount_premium(
        self, candles: List[Candle], idx: int, structure: Optional[Dict[str, Any]] = None
    ) -> Dict[str, float]:
        return calc_discount_premium(candles, idx, structure)

    def _detect_reversal_candle(self, candles: List[Candle], idx: int) -> Dict[str, Any]:
        return detect_reversal_candle(candles, idx)

    def _check_ltf_momentum(self, candles: List[Candle], idx: int, ltf_series: Optional[BarSeries] = None) -> int:
        cache_hit = (
            idx < len(self._ltf_cache_timestamps)
            and self._ltf_cache_timestamps[idx] == candles[idx].timestamp
            and self._ltf_rsi7_cache is not None
        )
        return check_ltf_momentum(
            candles,
            idx,
            ltf_series=ltf_series,
            rsi_cache=self._ltf_rsi7_cache if cache_hit else None,
            ema10_cache=self._ltf_ema10_cache if cache_hit else None,
            ema20_cache=self._ltf_ema20_cache if cache_hit else None,
            vol_sma20_cache=self._ltf_volume_sma20_cache if cache_hit else None,
        )

    def generate_signal(
        self,
        series: BarSeries,
        idx: int,
        regime: Optional[MarketRegime] = None,
        min_score_override: Optional[int] = None,
        include_blocked_preview: bool = False,
    ) -> Optional[Signal]:
        """Generate trading signal for the current candle."""
        if idx < self.get_warmup_bars():
            return None
        if self._htf_series is None or self._htf_atr_cache is None:
            return None

        candles = series.candles
        current = candles[idx]
        timestamp = current.timestamp
        decision_time = timestamp + series.timeframe.duration

        # Session filter: Commodities restricted to London (08-17 UTC) / NY (13-22 UTC)
        if series.asset_class == AssetClass.COMMODITY:
            hour_utc = decision_time.hour
            is_london = 8 <= hour_utc <= 17
            is_ny = 13 <= hour_utc <= 22
            if not (is_london or is_ny):
                return None

        # Synchronize HTF without lookahead
        htf_idx = self._find_htf_idx(decision_time)
        if htf_idx < 5:
            return None

        htf_candles = self._htf_series.candles
        htf_atr = float(self._htf_atr_cache[htf_idx])
        if not np.isfinite(htf_atr) or htf_atr <= 0:
            return None

        # ── HTF Multi-Factor Analysis ─────────────────────────────
        htf_structure = self._detect_market_structure(htf_candles, htf_idx)
        htf_obs = self._detect_order_blocks(htf_candles, htf_idx)
        htf_fvgs = self._detect_fvg(htf_candles, htf_idx)
        htf_zones = self._calc_discount_premium(htf_candles, htf_idx, htf_structure)

        htf_close = htf_candles[htf_idx].close
        trend = htf_structure["trend"]
        bos = htf_structure["bos"]
        choch = htf_structure["choch"]
        bos_direction = htf_structure.get("bos_direction", "NONE")
        choch_direction = htf_structure.get("choch_direction", "NONE")

        active_bullish_obs = [ob for ob in htf_obs if ob["type"] == "BULLISH" and ob.get("active", True)]
        active_bearish_obs = [ob for ob in htf_obs if ob["type"] == "BEARISH" and ob.get("active", True)]
        active_bullish_fvgs = [f for f in htf_fvgs if f["type"] == "BULLISH" and f.get("active", True)]
        active_bearish_fvgs = [f for f in htf_fvgs if f["type"] == "BEARISH" and f.get("active", True)]

        # Check POI zone rejection wicks
        rejected_bullish_obs = [
            ob for ob in active_bullish_obs
            if self._check_zone_rejection(htf_candles, htf_idx, ob["top"], ob["bottom"], "LONG", ob["idx"])
        ]
        rejected_bearish_obs = [
            ob for ob in active_bearish_obs
            if self._check_zone_rejection(htf_candles, htf_idx, ob["top"], ob["bottom"], "SHORT", ob["idx"])
        ]
        rejected_bullish_fvgs = [
            f for f in active_bullish_fvgs
            if self._check_zone_rejection(htf_candles, htf_idx, f["top"], f["bottom"], "LONG", f["idx"])
        ]
        rejected_bearish_fvgs = [
            f for f in active_bearish_fvgs
            if self._check_zone_rejection(htf_candles, htf_idx, f["top"], f["bottom"], "SHORT", f["idx"])
        ]
        ob_rejection_long = bool(rejected_bullish_obs)
        ob_rejection_short = bool(rejected_bearish_obs)
        fvg_rejection_long = bool(rejected_bullish_fvgs)
        fvg_rejection_short = bool(rejected_bearish_fvgs)

        # Institutional Fibonacci Discount / Premium
        price_in_discount = (
            htf_close <= htf_zones.get("discount_618_buy", 0.0)
            and htf_close >= htf_zones.get("deep_discount", 0.0)
        )
        price_in_premium = (
            htf_close >= htf_zones.get("premium_618", 0.0)
            and htf_close <= htf_zones.get("deep_premium", 0.0)
        )

        # ── LTF Microstructure & Triggers ─────────────────────────
        ltf_sweeps = self._detect_liquidity_sweeps(candles, idx, htf_structure)
        ltf_reversal = self._detect_reversal_candle(candles, idx)
        ltf_momentum = self._check_ltf_momentum(candles, idx, series)

        # ── Confluence Scoring ────────────────────────────────────
        score_long = 0
        score_short = 0
        reasons_long: List[str] = []
        reasons_short: List[str] = []

        htf_s_w = self._htf_structure_weight
        htf_bos_w = self._htf_bos_weight
        htf_ob_w = self._htf_ob_weight
        htf_fvg_w = self._htf_fvg_weight
        htf_disc_w = self._htf_discount_weight
        ltf_swp_w = self._ltf_sweep_weight
        ltf_rev_w = self._ltf_reversal_weight
        ltf_mom_w = self._ltf_momentum_weight

        # HTF Structure & Continuation
        if trend == "UPTREND":
            score_long += htf_s_w
            reasons_long.append("UPTREND")
            if bos_direction == "BULLISH":
                score_long += htf_bos_w
                reasons_long.append("BOS")
        elif trend == "DOWNTREND":
            score_short += htf_s_w
            reasons_short.append("DOWNTREND")
            if bos_direction == "BEARISH":
                score_short += htf_bos_w
                reasons_short.append("BOS")
        else:
            score_long += htf_s_w // 2
            score_short += htf_s_w // 2
            reasons_long.append("RANGE")
            reasons_short.append("RANGE")

        if choch_direction == "BULLISH":
            score_long += htf_bos_w // 2
            reasons_long.append("CHoCH")
        elif choch_direction == "BEARISH":
            score_short += htf_bos_w // 2
            reasons_short.append("CHoCH")

        # POI Rejection
        if ob_rejection_long:
            score_long += htf_ob_w
            reasons_long.append("OB_REJ")
        if ob_rejection_short:
            score_short += htf_ob_w
            reasons_short.append("OB_REJ")

        if fvg_rejection_long:
            score_long += htf_fvg_w
            reasons_long.append("FVG_REJ")
        if fvg_rejection_short:
            score_short += htf_fvg_w
            reasons_short.append("FVG_REJ")

        # Fibonacci Discount / Premium
        if price_in_discount:
            score_long += htf_disc_w
            reasons_long.append("FIB_DISC")
        if price_in_premium:
            score_short += htf_disc_w
            reasons_short.append("FIB_PREM")

        # LTF Liquidity Sweeps
        if ltf_sweeps["bullish_sweep"]:
            score_long += ltf_swp_w
            reasons_long.append("LIQ_SWEEP")
        if ltf_sweeps["bearish_sweep"]:
            score_short += ltf_swp_w
            reasons_short.append("LIQ_SWEEP")

        # LTF Candlestick Reversal
        if ltf_reversal["reversal"]:
            if ltf_reversal["bullish"]:
                score_long += ltf_rev_w
                reasons_long.append(f"REV_{ltf_reversal['rej_type']}")
            elif ltf_reversal["bearish"]:
                score_short += ltf_rev_w
                reasons_short.append(f"REV_{ltf_reversal['rej_type']}")

        # LTF Momentum Confluence
        if ltf_momentum == 1:
            score_long += ltf_mom_w
            reasons_long.append("MOMENTUM")
        elif ltf_momentum == -1:
            score_short += ltf_mom_w
            reasons_short.append("MOMENTUM")

        raw_score_long = score_long
        raw_score_short = score_short
        raw_reasons_long = list(reasons_long)
        raw_reasons_short = list(reasons_short)
        blocked_long: List[str] = []
        blocked_short: List[str] = []

        # Trend Regime Guard
        if trend == "UPTREND":
            if raw_score_short > 0:
                blocked_short.append("HTF_TREND")
            score_short = 0
        elif trend == "DOWNTREND":
            if raw_score_long > 0:
                blocked_long.append("HTF_TREND")
            score_long = 0

        # Confirmation Gate Enforcement
        long_structure_confirmed = bos_direction == "BULLISH" or choch_direction == "BULLISH"
        short_structure_confirmed = bos_direction == "BEARISH" or choch_direction == "BEARISH"
        long_poi_confirmed = ob_rejection_long or fvg_rejection_long
        short_poi_confirmed = ob_rejection_short or fvg_rejection_short

        conf_mode = self._confirmation_mode

        if conf_mode in ("both", "structure"):
            if not long_structure_confirmed:
                if raw_score_long > 0:
                    blocked_long.append("NO_BOS_CHOCH")
                score_long = 0
            if not short_structure_confirmed:
                if raw_score_short > 0:
                    blocked_short.append("NO_BOS_CHOCH")
                score_short = 0

        if conf_mode in ("both", "poi"):
            if not long_poi_confirmed:
                if raw_score_long > 0:
                    blocked_long.append("NO_POI_REJECTION")
                score_long = 0
            if not short_poi_confirmed:
                if raw_score_short > 0:
                    blocked_short.append("NO_POI_REJECTION")
                score_short = 0

        if conf_mode == "either":
            if not (long_structure_confirmed or long_poi_confirmed):
                if raw_score_long > 0:
                    blocked_long.extend(["NO_BOS_CHOCH", "NO_POI_REJECTION"])
                score_long = 0
            if not (short_structure_confirmed or short_poi_confirmed):
                if raw_score_short > 0:
                    blocked_short.extend(["NO_BOS_CHOCH", "NO_POI_REJECTION"])
                score_short = 0

        effective_min_score = self._min_score if min_score_override is None else int(min_score_override)

        # ── Dynamic Risk Geometry Calculation ─────────────────────
        reference_price = current.close
        sl = 0.0
        tp = 0.0
        risk_reward = self._tp_atr_mult / self._sl_atr_mult if self._sl_atr_mult > 0 else 2.0

        if score_long >= effective_min_score and score_long > score_short:
            ob_sl = None
            if rejected_bullish_obs:
                nearest_ob = min(rejected_bullish_obs, key=lambda ob: abs(ob["bottom"] - reference_price))
                ob_sl = nearest_ob["bottom"] * 0.998  # 0.2% below OB low
            swing_lows_list = htf_structure.get("swing_lows", [])
            swing_sl = swing_lows_list[-1]["price"] if swing_lows_list else None

            if ob_sl is not None and swing_sl is not None:
                sl = min(ob_sl, swing_sl)
            elif ob_sl is not None:
                sl = ob_sl
            elif swing_sl is not None:
                sl = swing_sl
            else:
                sl = reference_price - htf_atr * self._sl_atr_mult

            if sl >= reference_price:
                return None
            if not np.isfinite(risk_reward) or not (SMC_MIN_RISK_REWARD <= risk_reward <= SMC_MAX_RISK_REWARD):
                return None
            tp = reference_price + (reference_price - sl) * risk_reward

        elif score_short >= effective_min_score and score_short > score_long:
            ob_sl = None
            if rejected_bearish_obs:
                nearest_ob = min(rejected_bearish_obs, key=lambda ob: abs(ob["top"] - reference_price))
                ob_sl = nearest_ob["top"] * 1.002  # 0.2% above OB high
            swing_highs_list = htf_structure.get("swing_highs", [])
            swing_sl = swing_highs_list[-1]["price"] if swing_highs_list else None

            if ob_sl is not None and swing_sl is not None:
                sl = max(ob_sl, swing_sl)
            elif ob_sl is not None:
                sl = ob_sl
            elif swing_sl is not None:
                sl = swing_sl
            else:
                sl = reference_price + htf_atr * self._sl_atr_mult

            if sl <= reference_price:
                return None
            if not np.isfinite(risk_reward) or not (SMC_MIN_RISK_REWARD <= risk_reward <= SMC_MAX_RISK_REWARD):
                return None
            tp = reference_price - (sl - reference_price) * risk_reward

        # Guard: check minimum stop distance
        if (
            not np.isfinite(sl)
            or not np.isfinite(tp)
            or abs(reference_price - sl) < htf_atr * SMC_MIN_STOP_DISTANCE_ATR
        ):
            # If scoring succeeded but geometry failed and preview not requested, reject
            if not include_blocked_preview:
                return None

        current_regime = regime or MarketRegime.UNKNOWN

        # Emit Valid Signals
        if score_long >= effective_min_score and score_long > score_short:
            return Signal(
                direction=Direction.LONG,
                confidence=min(0.95, 0.35 + score_long / 100.0),
                score=float(min(score_long, 95)),
                indicator_values={
                    "htf_trend": trend,
                    "htf_bos": int(bos),
                    "htf_choch": int(choch),
                    "bos_direction": bos_direction,
                    "choch_direction": choch_direction,
                    "htf_atr": float(htf_atr),
                    "ob_rej": int(ob_rejection_long),
                    "fvg_rej": int(fvg_rejection_long),
                    "fib_disc": int(price_in_discount),
                    "ltf_sweep": int(ltf_sweeps["bullish_sweep"]),
                    "ltf_reversal": int(ltf_reversal["reversal"]),
                    "ltf_momentum": ltf_momentum,
                    "score": score_long,
                    "raw_score": raw_score_long,
                    "effective_score": score_long,
                    "trade_eligible": int(score_long >= self._min_score),
                    "blocked_by": "",
                    "confirmation_mode": conf_mode,
                    "reasons": ";".join(reasons_long),
                },
                regime=current_regime,
                strategy_name=self.name,
                timestamp=decision_time,
                metadata={
                    "sl": float(sl),
                    "tp": float(tp),
                    "max_hold": self._max_hold_bars,
                    "risk_reward": float(risk_reward),
                    "preview_only": False,
                },
            )

        elif score_short >= effective_min_score and score_short > score_long:
            return Signal(
                direction=Direction.SHORT,
                confidence=min(0.95, 0.35 + score_short / 100.0),
                score=float(min(score_short, 95)),
                indicator_values={
                    "htf_trend": trend,
                    "htf_bos": int(bos),
                    "htf_choch": int(choch),
                    "bos_direction": bos_direction,
                    "choch_direction": choch_direction,
                    "htf_atr": float(htf_atr),
                    "ob_rej": int(ob_rejection_short),
                    "fvg_rej": int(fvg_rejection_short),
                    "fib_prem": int(price_in_premium),
                    "ltf_sweep": int(ltf_sweeps["bearish_sweep"]),
                    "ltf_reversal": int(ltf_reversal["reversal"]),
                    "ltf_momentum": ltf_momentum,
                    "score": score_short,
                    "raw_score": raw_score_short,
                    "effective_score": score_short,
                    "trade_eligible": int(score_short >= self._min_score),
                    "blocked_by": "",
                    "confirmation_mode": conf_mode,
                    "reasons": ";".join(reasons_short),
                },
                regime=current_regime,
                strategy_name=self.name,
                timestamp=decision_time,
                metadata={
                    "sl": float(sl),
                    "tp": float(tp),
                    "max_hold": self._max_hold_bars,
                    "risk_reward": float(risk_reward),
                    "preview_only": False,
                },
            )

        # Blocked preview output for auditability and parameter sweeps
        if include_blocked_preview:
            if raw_score_long >= raw_score_short and raw_score_long > 0:
                p_dir = Direction.LONG
                p_score = raw_score_long
                p_eff_score = score_long
                p_reasons = raw_reasons_long
                p_blocked = list(blocked_long)
            elif raw_score_short > 0:
                p_dir = Direction.SHORT
                p_score = raw_score_short
                p_eff_score = score_short
                p_reasons = raw_reasons_short
                p_blocked = list(blocked_short)
            else:
                return None

            if p_eff_score < self._min_score and not p_blocked:
                p_blocked.append("BELOW_MIN_SCORE")

            blocked_str = ";".join(p_blocked)
            return Signal(
                direction=p_dir,
                confidence=min(0.95, 0.35 + p_score / 100.0),
                score=float(min(p_score, 95)),
                indicator_values={
                    "htf_trend": trend,
                    "htf_bos": int(bos),
                    "htf_choch": int(choch),
                    "bos_direction": bos_direction,
                    "choch_direction": choch_direction,
                    "htf_atr": float(htf_atr),
                    "score": p_score,
                    "raw_score": p_score,
                    "effective_score": p_eff_score,
                    "trade_eligible": 0,
                    "blocked_by": blocked_str,
                    "confirmation_mode": conf_mode,
                    "reasons": ";".join(p_reasons),
                },
                regime=current_regime,
                strategy_name=self.name,
                timestamp=decision_time,
                metadata={
                    "max_hold": self._max_hold_bars,
                    "preview_only": True,
                    "blocked_by": blocked_str,
                },
            )

        return None
