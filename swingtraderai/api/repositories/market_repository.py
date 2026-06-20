from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.db.models.market import Exchange, MarketData, Ticker

from .base import BaseRepository


class MarketRepository(BaseRepository[MarketData]):
	"""Репозиторий для агрегации последних MarketData по тикерам"""

	def __init__(self, session: AsyncSession):
		super().__init__(session, MarketData)

	async def get_latest_per_ticker(
		self,
		skip: int = 0,
		limit: int = 100,
		asset_type: Optional[str] = None,
		exchange_code: Optional[str] = None,
		timeframe: Optional[str] = None,
	) -> Sequence[MarketData]:
		"""Вернуть последние MarketData для каждого тикера с опциональными фильтрами"""

		# Подзапрос для получения последней метки времени по тикеру
		subq = (
			select(
				MarketData.ticker_id,
				func.max(MarketData.timestamp).label("ts"),
			)
			.group_by(MarketData.ticker_id)
			.subquery()
		)

		stmt = (
			select(MarketData)
			.join(
				subq,
				(MarketData.ticker_id == subq.c.ticker_id)
				& (MarketData.timestamp == subq.c.ts),
			)
			.join(Ticker, Ticker.id == MarketData.ticker_id)
			.options(joinedload(MarketData.ticker).joinedload(Ticker.exchange_ref))
			.offset(skip)
			.limit(limit)
			.order_by(MarketData.timestamp.desc())
		)

		if timeframe:
			stmt = stmt.where(MarketData.timeframe == timeframe)

		if asset_type:
			stmt = stmt.where(Ticker.asset_type == asset_type)

		if exchange_code:
			stmt = stmt.join(Exchange, Exchange.id == Ticker.exchange_id).where(
				func.upper(Exchange.code) == exchange_code.upper()
			)

		result = await self.session.execute(stmt)
		rows = result.scalars().all()

		# return list of MarketData with related ticker loaded (via relationship)
		return rows
