from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.db.models.market import Exchange

from .base import BaseRepository


class ExchangeRepository(BaseRepository[Exchange]):
	"""Репозиторий для работы с биржами."""

	def __init__(self, session: AsyncSession):
		super().__init__(session, Exchange)

	async def get_by_code(self, code: str) -> Optional[Exchange]:
		"""Получить биржу по коду."""
		query = select(Exchange).where(Exchange.code == code.upper())
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_by_name(self, name: str) -> Optional[Exchange]:
		"""Получить биржу по названию."""
		query = select(Exchange).where(Exchange.name.ilike(f"%{name}%"))
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_all(
		self,
		skip: int = 0,
		limit: int = 100,
		**filters: Any,  # ✅ Сохраняем сигнатуру родителя
	) -> List[Exchange]:
		"""
		Получить все биржи с пагинацией и фильтрацией.
		"""
		query = select(Exchange).order_by(Exchange.name)

		# Применяем фильтры
		for field, value in filters.items():
			if hasattr(self.model, field):
				query = query.where(getattr(self.model, field) == value)

		# Применяем пагинацию
		if skip:
			query = query.offset(skip)
		if limit:
			query = query.limit(limit)

		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def get_all_without_pagination(self) -> List[Exchange]:
		"""
		Получить все биржи без пагинации (удобно для небольших списков).
		"""
		query = select(Exchange).order_by(Exchange.name)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def get_or_create(
		self,
		code: str,
		name: str,
		timezone: str = "UTC",
		currency: str = "USD",
		**kwargs: Any,
	) -> Exchange:
		"""Получить биржу по коду или создать новую."""
		exchange = await self.get_by_code(code)
		if exchange:
			return exchange

		exchange_data: Dict[str, Any] = {
			"code": code.upper(),
			"name": name,
			"timezone": timezone,
			"currency": currency,
			**kwargs,
		}

		exchange = Exchange(**exchange_data)
		self.session.add(exchange)
		await self.session.commit()
		await self.session.refresh(exchange)
		return exchange

	async def get_by_currency(self, currency: str) -> List[Exchange]:
		"""Получить биржи по валюте."""
		query = select(Exchange).where(Exchange.currency == currency.upper())
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def get_by_timezone(self, timezone: str) -> List[Exchange]:
		"""Получить биржи по часовому поясу."""
		query = select(Exchange).where(Exchange.timezone == timezone)
		result = await self.session.execute(query)
		return list(result.scalars().all())
