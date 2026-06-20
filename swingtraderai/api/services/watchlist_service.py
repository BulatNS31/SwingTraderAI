from typing import Any, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.repositories.watchlist_repository import (
	WatchlistItemRepository,
	WatchlistRepository,
)
from swingtraderai.db.models.market import MarketData, Ticker
from swingtraderai.db.models.system import Watchlist, WatchlistItem
from swingtraderai.schemas.watchlist import (
	AIInsight,
	AnalysisConfig,
	AnalysisResult,
	SignalType,
	WatchlistCreate,
	WatchlistDataItem,
	WatchlistItemCreate,
	WatchlistItemUpdate,
	WatchlistStats,
)


class WatchlistService:
	"""Сервис для управления списком наблюдения пользователя"""

	def __init__(self, session: AsyncSession):
		self.session = session
		self.item_repo = WatchlistItemRepository(session)
		self.watchlist_repo = WatchlistRepository(session)

	def _calculate_score(self, change_pct: float, signals: list[str]) -> int:
		"""Рассчитывает общий score."""
		score = 0

		if change_pct > AnalysisConfig.THRESHOLDS["strong_bullish"]:
			score += AnalysisConfig.SCORES["strong_bullish"]
		elif change_pct > AnalysisConfig.THRESHOLDS["bullish"]:
			score += AnalysisConfig.SCORES["bullish"]
		elif change_pct < AnalysisConfig.THRESHOLDS["strong_bearish"]:
			score += AnalysisConfig.SCORES["strong_bearish"]
		elif change_pct < AnalysisConfig.THRESHOLDS["bearish"]:
			score += AnalysisConfig.SCORES["bearish"]

		for signal in signals:
			if signal in (SignalType.TARGET_HIT, SignalType.STOP_LOSS_HIT):
				score += AnalysisConfig.SCORES[signal]

		return score

	def _get_result_by_score(self, score: int) -> AnalysisResult:
		"""Возвращает результат на основе score."""
		for (min_score, max_score), result in AnalysisConfig.RESULT_MAPPING.items():
			if min_score <= score <= max_score:
				return AnalysisResult(*result)

		return AnalysisResult(*AnalysisConfig.NEUTRAL)

	def generate_signal_analysis(
		self,
		change_pct: float,
		signals: List[str],
	) -> AnalysisResult:
		score = self._calculate_score(change_pct, signals)
		return self._get_result_by_score(score)

	def check_signal(self, item: WatchlistItem, price: float) -> list[str]:
		signals = []

		if item.target_price and price >= item.target_price:
			signals.append("TARGET_HIT")

		if item.stop_loss and price <= item.stop_loss:
			signals.append("STOP_LOSS_HIT")

		return signals

	async def add_item(
		self, tenant_id: UUID, user_id: UUID, item_in: WatchlistItemCreate
	) -> WatchlistItem:
		from swingtraderai.db.models.market import Ticker

		ticker = await self.item_repo.session.get(Ticker, item_in.ticker_id)
		if not ticker:
			raise HTTPException(status_code=404, detail="Ticker not found")

		existing = await self.item_repo.get_by_ticker(
			tenant_id, user_id, item_in.ticker_id
		)
		if existing:
			raise HTTPException(status_code=400, detail="Ticker already in watchlist")

		watchlist = await self.watchlist_repo.get_or_create_default(tenant_id, user_id)

		item = await self.item_repo.create_watchlist_item(
			tenant_id=tenant_id,
			watchlist_id=watchlist.id,
			ticker_id=item_in.ticker_id,
			notes=item_in.notes,
			reason=item_in.reason,
			target_price=item_in.target_price,
			stop_loss=item_in.stop_loss,
		)

		return item

	async def create_watchlist(
		self, tenant_id: UUID, user_id: UUID, watchlist_in: WatchlistCreate
	) -> Watchlist:
		"""Создать новый watchlist"""
		query = select(Watchlist).where(
			and_(
				Watchlist.tenant_id == tenant_id,
				Watchlist.owner_id == user_id,
				Watchlist.name == watchlist_in.name,
			)
		)
		result = await self.session.execute(query)
		existing = result.scalar_one_or_none()

		if existing:
			raise HTTPException(
				status_code=400,
				detail=f"Watchlist with name '{watchlist_in.name}' already exists",
			)
		watchlist = Watchlist(
			tenant_id=tenant_id,
			owner_id=user_id,
			name=watchlist_in.name,
			description=watchlist_in.description,
		)
		self.session.add(watchlist)
		await self.session.commit()
		await self.session.refresh(watchlist)

		return watchlist

	async def get_user_items(
		self, tenant_id: UUID, user_id: UUID
	) -> List[WatchlistItem]:
		return await self.item_repo.get_user_watchlist_items(tenant_id, user_id)

	async def update_item(
		self,
		tenant_id: UUID,
		user_id: UUID,
		item_id: UUID,
		update_data: WatchlistItemUpdate,
	) -> WatchlistItem:
		item = await self.item_repo.get_by_id(tenant_id, item_id)
		if not item:
			raise HTTPException(status_code=404, detail="Watchlist item not found")

		watchlist = await self.item_repo.session.get(Watchlist, item.watchlist_id)

		if not watchlist:
			raise HTTPException(status_code=404, detail="Watchlist not found")

		if watchlist.owner_id != user_id:
			raise HTTPException(status_code=403, detail="Not your watchlist item")

		for key, value in update_data.model_dump(exclude_unset=True).items():
			setattr(item, key, value)

		await self.item_repo.session.commit()
		await self.item_repo.session.refresh(item)
		return item

	async def remove_item(self, tenant_id: UUID, user_id: UUID, item_id: UUID) -> bool:
		item = await self.item_repo.get_by_id(tenant_id, item_id)
		if not item:
			raise HTTPException(status_code=404, detail="Item not found")

		watchlist = await self.item_repo.session.get(Watchlist, item.watchlist_id)

		if not watchlist:
			raise HTTPException(status_code=404, detail="Watchlist not found")

		if watchlist.owner_id != user_id:
			raise HTTPException(status_code=403, detail="Not your watchlist item")

		return await self.item_repo.delete(tenant_id, item_id)

	async def get_or_create_default_watchlist(
		self, tenant_id: UUID, user_id: UUID
	) -> Watchlist:
		"""
		Получает или создает дефолтный watchlist для пользователя.
		"""
		default = await self.watchlist_repo.get_or_create_default(tenant_id, user_id)

		if not default:
			watchlist_data = {
				"name": "Default Watchlist",
				"description": "Your default watchlist",
				"owner_id": user_id,
				"tenant_id": tenant_id,
				"is_default": True,
			}
			default = await self.watchlist_repo.create(tenant_id, watchlist_data)

		return default

	async def get_watchlist_with_prices(
		self,
		tenant_id: UUID,
		user_id: UUID,
		limit: int = 50,
		search: str | None = None,
		asset_type: str = "all",
		sort_by: str = "change_percent",
		order: str = "desc",
		include_ai: bool = False,
		include_trend: bool = False,
	) -> List[WatchlistDataItem]:
		"""
		Возвращает watchlist с актуальными ценами и изменениями.
		"""

		# последние цены + prev_price
		price_subq = (
			select(
				MarketData.ticker_id,
				MarketData.close.label("last_price"),
				MarketData.volume.label("last_volume"),
				MarketData.timestamp,
				func.lag(MarketData.close)
				.over(
					partition_by=MarketData.ticker_id,
					order_by=MarketData.timestamp,
				)
				.label("prev_price"),
			)
		).subquery()

		last_prices = (
			select(price_subq)
			.distinct(price_subq.c.ticker_id)
			.order_by(
				price_subq.c.ticker_id,
				price_subq.c.timestamp.desc(),
			)
		).subquery()

		# trend (последние цены)
		trend_subq = (
			select(
				MarketData.ticker_id,
				func.array_agg(MarketData.close).label("trend"),
			).group_by(MarketData.ticker_id)
		).subquery()

		stmt = (
			select(
				WatchlistItem,
				Ticker.symbol,
				Ticker.asset_type,
				last_prices.c.last_price,
				last_prices.c.last_volume,
				last_prices.c.prev_price,
				trend_subq.c.trend,
			)
			.join(
				Watchlist,
				WatchlistItem.watchlist_id == Watchlist.id,
			)
			.join(
				Ticker,
				WatchlistItem.ticker_id == Ticker.id,
			)
			.join(
				last_prices,
				last_prices.c.ticker_id == Ticker.id,
			)
			.outerjoin(
				trend_subq,
				trend_subq.c.ticker_id == Ticker.id,
			)
			.where(
				Watchlist.owner_id == user_id,
				Watchlist.tenant_id == tenant_id,
			)
		)

		# search
		if search:
			search_term = f"%{search.lower()}%"

			stmt = stmt.where(
				or_(
					func.lower(Ticker.symbol).like(search_term),
				)
			)

		# asset_type
		if asset_type != "all":
			if asset_type in ("russian", "moex"):
				stmt = stmt.where(Ticker.asset_type == "russian")
			else:
				stmt = stmt.where(Ticker.asset_type == asset_type)

		# signal score
		signal_score = case(
			(
				and_(
					WatchlistItem.target_price.is_not(None),
					last_prices.c.last_price <= WatchlistItem.target_price,
				),
				1,
			),
			else_=0,
		)

		sort_field: Any

		# sorting
		if sort_by == "price":
			sort_field = last_prices.c.last_price

		elif sort_by == "change_percent":
			sort_field = (
				last_prices.c.last_price - last_prices.c.prev_price
			) / func.nullif(
				last_prices.c.prev_price,
				0,
			)

		elif sort_by == "symbol":
			sort_field = Ticker.symbol

		elif sort_by == "added_at":
			sort_field = WatchlistItem.created_at

		elif sort_by == "signal":
			sort_field = signal_score

		else:
			sort_field = last_prices.c.last_price

		stmt = (
			stmt.order_by(sort_field.asc())
			if order == "asc"
			else stmt.order_by(sort_field.desc())
		)

		result = await self.session.execute(stmt.limit(limit))
		rows = result.all()

		items = []

		for row in rows:
			(
				wi,
				symbol,
				a_type,
				lp,
				lv,
				pp,
				trend,
			) = row

			change_abs = float(lp - pp) if lp and pp else 0.0

			change_pct = float((lp - pp) / pp * 100) if lp and pp and pp != 0 else 0.0

			signals = self.check_signal(
				wi,
				float(lp) if lp else 0,
			)

			trend_data = []

			if include_trend and trend:
				trend_data = [float(x) for x in trend[:7] if x is not None]

			ai_insight = None

			if include_ai:
				ai_insight = AIInsight(
					summary=(
						"Momentum positive" if change_pct > 0 else "Weak momentum"
					),
					confidence=0.78,
				)

			items.append(
				WatchlistDataItem(
					item_id=wi.id,
					ticker_id=wi.ticker_id,
					symbol=symbol,
					asset_type=a_type,
					last_price=float(lp) if lp else None,
					change_percent=change_pct,
					change_abs=change_abs,
					volume=float(lv) if lv else None,
					added_at=wi.created_at,
					notes=wi.notes,
					reason=wi.reason,
					target_price=wi.target_price,
					stop_loss=wi.stop_loss,
					signals=signals,
					ai_insight=ai_insight,
					trend=trend_data,
				)
			)

		return items

	async def get_watchlist_stats(
		self,
		tenant_id: UUID,
		user_id: UUID,
	) -> WatchlistStats:
		items = await self.get_watchlist_with_prices(
			tenant_id=tenant_id,
			user_id=user_id,
			limit=200,
			include_ai=True,
		)

		if not items:
			return WatchlistStats()

		gainers = 0
		losers = 0
		neutral = 0

		strong_buy_count = 0
		buy_count = 0
		sell_count = 0
		strong_sell_count = 0

		total_change = 0.0

		top_gainer = None
		top_loser = None

		best_change = float("-inf")
		worst_change = float("inf")

		for item in items:
			change = item.change_percent or 0.0
			total_change += change

			# movement
			if change > 0:
				gainers += 1
			elif change < 0:
				losers += 1
			else:
				neutral += 1

			# top movers
			if change > best_change:
				best_change = change
				top_gainer = item.symbol

			if change < worst_change:
				worst_change = change
				top_loser = item.symbol

			# signals
			match item.signal:
				case "STRONG_BUY":
					strong_buy_count += 1
				case "BUY":
					buy_count += 1
				case "SELL":
					sell_count += 1
				case "STRONG_SELL":
					strong_sell_count += 1

		return WatchlistStats(
			total_assets=len(items),
			gainers=gainers,
			losers=losers,
			neutral=neutral,
			strong_buy_count=strong_buy_count,
			buy_count=buy_count,
			sell_count=sell_count,
			strong_sell_count=strong_sell_count,
			avg_change_percent=round(
				total_change / len(items),
				2,
			),
			top_gainer=top_gainer,
			top_loser=top_loser,
		)
