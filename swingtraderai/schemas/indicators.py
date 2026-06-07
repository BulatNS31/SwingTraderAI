from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Timeframe(StrEnum):
	M15 = "15m"
	H1 = "1h"
	H4 = "4h"
	D1 = "1d"
	W1 = "1w"


INDICATOR_TIMEFRAMES: dict[str, list[Timeframe]] = {
	# TREND
	"ema9": [Timeframe.M15, Timeframe.H1],
	"ema20": [Timeframe.H1, Timeframe.H4],
	"ema50": [Timeframe.H4, Timeframe.D1],
	"ema200": [Timeframe.D1, Timeframe.W1],
	"wma10": [Timeframe.M15, Timeframe.H1],
	"wma20": [Timeframe.H1, Timeframe.H4],
	"wma50": [Timeframe.H4, Timeframe.D1],
	# MOMENTUM
	"rsi": [Timeframe.H1, Timeframe.H4],
	"rsi7": [Timeframe.M15, Timeframe.H1],
	"rsi14": [Timeframe.H1, Timeframe.H4],
	"rsi_regime": [Timeframe.H4, Timeframe.D1],
	"cci": [Timeframe.H1, Timeframe.H4],
	"cci14": [Timeframe.H1, Timeframe.H4],
	"macd": [Timeframe.H1, Timeframe.H4, Timeframe.D1],
	"stoch": [Timeframe.M15, Timeframe.H1],
	"momentum10": [Timeframe.H1],
	"momentum20": [Timeframe.H4],
	# VOLATILITY
	"atr": [Timeframe.H1, Timeframe.H4],
	"atr10": [Timeframe.H1],
	"atr20": [Timeframe.H4],
	"bbands": [Timeframe.H1, Timeframe.H4],
	"donchian": [Timeframe.H4, Timeframe.D1],
	# VOLUME
	"obv": [Timeframe.H1, Timeframe.H4],
	"ad": [Timeframe.H1, Timeframe.H4],
	"volume_sma": [Timeframe.H1],
	"volume_sma10": [Timeframe.H1],
	"volume_sma20": [Timeframe.H4],
	"zscore_volume": [Timeframe.H1],
	"vwap": [Timeframe.M15],
	"vwap_session": [Timeframe.M15],
	# PRICE ACTION / LEVELS
	"pivot_points": [Timeframe.D1],
	"sr_levels": [Timeframe.D1, Timeframe.W1],
	"fractal": [Timeframe.H4, Timeframe.D1],
	# DERIVED
	"distance_from_ema20": [Timeframe.H1],
	"distance_from_ema50": [Timeframe.H4],
	"returns": [Timeframe.H1],
	"log_returns": [Timeframe.H1],
	"zscore_price": [Timeframe.H1, Timeframe.H4],
}


class IndicatorValue(BaseModel):
	value: Optional[float]
	signal: Optional[Literal["bullish", "bearish", "neutral"]] = None
	regime: Optional[str] = None
	metadata: Dict[str, Any] = Field(default_factory=dict)


class TechnicalIndicatorsOut(BaseModel):
	ticker_id: UUID
	symbol: str
	timeframe: str
	timestamp: datetime
	current_price: float

	indicators: Dict[str, IndicatorValue] = Field(default_factory=dict)
	summary: Dict[str, Any] = Field(default_factory=dict)
	signals: List[Dict[str, Any]] = Field(default_factory=list)

	model_config = ConfigDict(from_attributes=True)


class IndicatorRequest(BaseModel):
	indicators: List[str] = Field(
		default=["ema20", "ema50", "rsi", "macd", "bbands", "atr"],
		description="Список запрашиваемых индикаторов",
	)
	timeframe: Timeframe = Timeframe.H1
	limit: int = Field(500, ge=100, le=2000)


class SignalOut(BaseModel):
	type: Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"]
	strength: int = Field(..., ge=1, le=10)
	message: str
	indicators_used: List[str]
