from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx

from swingtraderai.api.services.market_data.providers.base import BaseMarketProvider
from swingtraderai.schemas.exchanges import Exchanges
from swingtraderai.schemas.market_data import MarketQuoteSchema


class BybitProvider(BaseMarketProvider):
	"""Provider using Bybit public API V5."""

	BASE_URL = "https://api.bybit.com"

	TICKER_URL = "/v5/market/tickers"

	PARAMS = {
		"category": "spot",
	}

	async def get_quote(self, symbol: str) -> MarketQuoteSchema:
		async with httpx.AsyncClient(timeout=10) as client:
			return await self._get_quote_with_client(client, symbol)

	async def get_quotes(self, symbols: List[str]) -> List[MarketQuoteSchema]:
		async with httpx.AsyncClient(timeout=10) as client:
			tasks = [self._get_quote_with_client(client, symbol) for symbol in symbols]

			return await asyncio.gather(*tasks)

	async def _get_quote_with_client(
		self,
		client: httpx.AsyncClient,
		symbol: str,
	) -> MarketQuoteSchema:
		params = {
			**self.PARAMS,
			"symbol": symbol.replace("/", ""),
		}

		price = None
		change_percent = None
		volume = None

		try:
			response = await client.get(
				f"{self.BASE_URL}{self.TICKER_URL}",
				params=params,
			)

			response.raise_for_status()

			data = response.json()

			price, change_percent, volume = self._extract_market_data(data)

		except httpx.HTTPError:
			pass

		return MarketQuoteSchema(
			symbol=symbol,
			price=Decimal(str(price)) if price is not None else Decimal("0"),
			change_percent=float(change_percent) if change_percent is not None else 0.0,
			volume=float(volume) if volume is not None else None,
			exchange_code=Exchanges.BYBIT.code,
			updated_at=datetime.now(timezone.utc),
		)

	def _extract_market_data(
		self,
		data: Dict[str, Any],
	) -> Tuple[
		Optional[float],
		Optional[float],
		Optional[float],
	]:
		"""
		Extract data from Bybit V5 ticker response.
		"""

		try:
			result = data.get("result", {})
			list_data = result.get("list", [])

			if not list_data:
				return None, None, None

			ticker = list_data[0]

			price = ticker.get("lastPrice")

			change_percent = ticker.get("price24hPcnt")
			if change_percent is not None:
				change_percent = float(change_percent) * 100

			volume = ticker.get("volume24h")

			return (
				float(price) if price else None,
				change_percent,
				float(volume) if volume else None,
			)

		except (KeyError, IndexError, TypeError, ValueError):
			return None, None, None
