from typing import Any, Dict, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.deps import get_current_user
from swingtraderai.api.repositories.exchange_repository import ExchangeRepository
from swingtraderai.api.repositories.market_quote_repository import (
	MarketQuoteRepository,
)
from swingtraderai.api.services.market_data.market_cache_service import (
	MarketCacheService,
)
from swingtraderai.api.services.market_data.market_sync_service import MarketSyncService
from swingtraderai.api.services.market_data.providers.moex_provider import MoexProvider
from swingtraderai.api.services.ticker_service import TickerService
from swingtraderai.core.tenant import get_current_tenant_id
from swingtraderai.db.models.user import User
from swingtraderai.db.session import get_db
from swingtraderai.schemas.market import MarketQuoteResponse

router = APIRouter(
	prefix="/markets",
	tags=["markets"],
)


def get_market_cache_service(
	db: AsyncSession = Depends(get_db),
) -> MarketCacheService:
	return MarketCacheService(db)


def get_market_quote_repo(
	db: AsyncSession = Depends(get_db),
) -> MarketQuoteRepository:
	return MarketQuoteRepository(db)


def get_ticker_service(
	db: AsyncSession = Depends(get_db),
) -> TickerService:
	return TickerService(db)


def get_market_sync_service(
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
	ticker_service: TickerService = Depends(get_ticker_service),
) -> MarketSyncService:
	return MarketSyncService(repository=repo, ticker_service=ticker_service)


def get_exchange_repository(
	db: AsyncSession = Depends(get_db),
) -> ExchangeRepository:
	return ExchangeRepository(db)


@router.get(
	"/snapshot",
	response_model=Dict[str, Any],
)
async def snapshot(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	cache: MarketCacheService = Depends(get_market_cache_service),
) -> Dict[str, Any]:
	return await cache.get_snapshot(tenant_id)


@router.get(
	"/crypto",
	response_model=List[MarketQuoteResponse],
)
async def crypto(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> List[MarketQuoteResponse]:
	items = await repo.get_by_market_type(
		tenant_id,
		"crypto",
	)

	return [MarketQuoteResponse.model_validate(item) for item in items]


@router.get(
	"/moex",
	response_model=List[MarketQuoteResponse],
)
async def moex(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> List[MarketQuoteResponse]:
	items = await repo.get_by_market_type(
		tenant_id,
		"moex",
	)

	return [MarketQuoteResponse.model_validate(item) for item in items]


@router.get(
	"/us",
	response_model=List[MarketQuoteResponse],
)
async def us(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> List[MarketQuoteResponse]:
	items = await repo.get_by_market_type(
		tenant_id,
		"us",
	)

	return [MarketQuoteResponse.model_validate(item) for item in items]


@router.post("/sync/moex")
async def sync_moex(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	sync_service: MarketSyncService = Depends(get_market_sync_service),
	exchange_repo: ExchangeRepository = Depends(get_exchange_repository),
) -> Dict[str, int]:
	# Получаем биржу MOEX
	exchange = await exchange_repo.get_by_code("MOEX")

	if not exchange:
		raise HTTPException(
			status_code=404, detail="Exchange MOEX not found in database"
		)

	items = await sync_service.sync(
		tenant_id=tenant_id,
		provider=MoexProvider(),
		exchange_id=exchange.id,
	)

	return {"updated": len(items)}


@router.get(
	"/heatmap",
	response_model=List[Dict[str, Any]],
)
async def heatmap(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> List[Dict[str, Any]]:
	items = await repo.list_recent(
		tenant_id,
		limit=200,
	)

	return [
		{
			"symbol": (item.ticker.symbol if item.ticker else None),
			"change_percent": float(item.change_percent or 0),
			"regime": ("Bullish" if (item.change_percent or 0) > 0 else "Bearish"),
		}
		for item in items
	]


@router.get(
	"/quote/{symbol}",
	response_model=MarketQuoteResponse,
)
async def quote(
	symbol: str,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	cache: MarketCacheService = Depends(get_market_cache_service),
) -> MarketQuoteResponse:
	q = await cache.get_quote(
		tenant_id,
		symbol,
	)

	if not q:
		raise HTTPException(
			status_code=404,
			detail="Quote not found",
		)

	return MarketQuoteResponse.model_validate(q)
