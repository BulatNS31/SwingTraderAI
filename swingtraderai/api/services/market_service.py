from statistics import mean
from typing import List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.repositories.market_repository import MarketRepository
from swingtraderai.api.repositories.ticker_repository import TickerRepository
from swingtraderai.db.models.market import MarketData
from swingtraderai.schemas.market import (
	MarketAsset,
	MarketHeatmapItem,
	MarketPulse,
	MarketsSnapshot,
)


class MarketService:
	def __init__(self, session: AsyncSession):
		self.session = session
		self.repo = MarketRepository(session)
		self.ticker_repo = TickerRepository(session)

	async def _to_asset(self, md: MarketData) -> MarketAsset:
		ticker = md.ticker
		last_price = float(md.close) if md.close is not None else None
		open_price = float(md.open) if md.open is not None else None
		change = None
		if last_price is not None and open_price is not None:
			try:
				change = (
					((last_price - open_price) / open_price) * 100
					if open_price != 0
					else 0.0
				)
			except Exception:
				change = 0.0

		volume = float(md.volume) if md.volume is not None else None

		exchange_code = None
		if ticker is not None and ticker.exchange_ref is not None:
			exchange_code = ticker.exchange_ref.code

		return MarketAsset(
			id=md.id,
			ticker_id=md.ticker_id,
			symbol=(ticker.symbol if ticker is not None else ""),
			exchange=exchange_code,
			asset_type=(ticker.asset_type if ticker is not None else None),
			last_price=last_price,
			change_percent=change,
			volume=volume,
			timestamp=md.timestamp,
		)

	async def get_snapshot(
		self,
		tenant_id: Optional[UUID] = None,
		page: int = 1,
		per_page: int = 100,
		timeframe: Optional[str] = None,
	) -> MarketsSnapshot:
		skip = max(page - 1, 0) * per_page

		rows = await self.repo.get_latest_per_ticker(
			skip=skip, limit=per_page * 3, timeframe=timeframe
		)

		assets: List[MarketAsset] = []
		for row in rows:
			assets.append(await self._to_asset(row))

		# partition
		crypto = [
			a for a in assets if (a.asset_type and a.asset_type.lower() == "crypto")
		][:per_page]
		moex = [a for a in assets if (a.exchange and a.exchange.lower() == "moex")][
			:per_page
		]
		nasdaq = [a for a in assets if (a.exchange and a.exchange.lower() == "nasdaq")][
			:per_page
		]

		# heatmap: top movers by absolute change_percent
		movers = [a for a in assets if a.change_percent is not None]
		movers_sorted = sorted(
			movers,
			key=lambda x: abs(
				float(x.change_percent) if x.change_percent is not None else 0.0
			),
			reverse=True,
		)[:per_page]
		heatmap = [
			MarketHeatmapItem(
				symbol=a.symbol,
				name=None,
				exchange=a.exchange,
				change_percent=a.change_percent or 0.0,
			)
			for a in movers_sorted
		]

		# pulse: simple aggregation
		changes: List[float] = [
			float(c)
			for c in [a.change_percent for a in assets if a.change_percent is not None]
		]
		gainers = sum(1 for c in changes if c > 0)
		losers = sum(1 for c in changes if c < 0)
		neutral = sum(1 for c in changes if abs(c) < 0.0001)
		avg_change = float(mean(changes)) if changes else 0.0

		pulse = MarketPulse(
			total=len(assets),
			gainers=gainers,
			losers=losers,
			neutral=neutral,
			avg_change_percent=avg_change,
		)

		return MarketsSnapshot(
			crypto=crypto, moex=moex, nasdaq=nasdaq, heatmap=heatmap, pulse=pulse
		)
