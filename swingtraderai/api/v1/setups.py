from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from swingtraderai.api.deps import get_setup_service
from swingtraderai.api.services.setup_service import SetupService
from swingtraderai.schemas.trade_setup import TradeSetup, TradeSetupList

router = APIRouter(prefix="/setups", tags=["setups"])


@router.get("/{ticker_id}", response_model=TradeSetupList)
async def list_setups(
	ticker_id: UUID,
	timeframe: str = Query("1h"),
	limit: int = Query(300, ge=50, le=2000),
	only_actionable: bool = Query(False),
	min_rr: float = Query(1.5, ge=0.5),
	min_strength: int = Query(5, ge=1, le=10),
	scan_history: bool = Query(False),
	setup_service: SetupService = Depends(get_setup_service),
) -> TradeSetupList:
	return await setup_service.get_setups(
		ticker_id,
		timeframe=timeframe,
		limit=limit,
		only_actionable=only_actionable,
		min_rr=min_rr,
		min_strength=min_strength,
		scan_history=scan_history,
	)


@router.get("/{ticker_id}/latest", response_model=Optional[TradeSetup])
async def latest_setup(
	ticker_id: UUID,
	timeframe: str = Query("1h"),
	limit: int = Query(300, ge=50, le=2000),
	setup_service: SetupService = Depends(get_setup_service),
) -> Optional[TradeSetup]:
	return await setup_service.get_latest_setup(
		ticker_id,
		timeframe=timeframe,
		limit=limit,
	)
