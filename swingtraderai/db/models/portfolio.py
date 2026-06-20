from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from swingtraderai.db.base import TenantBase

if TYPE_CHECKING:
	from .market import Ticker
	from .user import Position, User


class Portfolio(TenantBase):
	"""Портфель пользователя."""

	__tablename__ = "portfolios"

	id: Mapped[UUID] = mapped_column(
		PGUUID(as_uuid=True), primary_key=True, default=uuid7
	)
	user_id: Mapped[UUID] = mapped_column(
		PGUUID(as_uuid=True),
		ForeignKey("users.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	name: Mapped[str] = mapped_column(String(100), nullable=False)
	description: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		default=lambda: datetime.now(timezone.utc),
		server_default="NOW()",
	)
	updated_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		default=lambda: datetime.now(timezone.utc),
		onupdate=lambda: datetime.now(timezone.utc),
		server_default="NOW()",
	)

	user: Mapped["User"] = relationship("User", back_populates="portfolios")
	positions: Mapped[list["Position"]] = relationship(
		"Position",
		back_populates="portfolio",
		cascade="all, delete-orphan",
		lazy="select",
	)
	transactions: Mapped[list["PortfolioTransaction"]] = relationship(
		"PortfolioTransaction",
		back_populates="portfolio",
		cascade="all, delete-orphan",
		lazy="select",
	)

	__table_args__ = (
		Index("ix_portfolios_tenant_user_id", "tenant_id", "user_id"),
		Index("ix_portfolios_tenant_name", "tenant_id", "name"),
	)


class PortfolioTransaction(TenantBase):
	"""Транзакция покупки/продажи в портфеле."""

	__tablename__ = "portfolio_transactions"

	id: Mapped[UUID] = mapped_column(
		PGUUID(as_uuid=True), primary_key=True, default=uuid7
	)
	user_id: Mapped[UUID] = mapped_column(
		PGUUID(as_uuid=True),
		ForeignKey("users.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	portfolio_id: Mapped[UUID] = mapped_column(
		PGUUID(as_uuid=True),
		ForeignKey("portfolios.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	ticker_id: Mapped[UUID] = mapped_column(
		PGUUID(as_uuid=True),
		ForeignKey("tickers.id", ondelete="CASCADE"),
		nullable=False,
		index=True,
	)
	side: Mapped[str] = mapped_column(String(10), nullable=False)
	quantity: Mapped[Decimal] = mapped_column(
		Numeric(precision=18, scale=8), nullable=False
	)
	price: Mapped[Decimal] = mapped_column(
		Numeric(precision=18, scale=8), nullable=False
	)
	fee: Mapped[Decimal | None] = mapped_column(
		Numeric(precision=18, scale=8), nullable=True
	)
	executed_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default="NOW()"
	)
	notes: Mapped[str | None] = mapped_column(Text, nullable=True)
	created_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True),
		nullable=False,
		default=lambda: datetime.now(timezone.utc),
		server_default="NOW()",
	)

	user: Mapped["User"] = relationship("User")
	portfolio: Mapped["Portfolio"] = relationship(
		"Portfolio", back_populates="transactions"
	)
	ticker: Mapped["Ticker"] = relationship("Ticker")

	__table_args__ = (
		Index(
			"ix_portfolio_transactions_tenant_portfolio", "tenant_id", "portfolio_id"
		),
		Index("ix_portfolio_transactions_tenant_ticker", "tenant_id", "ticker_id"),
		Index("ix_portfolio_transactions_executed_at", "executed_at"),
	)
