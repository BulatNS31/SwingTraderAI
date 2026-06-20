from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional

import ccxt.async_support as ccxt

from swingtraderai.api.services.market_data.providers.base import BaseMarketProvider
from swingtraderai.schemas.market_data import MarketQuoteSchema


class CCXTProvider(BaseMarketProvider):
	"""Provider using CCXT async support. Default exchange: Binance."""

	def __init__(self, exchange_name: str = "binance"):
		self.exchange_name = exchange_name
		self._exchange: Optional[ccxt.Exchange] = None

	async def _get_exchange(self) -> ccxt.Exchange:
		if self._exchange is None:
			self._exchange = getattr(ccxt, self.exchange_name)({})()
		return self._exchange

	async def get_quote(self, symbol: str) -> MarketQuoteSchema:
		exchange = await self._get_exchange()
		try:
			ticker = await exchange.fetch_ticker(symbol)
			price = ticker.get("last")
			change = ticker.get("percentage")
			volume = ticker.get("baseVolume") or ticker.get("quoteVolume")
		finally:
			pass

		return MarketQuoteSchema(
			symbol=symbol,
			price=Decimal(price) if price is not None else Decimal("0"),
			change_percent=float(change) if change is not None else 0.0,
			volume=float(volume) if volume is not None else None,
			market_type="crypto",
			updated_at=datetime.now(timezone.utc),
		)

	async def get_quotes(self, symbols: List[str]) -> List[MarketQuoteSchema]:
		exchange = await self._get_exchange()
		results = []
		for s in symbols:
			ticker = await exchange.fetch_ticker(s)
			price = ticker.get("last")
			change = ticker.get("percentage")
			volume = ticker.get("baseVolume") or ticker.get("quoteVolume")
			results.append(
				MarketQuoteSchema(
					symbol=s,
					price=Decimal(price) if price is not None else Decimal("0"),
					change_percent=float(change) if change is not None else 0.0,
					volume=float(volume) if volume is not None else None,
					market_type="crypto",
					updated_at=datetime.now(timezone.utc),
				)
			)
		return results
