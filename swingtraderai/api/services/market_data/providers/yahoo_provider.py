from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx

from swingtraderai.api.services.market_data.providers.base import BaseMarketProvider
from swingtraderai.schemas.exchanges import Exchanges
from swingtraderai.schemas.market_data import MarketQuoteSchema


class YahooProvider(BaseMarketProvider):
	"""Provider using Yahoo Finance chart API."""

	BASE_URL = "https://query1.finance.yahoo.com/v8/finance/chart"

	PARAMS = {
		"interval": "1m",
		"range": "1d",
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
		price = None
		change_percent = None
		volume = None

		try:
			response = await client.get(
				f"{self.BASE_URL}/{symbol}",
				params=self.PARAMS,
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
			exchange_code=Exchanges.NYSE.code,
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
		try:
			result = data["chart"]["result"][0]

			meta = result.get("meta", {})
			quotes = result.get("indicators", {}).get("quote", [])

			if not quotes:
				return None, None, None

			quote = quotes[0]

			closes = quote.get("close", [])
			volumes = quote.get("volume", [])

			price = None
			volume = None

			for value in reversed(closes):
				if value is not None:
					price = value
					break

			for value in reversed(volumes):
				if value is not None:
					volume = value
					break

			previous_close = meta.get("previousClose")

			change_percent = None

			if price is not None and previous_close:
				change_percent = (price - previous_close) / previous_close * 100

			return (
				price,
				change_percent,
				volume,
			)

		except (
			KeyError,
			IndexError,
			TypeError,
			ValueError,
		):
			return None, None, None
