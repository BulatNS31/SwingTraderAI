from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.deps import get_current_user
from swingtraderai.api.services.portfolio.portfolio_service import PortfolioService
from swingtraderai.core.tenant import get_current_tenant_id
from swingtraderai.db.models.user import User
from swingtraderai.db.session import get_db
from swingtraderai.schemas.portfolio import (
	PortfolioCreate,
	PortfolioOut,
	PortfolioUpdate,
)
from swingtraderai.schemas.portfolio_transaction import (
	PortfolioTransactionCreate,
	PortfolioTransactionOut,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


def get_portfolio_service(db: AsyncSession = Depends(get_db)) -> PortfolioService:
	return PortfolioService(db)


@router.get("/", response_model=list[PortfolioOut])
async def list_portfolios(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> list[PortfolioOut]:
	portfolios = await portfolio_service.list_portfolios(
		tenant_id=tenant_id, user_id=current_user.id
	)
	return [PortfolioOut.model_validate(p) for p in portfolios]


@router.get("/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio(
	portfolio_id: UUID,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioOut:
	portfolio = await portfolio_service.get_portfolio(tenant_id, portfolio_id)
	if portfolio.user_id != current_user.id:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
	return PortfolioOut.model_validate(portfolio)


@router.post("/", response_model=PortfolioOut, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
	portfolio_in: PortfolioCreate,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioOut:
	portfolio = await portfolio_service.create_portfolio(
		tenant_id=tenant_id,
		user_id=current_user.id,
		portfolio_in=portfolio_in,
	)
	return PortfolioOut.model_validate(portfolio)


@router.patch("/{portfolio_id}", response_model=PortfolioOut)
async def update_portfolio(
	portfolio_id: UUID,
	portfolio_update: PortfolioUpdate,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioOut:
	portfolio = await portfolio_service.update_portfolio(
		tenant_id=tenant_id,
		user_id=current_user.id,
		portfolio_id=portfolio_id,
		portfolio_update=portfolio_update,
	)
	return PortfolioOut.model_validate(portfolio)


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
	portfolio_id: UUID,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> None:
	await portfolio_service.delete_portfolio(
		tenant_id=tenant_id,
		user_id=current_user.id,
		portfolio_id=portfolio_id,
	)


@router.get(
	"/{portfolio_id}/transactions", response_model=list[PortfolioTransactionOut]
)
async def list_portfolio_transactions(
	portfolio_id: UUID,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> list[PortfolioTransactionOut]:
	portfolio = await portfolio_service.get_portfolio(tenant_id, portfolio_id)
	if portfolio.user_id != current_user.id:
		raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

	transactions = await portfolio_service.tx_repo.get_by_portfolio(
		tenant_id=tenant_id, portfolio_id=portfolio_id
	)
	return [PortfolioTransactionOut.model_validate(tx) for tx in transactions]


@router.post(
	"/{portfolio_id}/transactions",
	response_model=PortfolioTransactionOut,
	status_code=status.HTTP_201_CREATED,
)
async def add_portfolio_transaction(
	portfolio_id: UUID,
	transaction_in: PortfolioTransactionCreate,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	portfolio_service: PortfolioService = Depends(get_portfolio_service),
) -> PortfolioTransactionOut:
	transaction = await portfolio_service.add_transaction(
		tenant_id=tenant_id,
		user_id=current_user.id,
		portfolio_id=portfolio_id,
		transaction_in=transaction_in,
	)
	return PortfolioTransactionOut.model_validate(transaction)
