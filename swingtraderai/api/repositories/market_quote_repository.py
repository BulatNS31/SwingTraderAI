from decimal import Decimal
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.api.repositories.base import TenantAwareRepository
from swingtraderai.db.models.market import Exchange, Ticker
from swingtraderai.db.models.market_quote import MarketQuoteSnapshot
from swingtraderai.schemas.market_data import MarketQuoteSchema


class MarketQuoteRepository(TenantAwareRepository[MarketQuoteSnapshot]):
	def __init__(self, session: AsyncSession):
		super().__init__(session, MarketQuoteSnapshot)

	async def get_by_symbol(
		self, tenant_id: UUID, symbol: str
	) -> Optional[MarketQuoteSnapshot]:
		query = (
			self._get_tenant_query(tenant_id)
			.join(Ticker, Ticker.id == MarketQuoteSnapshot.ticker_id)
			.where(Ticker.symbol == symbol)
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

	async def upsert_from_quote(
		self, tenant_id: UUID, quote: MarketQuoteSchema
	) -> Optional[MarketQuoteSnapshot]:
		query = select(Ticker).where(Ticker.symbol == quote.symbol).limit(1)
		res = await self.session.execute(query)
		ticker = res.scalar_one_or_none()

		if not ticker:
			return None

		existing = await self.get_by_symbol(tenant_id, quote.symbol)
		if existing:
			existing.price = (
				Decimal(str(quote.price)) if quote.price is not None else None
			)
			existing.change_percent = (
				Decimal(str(quote.change_percent))
				if quote.change_percent is not None
				else None
			)
			existing.volume = (
				Decimal(str(quote.volume)) if quote.volume is not None else None
			)
			existing.updated_at = quote.updated_at
			await self.session.commit()
			await self.session.refresh(existing)
			return existing

		snapshot = MarketQuoteSnapshot(
			ticker_id=ticker.id,
			tenant_id=tenant_id,
			price=Decimal(str(quote.price)) if quote.price is not None else None,
			change_percent=(
				float(quote.change_percent)
				if quote.change_percent is not None
				else None
			),
			volume=Decimal(str(quote.volume)) if quote.volume is not None else None,
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
		)
		result = await self.session.execute(query)
		return result.scalars().all()
