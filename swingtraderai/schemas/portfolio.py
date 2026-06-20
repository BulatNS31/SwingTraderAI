from datetime import datetime
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PortfolioCreate(BaseModel):
	name: str = Field(..., max_length=100)
	description: Optional[str] = None

	model_config = ConfigDict(from_attributes=True)


class PortfolioUpdate(BaseModel):
	name: Optional[str] = Field(None, max_length=100)
	description: Optional[str] = None

	model_config = ConfigDict(from_attributes=True)


class PortfolioOut(BaseModel):
	id: UUID
	user_id: UUID
	name: str
	description: Optional[str] = None
	created_at: datetime
	updated_at: datetime

	model_config = ConfigDict(from_attributes=True)


class PortfolioListOut(BaseModel):
	portfolios: List[PortfolioOut] = Field(default_factory=list)

	model_config = ConfigDict(from_attributes=True)
