from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum as PyEnum
from uuid import UUID

from sqlalchemy import (
	TIMESTAMP,
	BigInteger,
	Boolean,
	CheckConstraint,
	DateTime,
	Enum,
	ForeignKey,
	Index,
	Integer,
	Numeric,
	String,
	Text,
	UniqueConstraint,
	func,
	text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7

from swingtraderai.db.base import TenantBase
from swingtraderai.db.models.market import Ticker
from swingtraderai.db.models.portfolio import Portfolio


class UserRole(str, PyEnum):
	USER = "user"
	TESTER = "tester"
	SUPPORT = "support"
	ADMIN = "admin"


class User(TenantBase):
	__tablename__ = "users"

	id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
	username: Mapped[str] = mapped_column(
		String(50), unique=True, nullable=False, index=True
	)
	email: Mapped[str] = mapped_column(
		String(255), unique=True, nullable=False, index=True
	)
	password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
	telegram_id: Mapped[BigInteger | None] = mapped_column(
		BigInteger, nullable=True, index=False
	)
	telegram_verified: Mapped[bool] = mapped_column(
		Boolean, default=False, nullable=False
	)

	# Billing / subscription fields
	stripe_customer_id: Mapped[str | None] = mapped_column(
		String(255), nullable=True, index=True
	)
	subscription_status: Mapped[str] = mapped_column(
		String(50), nullable=False, server_default=text("'free'")
	)
	subscription_tier: Mapped[str | None] = mapped_column(String(50), nullable=True)
	subscription_current_period_end: Mapped[datetime | None] = mapped_column(
		TIMESTAMP(timezone=True), nullable=True
	)

	is_active: Mapped[bool] = mapped_column(
		Boolean, default=True, server_default=text("true"), nullable=False
	)
	is_banned: Mapped[bool] = mapped_column(
		Boolean, server_default=text("false"), nullable=False
	)
	ban_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
	banned_until: Mapped[datetime | None] = mapped_column(
		TIMESTAMP(timezone=True), nullable=True
	)
	role: Mapped[UserRole] = mapped_column(
		Enum(UserRole, values_callable=lambda x: [e.value for e in x]),
		default=UserRole.USER,
		nullable=False,
	)
	is_superuser: Mapped[bool] = mapped_column(
		Boolean, default=False, server_default=text("false"), nullable=False
	)
	created_at: Mapped[datetime] = mapped_column(
		TIMESTAMP(timezone=True),
		default=lambda: datetime.now(timezone.utc),
		server_default=func.now(),
		nullable=False,
	)
	updated_at: Mapped[datetime] = mapped_column(
		TIMESTAMP(timezone=True),
		default=lambda: datetime.now(timezone.utc),
		onupdate=lambda: datetime.now(timezone.utc),
		server_default=func.now(),
		nullable=False,
	)
	last_login: Mapped[datetime | None] = mapped_column(
		TIMESTAMP(timezone=True), nullable=True
	)
	password_changed_at: Mapped[datetime | None] = mapped_column(
		TIMESTAMP(timezone=True), nullable=True
	)
	failed_login_attempts: Mapped[int] = mapped_column(
		Integer, server_default=text("0"), nullable=False
	)
	locked_until: Mapped[datetime | None] = mapped_column(
		TIMESTAMP(timezone=True), nullable=True
	)
	signals_received_count: Mapped[int] = mapped_column(
		Integer, server_default=text("0"), nullable=False
	)
	api_request_count_last_hour: Mapped[int] = mapped_column(
		Integer, server_default=text("0"), nullable=False
	)
	last_api_request_at: Mapped[datetime | None] = mapped_column(
		TIMESTAMP(timezone=True), nullable=True
	)
	positions: Mapped[list["Position"]] = relationship(
		"Position", back_populates="user", cascade="all, delete-orphan"
	)
	portfolios: Mapped[list["Portfolio"]] = relationship(
		"Portfolio", back_populates="user", cascade="all, delete-orphan"
	)

	# Индексы для частых запросов
	__table_args__ = (
		Index("ix_users_role", "role"),
		Index("ix_users_is_banned", "is_banned"),
		UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
		UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
		Index(
			"ix_users_telegram_id",
			"telegram_id",
			unique=True,
			postgresql_where=text("telegram_id IS NOT NULL"),
		),
	)


class Position(TenantBase):
	__tablename__ = "positions"

	id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid7)
	user_id: Mapped[UUID] = mapped_column(
		ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
	)
	ticker_id: Mapped[UUID] = mapped_column(
		ForeignKey("tickers.id", ondelete="CASCADE"), nullable=False, index=True
	)

	position_type: Mapped[str] = mapped_column(
		String(10), nullable=False, server_default="long"
	)

	quantity: Mapped[Decimal] = mapped_column(
		Numeric(precision=18, scale=8), nullable=False
	)
	average_buy_price: Mapped[Decimal] = mapped_column(
		Numeric(precision=18, scale=8), nullable=False
	)
	total_cost: Mapped[Decimal] = mapped_column(
		Numeric(precision=18, scale=8), nullable=False
	)

	opened_at: Mapped[datetime] = mapped_column(
		DateTime(timezone=True), nullable=False, server_default=func.now()
	)
	closed_at: Mapped[datetime | None] = mapped_column(
		DateTime(timezone=True), nullable=True
	)

	notes: Mapped[str | None] = mapped_column(Text, nullable=True)

	user: Mapped[User] = relationship("User", back_populates="positions")
	portfolio_id: Mapped[UUID | None] = mapped_column(
		ForeignKey("portfolios.id", ondelete="SET NULL"), nullable=True, index=True
	)
	portfolio: Mapped[Portfolio | None] = relationship(
		"Portfolio", back_populates="positions"
	)
	ticker: Mapped[Ticker] = relationship("Ticker")

	__table_args__ = (
		CheckConstraint(
			"position_type IN ('long', 'short')", name="valid_position_type"
		),
		Index("ix_positions_tenant_user_ticker", "tenant_id", "user_id", "ticker_id"),
		Index("ix_positions_tenant_user_type", "tenant_id", "user_id", "position_type"),
		Index(
			"uq_active_position_per_tenant_user_ticker_type",
			"tenant_id",
			"user_id",
			"ticker_id",
			"position_type",
			postgresql_where=text("closed_at IS NULL"),
			unique=True,
		),
	)
