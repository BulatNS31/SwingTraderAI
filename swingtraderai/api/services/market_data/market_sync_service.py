from typing import List
from uuid import UUID

from swingtraderai.api.repositories.market_quote_repository import (
	MarketQuoteRepository,
)
from swingtraderai.api.services.market_data.providers.base import (
	BaseMarketProvider,
)
from swingtraderai.api.services.ticker_service import TickerService
from swingtraderai.db.models.market_quote import MarketQuoteSnapshot


class MarketSyncService:
	def __init__(
		self,
		repository: MarketQuoteRepository,
		ticker_service: TickerService,
	):
		self.repository = repository
		self.ticker_service = ticker_service

	async def sync(
		self,
		tenant_id: UUID,
		provider: BaseMarketProvider,
		exchange_id: UUID,
	) -> List[MarketQuoteSnapshot]:
		"""
		Синхронизация только активных тикеров,
		выбранных администратором.
		"""
		tickers = await self.ticker_service.get_active_by_exchange(exchange_id)

		if not tickers:
			return []

		symbols = [ticker.symbol for ticker in tickers]

		quotes = await provider.get_quotes(symbols)

		result = []

		ticker_map = {ticker.symbol: ticker for ticker in tickers}

		for quote in quotes:
			if quote.price is None:
				continue

			ticker = ticker_map.get(quote.symbol)

			if not ticker:
				continue

			item = await self.repository.upsert_from_quote(
				tenant_id=tenant_id,
				ticker_id=ticker.id,
				quote=quote,
			)

			if item:
				result.append(item)

		return result
