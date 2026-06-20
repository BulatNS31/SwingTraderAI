from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MarketAsset(BaseModel):
	id: UUID
	ticker_id: UUID
	symbol: str
	exchange: Optional[str] = None
	asset_type: Optional[str] = None
	last_price: Optional[float] = None
	change_percent: Optional[float] = None
	volume: Optional[float] = None
	timestamp: Optional[datetime] = None

	model_config = ConfigDict(from_attributes=True)


class MarketHeatmapItem(BaseModel):
	symbol: str
	name: Optional[str] = None
	exchange: Optional[str] = None
	change_percent: float

	model_config = ConfigDict(from_attributes=True)


class MarketPulse(BaseModel):
	total: int = 0
	gainers: int = 0
	losers: int = 0
	neutral: int = 0
	avg_change_percent: float = 0.0

	model_config = ConfigDict(from_attributes=True)


class MarketsSnapshot(BaseModel):
	crypto: List[MarketAsset] = Field(default_factory=list)
	moex: List[MarketAsset] = Field(default_factory=list)
	nasdaq: List[MarketAsset] = Field(default_factory=list)
	heatmap: List[MarketHeatmapItem] = Field(default_factory=list)
	pulse: MarketPulse | Dict[str, Any] = Field(default_factory=dict)

	model_config = ConfigDict(from_attributes=True)


class MarketQuoteResponse(BaseModel):
	"""Ответ с данными котировки для одного символа"""

	symbol: str
	price: Decimal
	change_percent: float
	volume: Optional[float] = None
	market_type: Optional[str] = None
	updated_at: datetime

	model_config = ConfigDict(from_attributes=True)
