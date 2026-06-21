from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Final, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SignalType(str, Enum):
	TARGET_HIT = "target_hit"
	STOP_LOSS_HIT = "stop_loss_hit"


@dataclass(frozen=True)
class AnalysisResult:
	action: str
	confidence: float
	description: str


class AnalysisConfig:
	THRESHOLDS: Final = {
		"strong_bullish": 5.0,
		"bullish": 2.0,
		"strong_bearish": -5.0,
		"bearish": -2.0,
	}

	SCORES: Final = {
		"strong_bullish": 20,
		"bullish": 10,
		"strong_bearish": -20,
		"bearish": -10,
		SignalType.TARGET_HIT: 15,
		SignalType.STOP_LOSS_HIT: -15,
	}

	RESULT_MAPPING: Final = {
		(30, float("inf")): ("STRONG_BUY", 0.91, "Strong bullish momentum detected"),
		(10, 29): ("BUY", 0.77, "Positive momentum with upside potential"),
		(6, 9): (
			"BUY",
			0.70,
			"Mild positive momentum",
		),  # Добавлен диапазон для умеренного BUY
		(-5, 5): (
			"HOLD",
			0.63,
			"Price action remains neutral",
		),  # HOLD для нейтральных значений
		(-9, -6): (
			"SELL",
			0.70,
			"Mild negative momentum",
		),  # Добавлен диапазон для умеренного SELL
		(-29, -10): ("SELL", 0.74, "Negative momentum observed"),
		(float("-inf"), -30): (
			"STRONG_SELL",
			0.89,
			"Strong downside pressure detected",
		),
	}

	NEUTRAL: Final = ("NEUTRAL", 0.63, "Price action remains neutral")


class WatchlistBase(BaseModel):
	name: Optional[str] = None
	owner_id: Optional[UUID] = None


class WatchlistCreate(BaseModel):
	"""Схема для создания нового watchlist"""

	name: str = Field(
		..., min_length=1, max_length=100, description="Название списка наблюдения"
	)
	description: Optional[str] = Field(
		None, max_length=500, description="Описание списка"
	)

	model_config = ConfigDict(from_attributes=True)


class WatchlistUpdate(BaseModel):
	"""Схема для обновления watchlist"""

	name: Optional[str] = Field(None, min_length=1, max_length=100)
	description: Optional[str] = Field(None, max_length=500)

	model_config = ConfigDict(from_attributes=True)


class WatchlistInDB(WatchlistBase):
	"""Полная схема watchlist из БД"""

	id: UUID
	owner_id: UUID
	created_at: datetime
	updated_at: Optional[datetime] = None

	model_config = ConfigDict(from_attributes=True)


class WatchlistOut(WatchlistBase):
	id: UUID
	created_at: datetime

	model_config = ConfigDict(from_attributes=True)


class WatchlistItemBase(BaseModel):
	watchlist_id: UUID = Field(..., description="ID списка наблюдения")
	ticker_id: UUID = Field(..., description="ID тикера для добавления в список")


class WatchlistItemOut(WatchlistItemBase):
	id: UUID
	notes: Optional[str] = None
	reason: Optional[str] = None
	target_price: Optional[float] = None
	stop_loss: Optional[float] = None
	watchlist_id: UUID
	ticker_id: UUID

	model_config = ConfigDict(from_attributes=True)


class WatchlistItemCreate(WatchlistItemBase):
	"""
	Схема для создания нового элемента в watchlist.
	Можно расширить дополнительными полями при необходимости.
	"""

	notes: Optional[str] = None
	reason: Optional[str] = None
	target_price: Optional[float] = None
	stop_loss: Optional[float] = None


class WatchlistItemUpdate(BaseModel):
	"""Схема для частичного обновления элемента в watchlist"""

	notes: Optional[str] = None
	reason: Optional[str] = None
	target_price: Optional[float] = None
	stop_loss: Optional[float] = None

	model_config = ConfigDict(from_attributes=True)


class AIInsight(BaseModel):
	summary: str
	confidence: float

	model_config = ConfigDict(from_attributes=True)


class WatchlistDataItem(BaseModel):
	item_id: UUID
	ticker_id: UUID
	symbol: str
	asset_type: str

	last_price: Optional[float] = None
	change_percent: Optional[float] = 0.0
	change_abs: Optional[float] = 0.0
	volume: Optional[float] = None
	added_at: datetime

	notes: Optional[str] = None
	reason: Optional[str] = None
	target_price: Optional[float] = None
	stop_loss: Optional[float] = None
	signals: list[str] = Field(default_factory=list)

	signal: Optional[
		Literal[
			"STRONG_BUY",
			"BUY",
			"NEUTRAL",
			"SELL",
			"STRONG_SELL",
		]
	] = None

	confidence: float = 0.0
	ai_summary: Optional[str] = None

	ai_insight: Optional[AIInsight] = None
	trend: list[float] = Field(default_factory=list)

	model_config = ConfigDict(from_attributes=True)


class WatchlistStats(BaseModel):
	total_assets: int = 0

	gainers: int = 0
	losers: int = 0
	neutral: int = 0

	strong_buy_count: int = 0
	buy_count: int = 0
	sell_count: int = 0
	strong_sell_count: int = 0

	avg_change_percent: float = 0.0

	top_gainer: Optional[str] = None
	top_loser: Optional[str] = None

	model_config = ConfigDict(from_attributes=True)
