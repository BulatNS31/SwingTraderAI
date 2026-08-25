from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.api.repositories.base import TenantAwareRepository
from swingtraderai.db.models.market import Exchange, Ticker
from swingtraderai.db.models.market_quote import MarketQuoteSnapshot
from swingtraderai.schemas.market_data import MarketQuoteSchema


class MarketQuoteRepository(TenantAwareRepository[MarketQuoteSnapshot]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, MarketQuoteSnapshot)

	async def get_by_ticker_id(
		self, tenant_id: UUID, ticker_id: UUID
	) -> Optional[MarketQuoteSnapshot]:
		"""Получение snapshot котировки напрямую по ticker_id."""
		query = (
			self._get_tenant_query(tenant_id)
			.where(MarketQuoteSnapshot.ticker_id == ticker_id)
			.options(joinedload(MarketQuoteSnapshot.ticker))
		)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_by_market_type(
		self, tenant_id: UUID, market_type: str, limit: int = 200
	) -> Sequence[MarketQuoteSnapshot]:
		"""market_type — это код биржи (moex, spb, etc.)"""
		query = (
			self._get_tenant_query(tenant_id)
			.join(Ticker, Ticker.id == MarketQuoteSnapshot.ticker_id)
			.join(Exchange, Ticker.exchange_id == Exchange.id)
			.where(Exchange.code == market_type)
			.order_by(MarketQuoteSnapshot.updated_at.desc())
			.limit(limit)
			.options(joinedload(MarketQuoteSnapshot.ticker))
		)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def upsert_by_symbol(
		self, tenant_id: UUID, symbol: str, quote: MarketQuoteSchema
	) -> Optional[MarketQuoteSnapshot]:
		"""Обновить или создать котировку по символу."""
		# Находим тикер
		ticker_query = select(Ticker).where(Ticker.symbol == symbol.upper())
		ticker_result = await self.session.execute(ticker_query)
		ticker = ticker_result.scalar_one_or_none()

		if not ticker:
			return None

		return await self.upsert_from_quote(tenant_id, ticker.id, quote)

	async def upsert_from_quote(
		self, tenant_id: UUID, ticker_id: UUID, quote: MarketQuoteSchema
	) -> MarketQuoteSnapshot:
		"""
		Создает или обновляет snapshot котировки по ticker_id.
		Поиск и создание Ticker выполняется снаружи (в Service).
		"""
		existing = await self.get_by_ticker_id(tenant_id, ticker_id)

		price_val = Decimal(str(quote.price)) if quote.price is not None else None
		change_val = (
			Decimal(str(quote.change_percent))
			if quote.change_percent is not None
			else None
		)
		volume_val = Decimal(str(quote.volume)) if quote.volume is not None else None

		if existing:
			existing.price = price_val
			existing.change_percent = change_val
			existing.volume = volume_val
			existing.updated_at = quote.updated_at
			await self.session.commit()
			await self.session.refresh(existing)
			return existing

		snapshot = MarketQuoteSnapshot(
			ticker_id=ticker_id,
			tenant_id=tenant_id,
			price=price_val,
			change_percent=change_val,
			volume=volume_val,
			updated_at=quote.updated_at,
		)
		self.session.add(snapshot)
		await self.session.commit()
		await self.session.refresh(snapshot)
		return snapshot

	async def list_recent(
		self, tenant_id: UUID, limit: int = 500
	) -> Sequence[MarketQuoteSnapshot]:
		query = (
			self._get_tenant_query(tenant_id)
			.order_by(MarketQuoteSnapshot.updated_at.desc())
			.limit(limit)
			.options(joinedload(MarketQuoteSnapshot.ticker))
		)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_latest_by_ticker(
		self, tenant_id: UUID, ticker_id: UUID
	) -> Optional[MarketQuoteSnapshot]:
		"""Получить последний котировку для конкретного тикера."""
		query = (
			self._get_tenant_query(tenant_id)
			.where(MarketQuoteSnapshot.ticker_id == ticker_id)
			.order_by(desc(MarketQuoteSnapshot.updated_at))
			.limit(1)
			.options(joinedload(MarketQuoteSnapshot.ticker))
		)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	# ✅ НОВЫЙ МЕТОД: Получить котировку по символу
	async def get_by_symbol(
		self, tenant_id: UUID, symbol: str
	) -> Optional[MarketQuoteSnapshot]:
		"""Получить последний котировку по символу тикера."""
		# Сначала находим тикер по символу
		ticker_query = select(Ticker).where(Ticker.symbol == symbol.upper())
		ticker_result = await self.session.execute(ticker_query)
		ticker = ticker_result.scalar_one_or_none()

		if not ticker:
			return None

		# Получаем последний котировку для этого тикера
		return await self.get_latest_by_ticker(tenant_id, ticker.id)
