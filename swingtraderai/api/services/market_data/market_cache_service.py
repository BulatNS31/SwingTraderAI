from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.repositories.market_quote_repository import MarketQuoteRepository
from swingtraderai.schemas.market_data import MarketQuoteSchema


class MarketCacheService:
	def __init__(self, session: AsyncSession):
		self.session = session
		self.repo = MarketQuoteRepository(session)

	async def save_quotes(
		self, tenant_id: UUID, quotes: List[MarketQuoteSchema]
	) -> None:
		for q in quotes:
			await self.repo.upsert_by_symbol(tenant_id, q.symbol, q)

	async def get_snapshot(self, tenant_id: UUID) -> Dict[str, Any]:
		# return grouped snapshot
		crypto = await self.repo.get_by_market_type(tenant_id, "crypto")
		moex = await self.repo.get_by_market_type(tenant_id, "moex")
		us = await self.repo.get_by_market_type(tenant_id, "us")
		return {"crypto": crypto, "moex": moex, "us": us}

	async def get_quote(self, tenant_id: UUID, symbol: str) -> Optional[Any]:
		return await self.repo.get_by_symbol(tenant_id, symbol)
