from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.deps import get_current_user
from swingtraderai.api.repositories.market_quote_repository import MarketQuoteRepository
from swingtraderai.api.services.market_data.market_cache_service import (
	MarketCacheService,
)
from swingtraderai.core.tenant import get_current_tenant_id
from swingtraderai.db.models.user import User
from swingtraderai.db.session import get_db
from swingtraderai.schemas.market import MarketQuoteResponse

router = APIRouter(prefix="/markets", tags=["markets"])


def get_market_cache_service(db: AsyncSession = Depends(get_db)) -> MarketCacheService:
	return MarketCacheService(db)


def get_market_quote_repo(db: AsyncSession = Depends(get_db)) -> MarketQuoteRepository:
	return MarketQuoteRepository(db)


@router.get("/snapshot")
async def snapshot(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	cache: MarketCacheService = Depends(get_market_cache_service),
) -> Dict[str, Any]:
	data = await cache.get_snapshot(tenant_id)
	return data


@router.get("/crypto")
async def crypto(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> Sequence[Any]:
	items = await repo.get_by_market_type(tenant_id, "crypto")
	return items


@router.get("/moex")
async def moex(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> Sequence[Any]:
	items = await repo.get_by_market_type(tenant_id, "moex")
	return items


@router.get("/us")
async def us(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> Sequence[Any]:
	items = await repo.get_by_market_type(tenant_id, "us")
	return items


@router.get("/heatmap")
async def heatmap(
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	repo: MarketQuoteRepository = Depends(get_market_quote_repo),
) -> List[Dict[str, Any]]:
	items = await repo.list_recent(tenant_id, limit=200)
	heat = [
		{
			"symbol": i.ticker.symbol if i.ticker else None,
			"change_percent": float(i.change_percent),
			"regime": ("Bullish" if i.change_percent >= 0 else "Bearish"),
		}
		for i in items
	]
	return heat


@router.get("/quote/{symbol}")
async def quote(
	symbol: str,
	current_user: User = Depends(get_current_user),
	tenant_id: UUID = Depends(get_current_tenant_id),
	cache: MarketCacheService = Depends(get_market_cache_service),
) -> Optional[MarketQuoteResponse]:
	q = await cache.get_quote(tenant_id, symbol)
	if not q:
		raise HTTPException(status_code=404, detail="Quote not found")
	return MarketQuoteResponse(**q) if isinstance(q, dict) else None
