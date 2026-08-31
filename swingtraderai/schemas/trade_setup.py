# swingtraderai/schemas/trade_setup.py
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class TrendDirection(str, Enum):
	UP = "up"
	DOWN = "down"
	SIDEWAYS = "sideways"
	UNKNOWN = "unknown"


class LevelType(str, Enum):
	SUPPORT = "support"
	RESISTANCE = "resistance"
	NONE = "none"


class SetupType(str, Enum):
	# Найман
	BULLISH_DIVERGENCE = "bullish_divergence"
	BEARISH_DIVERGENCE = "bearish_divergence"

	# Герчик
	FALSE_BREAKOUT_BEAR_TRAP = "false_breakout_bear_trap"  # long
	FALSE_BREAKOUT_BULL_TRAP = "false_breakout_bull_trap"  # short
	BSU_BPU_REACTION = "bsu_bpu_reaction"  # отскок/реакция у БСУ-БПУ

	# Carter
	TTM_SQUEEZE_FIRE_LONG = "ttm_squeeze_fire_long"
	TTM_SQUEEZE_FIRE_SHORT = "ttm_squeeze_fire_short"

	# Bulkowski / price action
	DOUBLE_BOTTOM = "double_bottom"
	DOUBLE_TOP = "double_top"
	HAMMER = "hammer"
	BULLISH_ENGULFING = "bullish_engulfing"

	# Общие
	PULLBACK_TO_LEVEL = "pullback_to_level"
	BREAKOUT = "breakout"
	OTHER = "other"


class SetupSide(str, Enum):
	LONG = "long"
	SHORT = "short"
	NONE = "none"


class SignalStrength(str, Enum):
	STRONG_BUY = "STRONG_BUY"
	BUY = "BUY"
	NEUTRAL = "NEUTRAL"
	SELL = "SELL"
	STRONG_SELL = "STRONG_SELL"


class TrendContext(BaseModel):
	"""Контекст тренда (желательно со старшего ТФ)."""

	direction: TrendDirection = TrendDirection.UNKNOWN
	timeframe: Optional[str] = None  # напр. "1D" если анализ на "1h"
	price_above_ema200: Optional[bool] = None
	ema9_gt_ema21: Optional[bool] = None
	structure: Optional[str] = None  # "HH_HL" | "LH_LL" | "mixed" | None
	notes: Optional[str] = None


class LevelContext(BaseModel):
	near_level: bool = False
	level_type: LevelType = LevelType.NONE
	level_price: Optional[float] = None
	level_strength: Optional[float] = None  # общее
	dist_to_level_pct: Optional[float] = None

	# Герчик BSU/BPU
	bpu_count: Optional[int] = None
	atr_potential: Optional[float] = (
		None  # запас хода в ATR (res_atr_left / sup_atr_left)
	)
	source: Optional[str] = None  # "bsu_bpu" | "sr_zones" | "fractal" | "pivot"
	notes: Optional[str] = None


class TriggerContext(BaseModel):
	"""Что именно дало точку входа."""

	setup_type: SetupType
	side: SetupSide
	confirmed: bool = True
	# детали триггера (глубина FB, тип дивергенции, осциллятор и т.д.)
	details: Dict[str, Any] = Field(default_factory=dict)


class VolumeContext(BaseModel):
	confirmed: bool = False
	volume_ratio: Optional[float] = None  # volume / SMA(volume)
	volume_zscore: Optional[float] = None
	spike: Optional[bool] = None
	notes: Optional[str] = None


class RiskContext(BaseModel):
	"""Точка входа, отмена сценария, цели, R:R."""

	entry: float
	invalidation: float  # стоп / отмена сценария
	stop_distance: Optional[float] = None  # |entry - invalidation|
	target_1: Optional[float] = None
	target_2: Optional[float] = None
	reward_risk: Optional[float] = None  # R:R до target_1
	atr: Optional[float] = None
	atr_stop_mult: Optional[float] = None  # если стоп в ATR

	@model_validator(mode="after")
	def compute_derived(self) -> "RiskContext":
		if (
			self.stop_distance is None
			and self.entry is not None
			and self.invalidation is not None
		):
			self.stop_distance = abs(self.entry - self.invalidation)
		if (
			self.reward_risk is None
			and self.target_1 is not None
			and self.stop_distance
			and self.stop_distance > 0
		):
			self.reward_risk = abs(self.target_1 - self.entry) / self.stop_distance
		return self


class TradeSetup(BaseModel):
	"""
	Единый торговый сценарий.

	Формируется детерминированным pandas-сканером.
	ML и AI-агент работают уже поверх этого объекта.
	"""

	# --- идентификация ---
	ticker_id: Optional[UUID] = None
	symbol: str
	timeframe: str
	bar_time: datetime  # время бара, на котором сформирован setup

	# --- направление ---
	side: SetupSide
	setup_type: SetupType

	# --- контекст ---
	trend: TrendContext = Field(default_factory=TrendContext)
	level: LevelContext = Field(default_factory=LevelContext)
	trigger: TriggerContext
	volume: VolumeContext = Field(default_factory=VolumeContext)
	risk: RiskContext

	# --- оценки ---
	composite_signal: SignalStrength = SignalStrength.NEUTRAL
	signal_strength: int = Field(default=1, ge=1, le=10)  # 1..10
	ml_prob: Optional[float] = Field(default=None, ge=0.0, le=1.0)

	# --- служебное ---
	indicators_used: List[str] = Field(default_factory=list)
	tags: List[str] = Field(default_factory=list)
	notes: Optional[str] = None
	raw: Dict[str, Any] = Field(default_factory=dict)  # отладочный срез фич

	@model_validator(mode="after")
	def side_matches_trigger(self) -> "TradeSetup":
		# side setup'а должен совпадать с side триггера (если задан)
		if self.trigger.side != SetupSide.NONE and self.side != self.trigger.side:
			raise ValueError(
				f"side={self.side} не совпадает с trigger.side={self.trigger.side}"
			)
		return self

	def is_actionable(self, min_rr: float = 1.5, min_strength: int = 5) -> bool:
		"""Грубый rule-based фильтр до AI-агента."""
		if self.side == SetupSide.NONE:
			return False
		if self.signal_strength < min_strength:
			return False
		if self.risk.reward_risk is not None and self.risk.reward_risk < min_rr:
			return False
		return True

	def to_agent_payload(self) -> Dict[str, Any]:
		"""Компактный JSON для LangGraph / LLM."""
		return {
			"symbol": self.symbol,
			"timeframe": self.timeframe,
			"bar_time": self.bar_time.isoformat(),
			"side": self.side.value,
			"setup_type": self.setup_type.value,
			"trend": self.trend.model_dump(),
			"level": self.level.model_dump(),
			"trigger": {
				"type": self.trigger.setup_type.value,
				"confirmed": self.trigger.confirmed,
				"details": self.trigger.details,
			},
			"volume_confirmed": self.volume.confirmed,
			"risk": {
				"entry": self.risk.entry,
				"invalidation": self.risk.invalidation,
				"target_1": self.risk.target_1,
				"reward_risk": self.risk.reward_risk,
			},
			"composite_signal": self.composite_signal.value,
			"signal_strength": self.signal_strength,
			"ml_prob": self.ml_prob,
			"tags": self.tags,
			"notes": self.notes,
		}


class TradeSetupList(BaseModel):
	"""Список setup'ов по тикеру/скану."""

	symbol: str
	timeframe: str
	as_of: datetime
	setups: List[TradeSetup] = Field(default_factory=list)

	@property
	def actionable(self) -> List[TradeSetup]:
		return [s for s in self.setups if s.is_actionable()]
