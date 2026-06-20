from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.services.market_service import MarketService
from swingtraderai.db.session import get_db
from swingtraderai.schemas.market import MarketsSnapshot

router = APIRouter()


def get_market_service(db: AsyncSession = Depends(get_db)) -> MarketService:
	return MarketService(db)


@router.get("/markets/snapshot", response_model=MarketsSnapshot)
async def get_markets_snapshot(
	page: int = Query(1, ge=1),
	per_page: int = Query(100, ge=1, le=1000),
	timeframe: Optional[str] = Query(None),
	tenant_id: Optional[UUID] = Query(None),
	service: MarketService = Depends(get_market_service),
) -> Any:
	"""Return a markets snapshot grouped by category with heatmap and pulse."""
	snapshot = await service.get_snapshot(
		tenant_id=tenant_id, page=page, per_page=per_page, timeframe=timeframe
	)
	return snapshot
