from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import List, Optional, Tuple

import yfinance as yf

from swingtraderai.api.services.market_data.providers.base import BaseMarketProvider
from swingtraderai.schemas.market_data import MarketQuoteSchema


class YahooProvider(BaseMarketProvider):
	"""Provider using yfinance (supports MOEX .ME tickers, US stocks, ETFs, indices)."""

	async def get_quote(self, symbol: str) -> MarketQuoteSchema:
		loop = asyncio.get_running_loop()

		def fetch(s: str) -> Tuple[Optional[float], Optional[float], Optional[float]]:
			t = yf.Ticker(s)
			info = t.history(period="1d", interval="1m")
			if info.empty:
				# fallback to info dict
				data = t.info
				price = data.get("regularMarketPrice")
				change = data.get("regularMarketChangePercent")
				vol = data.get("volume")
			else:
				last = info.iloc[-1]
				price = last.get("Close")
				prev = info.iloc[0].get("Close") if len(info) > 1 else None
				change = None
				if prev and price:
					try:
						change = float((price - prev) / prev * 100)
					except Exception:
						change = None
				vol = last.get("Volume") if "Volume" in info.columns else None

			return price, change, vol

		price, change_percent, volume = await loop.run_in_executor(None, fetch, symbol)

		return MarketQuoteSchema(
			symbol=symbol,
			price=Decimal(price) if price is not None else Decimal("0"),
			change_percent=float(change_percent) if change_percent is not None else 0.0,
			volume=float(volume) if volume is not None else None,
			market_type="moex" if symbol.upper().endswith(".ME") else "us",
			updated_at=datetime.now(timezone.utc),
		)

	async def get_quotes(self, symbols: List[str]) -> List[MarketQuoteSchema]:
		tasks = [self.get_quote(s) for s in symbols]
		return await asyncio.gather(*tasks)
