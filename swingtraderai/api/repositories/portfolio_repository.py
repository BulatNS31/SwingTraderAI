from typing import Any, Optional, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.api.repositories.base import TenantAwareRepository
from swingtraderai.db.models.portfolio import Portfolio


class PortfolioRepository(TenantAwareRepository[Portfolio]):
	"""Репозиторий для работы с портфелями пользователя."""

	def __init__(self, session: AsyncSession):
		super().__init__(session, Portfolio)

	async def get_by_user(
		self, tenant_id: UUID, user_id: UUID, skip: int = 0, limit: int = 100
	) -> Sequence[Portfolio]:
		query = (
			self._get_tenant_query(tenant_id)
			.where(Portfolio.user_id == user_id)
			.offset(skip)
			.limit(limit)
			.options(
				joinedload(Portfolio.positions), joinedload(Portfolio.transactions)
			)
		)
		result = await self.session.execute(query)
		return result.unique().scalars().all()

	async def get_by_id(
		self, tenant_id: UUID, portfolio_id: UUID
	) -> Optional[Portfolio]:
		query = (
			self._get_tenant_query(tenant_id)
			.where(Portfolio.id == portfolio_id)
			.options(
				joinedload(Portfolio.positions), joinedload(Portfolio.transactions)
			)
		)
		result = await self.session.execute(query)
		return result.unique().scalar_one_or_none()

	async def create_for_user(
		self, tenant_id: UUID, user_id: UUID, obj_in: dict[str, Any]
	) -> Portfolio:
		obj_in["tenant_id"] = tenant_id
		obj_in["user_id"] = user_id
		portfolio = Portfolio(**obj_in)
		self.session.add(portfolio)
		await self.session.commit()
		await self.session.refresh(portfolio)
		return portfolio
