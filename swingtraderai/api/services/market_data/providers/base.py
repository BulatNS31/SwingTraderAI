from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from swingtraderai.schemas.market_data import MarketQuoteSchema


class BaseMarketProvider(ABC):
	"""Base interface for market data providers."""

	@abstractmethod
	async def get_quote(self, symbol: str) -> MarketQuoteSchema:
		raise NotImplementedError()

	@abstractmethod
	async def get_quotes(self, symbols: List[str]) -> List[MarketQuoteSchema]:
		raise NotImplementedError()
