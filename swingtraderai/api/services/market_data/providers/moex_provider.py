from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

import httpx

from swingtraderai.api.services.market_data.providers.base import BaseMarketProvider
from swingtraderai.schemas.exchanges import Exchanges
from swingtraderai.schemas.market_data import MarketQuoteSchema


class MoexProvider(BaseMarketProvider):
	BASE_URL = "https://iss.moex.com/iss/engines/stock/markets/shares/securities"

	PARAMS = {
		"iss.only": "marketdata,securities",
		"marketdata.columns": "LAST,MARKETPRICE,LASTTOPREVPRICE,VOLTODAY",
		"securities.columns": "PREVPRICE",
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
		url = f"{self.BASE_URL}/{symbol}.json"

		try:
			response = await client.get(url, params=self.PARAMS)
			response.raise_for_status()

			data = response.json()

			price, change_percent, volume = self._extract_market_data(data)

		except httpx.HTTPError:
			price = None
			change_percent = None
			volume = None

		return MarketQuoteSchema(
			symbol=symbol,
			price=Decimal(str(price)) if price is not None else Decimal("0"),
			change_percent=float(change_percent) if change_percent is not None else 0.0,
			volume=float(volume) if volume is not None else None,
			exchange_code=Exchanges.MOEX.code,
			updated_at=datetime.now(timezone.utc),
		)

	def _extract_market_data(
		self,
		data: Dict[str, Any],
	) -> Tuple[Optional[float], Optional[float], Optional[float]]:
		"""
		Извлекает цену, изменение и объём из ответа MOEX ISS.
		"""

		try:
			marketdata = data.get("marketdata", {})
			columns = marketdata.get("columns", [])
			rows = marketdata.get("data", [])

			if not rows:
				return None, None, None

			row = dict(zip(columns, rows[0], strict=False))

			price = row.get("LAST") or row.get("MARKETPRICE") or row.get("PREVPRICE")

			change_percent = row.get("LASTTOPREVPRICE")
			volume = row.get("VOLTODAY")

			return price, change_percent, volume

		except (KeyError, IndexError, TypeError):
			return None, None, None
