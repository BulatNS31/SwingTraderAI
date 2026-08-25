from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import TIMESTAMP, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import NUMERIC, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from uuid6 import uuid7

from swingtraderai.db.base import Base
from swingtraderai.db.models.market_quote import MarketQuoteSnapshot

if TYPE_CHECKING:
	from swingtraderai.db.models.system import WatchlistItem


class Ticker(Base):
	__tablename__ = "tickers"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid7
	)
	symbol: Mapped[str] = mapped_column(String(20), nullable=False)
	asset_type: Mapped[str] = mapped_column(String(10), nullable=False)
	exchange_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True),
		ForeignKey("exchanges.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	base_currency: Mapped[str | None] = mapped_column(String(10))
	quote_currency: Mapped[str | None] = mapped_column(String(10))
	is_active: Mapped[bool] = mapped_column(
		Boolean,
		default=True,
		nullable=False,
		index=True,
	)
	created_at: Mapped[datetime] = mapped_column(
		TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
	)
	exchange_ref: Mapped[Optional["Exchange"]] = relationship(
		"Exchange", back_populates="tickers"
	)
	watchlist_items: Mapped[List["WatchlistItem"]] = relationship(
		"WatchlistItem",
		back_populates="ticker",
		cascade="all, delete-orphan",
		lazy="select",
	)
	market_quote_snapshot: Mapped[Optional["MarketQuoteSnapshot"]] = relationship(
		"MarketQuoteSnapshot", back_populates="ticker", uselist=False, lazy="selectin"
	)

	__table_args__ = (
		UniqueConstraint("symbol", "exchange_id", name="uq_ticker_symbol_exchange"),
	)


class MarketData(Base):
	__tablename__ = "market_data"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid7
	)
	ticker_id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), ForeignKey("tickers.id")
	)
	timeframe: Mapped[str | None] = mapped_column(String(10))
	timestamp: Mapped[datetime | None] = mapped_column(
		TIMESTAMP(timezone=True), nullable=False, server_default=func.now(), index=True
	)
	open: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(20, 10))
	high: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(20, 10))
	low: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(20, 10))
	close: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(20, 10))
	volume: Mapped[Optional[Decimal]] = mapped_column(NUMERIC(20, 10))
	created_at: Mapped[datetime] = mapped_column(
		TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
	)
	source: Mapped[str | None] = mapped_column(String(20), index=True, nullable=True)
	ingested_at: Mapped[datetime] = mapped_column(
		TIMESTAMP(timezone=True),
		default=lambda: datetime.now(timezone.utc),
		nullable=False,
	)

	ticker = relationship("Ticker")

	__table_args__ = (
		Index("idx_market_data", "ticker_id", "timeframe", "timestamp"),
		UniqueConstraint(
			"ticker_id", "timeframe", "timestamp", name="uq_market_data_time"
		),
	)


class Exchange(Base):
	"""
	Минималистичная модель биржи. Оставлено только то, что влияет на
	логику обработки данных и типизацию тикеров.
	"""

	__tablename__ = "exchanges"

	id: Mapped[uuid.UUID] = mapped_column(
		UUID(as_uuid=True), primary_key=True, default=uuid7
	)
	name: Mapped[str] = mapped_column(
		String(50), unique=True, nullable=False, index=True
	)
	code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
	timezone: Mapped[str] = mapped_column(String(50), default="UTC")
	currency: Mapped[str] = mapped_column(String(10), default="USD")

	created_at: Mapped[datetime] = mapped_column(
		TIMESTAMP(timezone=True), default=lambda: datetime.now(timezone.utc)
	)

	tickers: Mapped[List["Ticker"]] = relationship(
		"Ticker", back_populates="exchange_ref", cascade="all, delete-orphan"
	)
