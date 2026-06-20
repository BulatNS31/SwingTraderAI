from typing import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.api.repositories.base import TenantAwareRepository
from swingtraderai.db.models.portfolio import PortfolioTransaction


class PortfolioTransactionRepository(TenantAwareRepository[PortfolioTransaction]):
	"""Репозиторий для истории транзакций портфеля."""

	def __init__(self, session: AsyncSession):
		super().__init__(session, PortfolioTransaction)

	async def get_by_portfolio(
		self, tenant_id: UUID, portfolio_id: UUID
	) -> Sequence[PortfolioTransaction]:
		query = (
			self._get_tenant_query(tenant_id)
			.where(PortfolioTransaction.portfolio_id == portfolio_id)
			.order_by(PortfolioTransaction.executed_at.desc())
			.options(joinedload(PortfolioTransaction.ticker))
		)
		result = await self.session.execute(query)
		return result.scalars().all()

	async def create_for_portfolio(
		self, tenant_id: UUID, obj_in: dict[str, object]
	) -> PortfolioTransaction:
		obj_in["tenant_id"] = tenant_id
		transaction = PortfolioTransaction(**obj_in)
		self.session.add(transaction)
		await self.session.commit()
		await self.session.refresh(transaction)
		return transaction
