from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PortfolioTransactionCreate(BaseModel):
	ticker_id: UUID
	side: str = Field(..., pattern="^(BUY|SELL)$")
	quantity: Decimal = Field(..., gt=0)
	price: Decimal = Field(..., gt=0)
	fee: Optional[Decimal] = None
	executed_at: Optional[datetime] = None
	notes: Optional[str] = None

	@field_validator("side")
	@classmethod
	def validate_side(cls, value: str) -> str:
		return value.upper()

	model_config = ConfigDict(from_attributes=True)


class PortfolioTransactionOut(BaseModel):
	id: UUID
	user_id: UUID
	portfolio_id: UUID
	ticker_id: UUID
	side: str
	quantity: Decimal
	price: Decimal
	fee: Optional[Decimal] = None
	executed_at: datetime
	notes: Optional[str] = None
	created_at: datetime

	model_config = ConfigDict(from_attributes=True)
