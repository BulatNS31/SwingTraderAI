from __future__ import annotations

from typing import List

from swingtraderai.api.services.market_data.providers.ccxt_provider import CCXTProvider
from swingtraderai.api.services.market_data.providers.moex_provider import MoexProvider
from swingtraderai.api.services.market_data.providers.yahoo_provider import (
	YahooProvider,
)
from swingtraderai.schemas.market_data import MarketQuoteSchema


class MarketDataService:
	def __init__(self, default_crypto_exchange: str = "binance") -> None:
		self.ccxt = CCXTProvider(exchange_name=default_crypto_exchange)
		self.yahoo = YahooProvider()
		self.moex = MoexProvider()

	def _detect_market(self, symbol: str) -> str:
		s = symbol.upper()
		if "/" in s:
			return "crypto"
		if s.endswith(".ME"):
			return "moex"
		return "us"

	async def get_quote(self, symbol: str) -> MarketQuoteSchema:
		market = self._detect_market(symbol)
		if market == "crypto":
			return await self.ccxt.get_quote(symbol)
		if market == "moex":
			return await self.moex.get_quote(symbol)
		return await self.yahoo.get_quote(symbol)

	async def get_quotes(self, symbols: List[str]) -> List[MarketQuoteSchema]:
		# group by market
		groups: dict[str, list[str]] = {}
		for s in symbols:
			m = self._detect_market(s)
			groups.setdefault(m, []).append(s)

		results: List[MarketQuoteSchema] = []
		for m, syms in groups.items():
			if m == "crypto":
				results.extend(await self.ccxt.get_quotes(syms))
			elif m == "moex":
				results.extend(await self.moex.get_quotes(syms))
			else:
				results.extend(await self.yahoo.get_quotes(syms))
		return results
