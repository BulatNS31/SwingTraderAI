from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.repositories.portfolio_repository import PortfolioRepository
from swingtraderai.api.repositories.portfolio_transaction_repository import (
	PortfolioTransactionRepository,
)
from swingtraderai.api.repositories.position_repository import PositionRepository
from swingtraderai.db.models.market import Ticker
from swingtraderai.db.models.portfolio import Portfolio, PortfolioTransaction
from swingtraderai.db.models.user import Position
from swingtraderai.schemas.portfolio import (
	PortfolioCreate,
	PortfolioUpdate,
)
from swingtraderai.schemas.portfolio_transaction import (
	PortfolioTransactionCreate,
)


class PortfolioService:
	def __init__(self, session: AsyncSession):
		self.session = session
		self.repo = PortfolioRepository(session)
		self.tx_repo = PortfolioTransactionRepository(session)
		self.position_repo = PositionRepository(session)

	async def create_portfolio(
		self, tenant_id: UUID, user_id: UUID, portfolio_in: PortfolioCreate
	) -> Portfolio:
		return await self.repo.create_for_user(
			tenant_id, user_id, portfolio_in.model_dump()
		)

	async def get_portfolio(self, tenant_id: UUID, portfolio_id: UUID) -> Portfolio:
		portfolio = await self.repo.get_by_id(tenant_id, portfolio_id)
		if not portfolio:
			raise HTTPException(status_code=404, detail="Portfolio not found")
		return portfolio

	async def list_portfolios(
		self, tenant_id: UUID, user_id: UUID, skip: int = 0, limit: int = 100
	) -> Sequence[Portfolio]:
		return await self.repo.get_by_user(tenant_id, user_id, skip=skip, limit=limit)

	async def update_portfolio(
		self,
		tenant_id: UUID,
		user_id: UUID,
		portfolio_id: UUID,
		portfolio_update: PortfolioUpdate,
	) -> Portfolio:
		portfolio = await self.repo.get_by_id(tenant_id, portfolio_id)
		if not portfolio:
			raise HTTPException(status_code=404, detail="Portfolio not found")
		if portfolio.user_id != user_id:
			raise HTTPException(status_code=403, detail="Forbidden")

		update_data = portfolio_update.model_dump(exclude_unset=True)
		for key, value in update_data.items():
			setattr(portfolio, key, value)

		await self.session.commit()
		await self.session.refresh(portfolio)
		return portfolio

	async def delete_portfolio(
		self, tenant_id: UUID, user_id: UUID, portfolio_id: UUID
	) -> bool:
		portfolio = await self.repo.get_by_id(tenant_id, portfolio_id)
		if not portfolio:
			raise HTTPException(status_code=404, detail="Portfolio not found")
		if portfolio.user_id != user_id:
			raise HTTPException(status_code=403, detail="Forbidden")
		await self.session.delete(portfolio)
		await self.session.commit()
		return True

	async def add_transaction(
		self,
		tenant_id: UUID,
		user_id: UUID,
		portfolio_id: UUID,
		transaction_in: PortfolioTransactionCreate,
	) -> PortfolioTransaction:
		portfolio = await self.repo.get_by_id(tenant_id, portfolio_id)
		if not portfolio:
			raise HTTPException(status_code=404, detail="Portfolio not found")
		if portfolio.user_id != user_id:
			raise HTTPException(status_code=403, detail="Forbidden")

		ticker = await self.session.get(Ticker, transaction_in.ticker_id)
		if not ticker:
			raise HTTPException(status_code=404, detail="Ticker not found")

		transaction_data = transaction_in.model_dump()
		transaction_data["user_id"] = user_id
		transaction_data["portfolio_id"] = portfolio_id
		transaction_data["tenant_id"] = tenant_id
		transaction_data["executed_at"] = (
			transaction_in.executed_at
			if transaction_in.executed_at
			else datetime.now(timezone.utc)
		)

		transaction = await self.tx_repo.create_for_portfolio(
			tenant_id, transaction_data
		)
		await self.recalculate_position(
			tenant_id=tenant_id,
			user_id=user_id,
			portfolio_id=portfolio_id,
			ticker_id=transaction_in.ticker_id,
			side=transaction_in.side,
			quantity=transaction_in.quantity,
			price=transaction_in.price,
		)
		return transaction

	async def close_position(self, tenant_id: UUID, position_id: UUID) -> bool:
		position = await self.position_repo.get_by_id(tenant_id, position_id)
		if not position:
			raise HTTPException(status_code=404, detail="Position not found")
		if position.closed_at:
			return False

		position.closed_at = datetime.now(timezone.utc)
		await self.session.commit()
		return True

	async def recalculate_position(
		self,
		tenant_id: UUID,
		user_id: UUID,
		portfolio_id: UUID,
		ticker_id: UUID,
		side: str,
		quantity: Decimal,
		price: Decimal,
	) -> Position:
		side = side.upper()
		if side not in {"BUY", "SELL"}:
			raise HTTPException(status_code=400, detail="Invalid transaction side")

		position = await self.position_repo.get_active_by_ticker(
			tenant_id=tenant_id,
			user_id=user_id,
			ticker_id=ticker_id,
			position_type="long",
		)

		if side == "BUY":
			if position is None:
				position_data = {
					"user_id": user_id,
					"ticker_id": ticker_id,
					"portfolio_id": portfolio_id,
					"position_type": "long",
					"quantity": quantity,
					"average_buy_price": price,
					"total_cost": quantity * price,
				}
				position = await self.position_repo.create(tenant_id, position_data)
			else:
				current_qty = Decimal(position.quantity)
				current_cost = Decimal(position.total_cost)
				new_qty = current_qty + quantity
				new_total_cost = current_cost + (quantity * price)
				position.quantity = new_qty
				position.average_buy_price = new_total_cost / new_qty
				position.total_cost = new_total_cost
				await self.session.commit()
				await self.session.refresh(position)
		else:
			if position is None:
				raise HTTPException(
					status_code=400,
					detail="No active position to sell",
				)

			new_qty = Decimal(position.quantity) - quantity
			if new_qty < 0:
				raise HTTPException(
					status_code=400,
					detail="Sell quantity exceeds active position",
				)

			if new_qty == 0:
				position.quantity = Decimal("0")
				position.closed_at = datetime.now(timezone.utc)
			else:
				position.quantity = new_qty
				position.total_cost = position.average_buy_price * new_qty

			await self.session.commit()
			await self.session.refresh(position)

		return position
