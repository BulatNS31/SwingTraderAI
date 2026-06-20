from __future__ import annotations

import asyncio
from typing import Optional
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.services.market_data.market_cache_service import (
	MarketCacheService,
)
from swingtraderai.api.services.market_data.market_data_service import MarketDataService
from swingtraderai.db.models.ticker import Ticker
from swingtraderai.db.session import AsyncSessionLocal


async def _collect_and_save(session: AsyncSession) -> None:
	# fetch active tickers
	q = await session.execute(Ticker.select())
	tickers = q.scalars().all()
	symbols = [t.symbol for t in tickers]
	if not symbols:
		return

	mds = MarketDataService()
	quotes = await mds.get_quotes(symbols)
	cache = MarketCacheService(session)
	tenant_id: Optional[UUID] = tickers[0].tenant_id if tickers else None
	if tenant_id is None:
		return

	await cache.save_quotes(tenant_id, quotes)


def start_scheduler() -> None:
	scheduler = AsyncIOScheduler()
	scheduler.add_job(
		lambda: asyncio.create_task(_run_job()),
		"interval",
		seconds=60,
		id="market_quotes",
	)
	scheduler.start()


async def _run_job() -> None:
	async with AsyncSessionLocal() as session:
		await _collect_and_save(session)


if __name__ == "__main__":
	start_scheduler()
