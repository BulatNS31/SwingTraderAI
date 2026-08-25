from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.db.models.market import Ticker

from .base import BaseRepository


class TickerRepository(BaseRepository[Ticker]):
	"""Репозиторий для тикеров (общие данные — без tenant_id)"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, Ticker)

	# Переопределяем методы, так как Ticker не использует tenant_id
	async def get_by_id(self, ticker_id: UUID) -> Optional[Ticker]:
		result = await self.session.get(Ticker, ticker_id)
		if result:
			await self.session.refresh(result, ["exchange_ref"])
		return result

	async def get_all(
		self, skip: int = 0, limit: int = 100, **filters: Any
	) -> List[Ticker]:
		query = (
			select(Ticker)
			.offset(skip)
			.limit(limit)
			.order_by(Ticker.symbol)
			.options(joinedload(Ticker.exchange_ref))
		)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def search(self, q: str, limit: int = 20) -> List[Ticker]:
		search_term = f"%{q.lower()}%"
		query = (
			select(Ticker)
			.where(
				or_(
					Ticker.symbol.ilike(search_term),
					Ticker.asset_type.ilike(search_term),
				)
			)
			.order_by(Ticker.symbol)
			.limit(limit)
			.options(joinedload(Ticker.exchange_ref))
		)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def get_by_symbol(self, symbol: str) -> Optional[Ticker]:
		query = select(Ticker).where(Ticker.symbol == symbol.upper())
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_active_by_exchange(self, exchange_id: UUID) -> List[Ticker]:
		"""
		Возвращает активные тикеры для конкретной биржи.
		"""
		query = (
			select(Ticker)
			.where(Ticker.exchange_id == exchange_id)
			.where(Ticker.is_active)
			.order_by(Ticker.symbol)
			.options(joinedload(Ticker.exchange_ref))
		)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def bulk_create_or_update(
		self, tickers_data: List[Dict[str, Any]]
	) -> List[Ticker]:
		created = []
		for data in tickers_data:
			symbol = data.get("symbol")
			existing = await self.get_by_symbol(str(symbol))

			if existing:
				for key, value in data.items():
					if key != "id" and hasattr(existing, key):
						setattr(existing, key, value)
				created.append(existing)
			else:
				new_ticker = Ticker(**data)
				self.session.add(new_ticker)
				created.append(new_ticker)

		await self.session.commit()
		for t in created:
			await self.session.refresh(t)
		return created
