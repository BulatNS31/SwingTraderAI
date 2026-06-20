from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from swingtraderai.db.base import TenantBase

if TYPE_CHECKING:
	from .market import Ticker


class MarketQuoteSnapshot(TenantBase):
	__tablename__ = "market_quotes"

	ticker_id: Mapped[UUID] = mapped_column(
		PGUUID(as_uuid=True),
		ForeignKey("tickers.id", ondelete="CASCADE"),
		primary_key=True,
		index=True,
	)

	price: Mapped[Decimal] = mapped_column(
		Numeric(precision=20, scale=10), nullable=False
	)
	change_percent: Mapped[Decimal] = mapped_column(
		Numeric(precision=10, scale=4), nullable=False
	)
	volume: Mapped[Decimal | None] = mapped_column(
		Numeric(precision=20, scale=8), nullable=True
	)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False
	)

	ticker: Mapped["Ticker"] = relationship(
		"Ticker",
		lazy="selectin",
	)

	__table_args__ = (Index("ix_market_quotes_updated_at", "updated_at"),)
