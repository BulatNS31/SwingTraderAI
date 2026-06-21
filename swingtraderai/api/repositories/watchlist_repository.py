from typing import Any, List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.db.models.system import Watchlist, WatchlistItem

from .base import TenantAwareRepository


class WatchlistRepository(TenantAwareRepository[Watchlist]):
	"""Репозиторий для управления watchlist пользователей."""

	def __init__(self, session: AsyncSession):
		super().__init__(session, Watchlist)

	async def get_by_owner(self, tenant_id: UUID, user_id: UUID) -> Optional[Watchlist]:
		"""Получить watchlist по владельцу и тенанту"""
		query = select(Watchlist).where(
			and_(Watchlist.tenant_id == tenant_id, Watchlist.owner_id == user_id)
		)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_or_create_default(
		self, tenant_id: UUID, user_id: UUID, name: Optional[str] = None
	) -> Watchlist:
		"""Получить или создать дефолтный watchlist для пользователя"""
		watchlist = await self.get_by_owner(tenant_id, user_id)

		if not watchlist:
			watchlist_name = name or f"Default-{user_id.hex[:8]}"
			watchlist = Watchlist(
				tenant_id=tenant_id,
				owner_id=user_id,
				name=watchlist_name,
				is_default=True,
			)
			self.session.add(watchlist)
			await self.session.commit()
			await self.session.refresh(watchlist)

		return watchlist


class WatchlistItemRepository(TenantAwareRepository[WatchlistItem]):
	"""Репозиторий для управления элементами watchlist (WatchlistItem)."""

	def __init__(self, session: AsyncSession):
		super().__init__(session, WatchlistItem)

	async def get_user_watchlist_items(
		self, tenant_id: UUID, user_id: UUID
	) -> List[WatchlistItem]:
		"""Получить все items пользователя с тикерами"""
		query = (
			self._get_tenant_query(tenant_id)
			.join(Watchlist)
			.where(Watchlist.owner_id == user_id)
			.options(joinedload(WatchlistItem.ticker))
			.order_by(WatchlistItem.created_at.desc())
		)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def get_by_ticker(
		self, tenant_id: UUID, user_id: UUID, ticker_id: UUID
	) -> Optional[WatchlistItem]:
		"""Проверка, есть ли тикер уже в watchlist"""
		query = (
			self._get_tenant_query(tenant_id)
			.join(Watchlist)
			.where(
				and_(
					Watchlist.owner_id == user_id,
					WatchlistItem.ticker_id == ticker_id,
				)
			)
		)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_by_watchlist(
		self, tenant_id: UUID, watchlist_id: UUID
	) -> List[WatchlistItem]:
		"""Получить все элементы конкретного watchlist"""
		query = (
			self._get_tenant_query(tenant_id)
			.where(WatchlistItem.watchlist_id == watchlist_id)
			.options(joinedload(WatchlistItem.ticker))
			.order_by(WatchlistItem.created_at.desc())
		)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def create_watchlist_item(
		self, tenant_id: UUID, watchlist_id: UUID, ticker_id: UUID, **kwargs: Any
	) -> WatchlistItem:
		"""Создать новый элемент в watchlist"""
		stmt = select(WatchlistItem).where(
			and_(
				WatchlistItem.watchlist_id == watchlist_id,
				WatchlistItem.ticker_id == ticker_id,
			)
		)
		result = await self.session.execute(stmt)
		existing = result.scalar_one_or_none()

		if existing:
			raise ValueError(f"Ticker {ticker_id} already in watchlist {watchlist_id}")

		item = WatchlistItem(
			tenant_id=tenant_id,
			watchlist_id=watchlist_id,
			ticker_id=ticker_id,
			**kwargs,
		)
		self.session.add(item)
		await self.session.commit()
		await self.session.refresh(item)
		return item

	async def create_watchlist_if_not_exists(
		self, tenant_id: UUID, user_id: UUID, name: str = ""
	) -> Watchlist:
		"""Создать watchlist для пользователя, если его нет"""
		result = await self.session.execute(
			select(Watchlist).where(
				and_(
					Watchlist.tenant_id == tenant_id,
					Watchlist.owner_id == user_id,
				)
			)
		)
		watchlist = result.scalar_one_or_none()

		if not watchlist:
			watchlist = Watchlist(
				tenant_id=tenant_id,
				owner_id=user_id,
				name=name or f"Watchlist-{user_id}",
				is_default=True,
			)
			self.session.add(watchlist)
			await self.session.commit()
			await self.session.refresh(watchlist)

		return watchlist
