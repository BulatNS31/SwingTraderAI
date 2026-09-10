"""Модели предметной области для механизма обратного тестирования.

Это чисто Pydantic модели. Они намеренно отделены от
Схем SQLAlchemy / API. Сохранение добавляется только после
корректной настройки механизма в памяти.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, computed_field


class Side(StrEnum):
	LONG = "long"
	SHORT = "short"
	NEUTRAL = "neutral"


class ExitReason(StrEnum):
	STOP_LOSS = "sl"
	TAKE_PROFIT = "tp"
	TRAILING_STOP = "trailing"
	SIGNAL_REVERSE = "signal"
	TIME_EXIT = "time"
	END_OF_DATA = "end_of_data"
	MANUAL = "manual"


# ---------------------------------------------------------------------------
# Signal — вывод существующего конвейера анализа в определенный момент времени
# ---------------------------------------------------------------------------


class Signal(BaseModel):
	"""Point-in-time trading signal produced by SignalGenerator.

	Must never contain future information. entry_reference_price is the
	price observed on the signal bar (usually close) and is used only as
	a reference for SL/TP calculation; actual fill price is determined
	by the execution model.
	"""

	timestamp: datetime
	ticker: str
	timeframe: str
	side: Side

	signal_type: str  # STRONG_BUY / BUY / NEUTRAL / SELL / STRONG_SELL
	signal_score: float = Field(..., ge=0, le=10)
	confidence: Optional[float] = Field(None, ge=0, le=1)

	market_regime: Optional[str] = None
	entry_reference_price: float
	stop_loss: Optional[float] = None
	take_profit: Optional[float] = None

	ml_probability: Optional[float] = None
	indicators_used: List[str] = Field(default_factory=list)
	metadata: Dict[str, Any] = Field(default_factory=dict)

	model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Position — открытая экспозиция
# ---------------------------------------------------------------------------


class Position(BaseModel):
	"""Currently open position (one at a time in Phase 1)."""

	side: Side
	quantity: float
	entry_price: float
	entry_time: datetime
	entry_bar_index: int

	stop_loss: Optional[float] = None
	take_profit: Optional[float] = None
	trailing_stop: Optional[float] = None

	# Tracking for MFE / MAE (in price units, signed for long)
	max_favorable_price: float  # best price seen since entry
	max_adverse_price: float  # worst price seen since entry

	signal: Signal  # originating signal
	bars_held: int = 0

	model_config = {"extra": "forbid"}

	def unrealized_pnl(self, current_price: float) -> float:
		if self.side == Side.LONG:
			return (current_price - self.entry_price) * self.quantity
		if self.side == Side.SHORT:
			return (self.entry_price - current_price) * self.quantity
		return 0.0

	def update_excursions(self, high: float, low: float) -> None:
		"""Update MFE/MAE trackers from the current bar's high/low."""
		if self.side == Side.LONG:
			self.max_favorable_price = max(self.max_favorable_price, high)
			self.max_adverse_price = min(self.max_adverse_price, low)
		elif self.side == Side.SHORT:
			self.max_favorable_price = min(self.max_favorable_price, low)
			self.max_adverse_price = max(self.max_adverse_price, high)


# ---------------------------------------------------------------------------
# Trade — завершенный сделки туда и обратно
# ---------------------------------------------------------------------------


class Trade(BaseModel):
	"""Полностью закрытая сделка со всеми полями учета."""

	signal_timestamp: datetime
	ticker: str
	timeframe: str
	side: Side

	entry_price: float
	entry_time: datetime
	exit_price: float
	exit_time: datetime

	stop_loss: Optional[float] = None
	take_profit: Optional[float] = None

	position_size: float  # quantity
	pnl: float
	pnl_percent: float
	commission: float
	slippage: float

	exit_reason: ExitReason
	bars_held: int

	max_favorable_excursion: float  # price units
	max_adverse_excursion: float  # price units
	mfe_percent: float = 0.0
	mae_percent: float = 0.0

	signal_score: float
	market_regime: Optional[str] = None
	signal_type: str
	ml_probability: Optional[float] = None

	model_config = {"extra": "forbid"}

	@computed_field  # type: ignore[prop-decorator]
	@property
	def net_pnl(self) -> float:
		return self.pnl - self.commission - self.slippage


# ---------------------------------------------------------------------------
# Точка кривой собственного капитала
# ---------------------------------------------------------------------------


class EquityPoint(BaseModel):
	time: datetime
	equity: float
	cash: float
	unrealized_pnl: float = 0.0
	drawdown: float = 0.0
	drawdown_pct: float = 0.0

	model_config = {"extra": "forbid"}


# ---------------------------------------------------------------------------
# Backtest result
# ---------------------------------------------------------------------------


class BacktestMetrics(BaseModel):
	"""Core performance metrics (populated in Phase 2; stub in Phase 1)."""

	total_return: float = 0.0
	total_return_pct: float = 0.0
	cagr: Optional[float] = None
	sharpe: Optional[float] = None
	sortino: Optional[float] = None
	max_drawdown: float = 0.0
	max_drawdown_pct: float = 0.0
	calmar: Optional[float] = None

	win_rate: float = 0.0
	loss_rate: float = 0.0
	profit_factor: Optional[float] = None
	expectancy: float = 0.0
	average_trade: float = 0.0
	average_win: float = 0.0
	average_loss: float = 0.0
	largest_win: float = 0.0
	largest_loss: float = 0.0
	total_trades: int = 0
	winning_trades: int = 0
	losing_trades: int = 0
	average_bars_held: float = 0.0

	avg_mfe: float = 0.0
	avg_mae: float = 0.0

	model_config = {"extra": "forbid"}


class BacktestResult(BaseModel):
	"""Complete result of one backtest run."""

	# Identity
	ticker: str
	timeframe: str
	start: datetime
	end: datetime

	config: Any  # BacktestConfig (avoid circular import issues)
	trades: List[Trade] = Field(default_factory=list)
	equity_curve: List[EquityPoint] = Field(default_factory=list)
	metrics: BacktestMetrics = Field(default_factory=BacktestMetrics)

	# Metadata
	model_version: Optional[str] = None
	bars_processed: int = 0
	signals_generated: int = 0
	notes: Optional[str] = None
	metadata: Dict[str, Any] = Field(default_factory=dict)

	model_config = {"extra": "forbid"}
