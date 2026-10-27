"""Constants and geometric parameters for Smart Money Concepts (SMC) MTF Strategy."""

# SMC Signal Geometry Bounds
SMC_MIN_SL_ATR_MULT: float = 0.1
SMC_MAX_SL_ATR_MULT: float = 10.0
SMC_MIN_TP_ATR_MULT: float = 0.1
SMC_MAX_TP_ATR_MULT: float = 20.0
SMC_MIN_RISK_REWARD: float = 0.25
SMC_MAX_RISK_REWARD: float = 20.0
SMC_MIN_STOP_DISTANCE_ATR: float = 0.05

# Strategy Defaults
DEFAULT_LOOKBACK_MSB: int = 30
DEFAULT_LOOKBACK_OB: int = 20
DEFAULT_FVG_MAX_BARS: int = 10
DEFAULT_MIN_SCORE: int = 50
DEFAULT_MAX_HOLD_BARS: int = 20
DEFAULT_SL_ATR_MULT: float = 1.5
DEFAULT_TP_ATR_MULT: float = 3.0
DEFAULT_CONFIRMATION_MODE: str = "both"

# Scoring Weight Defaults
DEFAULT_HTF_STRUCTURE_WEIGHT: int = 20
DEFAULT_HTF_BOS_WEIGHT: int = 10
DEFAULT_HTF_OB_WEIGHT: int = 20
DEFAULT_HTF_FVG_WEIGHT: int = 15
DEFAULT_HTF_DISCOUNT_WEIGHT: int = 5
DEFAULT_LTF_SWEEP_WEIGHT: int = 15
DEFAULT_LTF_REVERSAL_WEIGHT: int = 15
DEFAULT_LTF_MOMENTUM_WEIGHT: int = 10

# Backtest Engine Defaults
DEFAULT_CAPITAL: float = 1_000_000.0
DEFAULT_RISK_PER_TRADE: float = 0.005
DEFAULT_SLIPPAGE_BPS: float = 1.0
DEFAULT_COMMISSION_BPS: float = 4.0
DEFAULT_SPREAD_BPS: float = 1.0
DEFAULT_WARMUP_BARS: int = 100
DEFAULT_RANDOM_SEED: int = 42

# Fee structures by asset class
ASSET_FEES = {
    "CRYPTO": {"spread_bps": 1.0, "commission_bps": 4.0, "slippage_bps": 1.0},
    "COMMODITY": {"spread_bps": 2.0, "commission_bps": 4.0, "slippage_bps": 1.0},
    "FOREX": {"spread_bps": 0.5, "commission_bps": 2.0, "slippage_bps": 0.5},
    "INDEX": {"spread_bps": 1.0, "commission_bps": 2.0, "slippage_bps": 0.5},
}
