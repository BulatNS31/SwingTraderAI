from __future__ import annotations

from typing import Dict
from uuid import UUID

from swingtraderai.api.services.indicator_service import IndicatorService
from swingtraderai.api.services.setup_service import SetupService


class AnalysisService:
	def __init__(
		self,
		indicator_service: IndicatorService,
		setup_service: SetupService,
	) -> None:
		self.indicator_service = indicator_service
		self.setup_service = setup_service

	async def get_analysis(
		self, ticker_id: UUID, timeframe: str = "1h"
	) -> Dict[str, object]:
		signals = await self.indicator_service.get_signals(ticker_id, period=timeframe)

		setup_service = getattr(self, "setup_service", None)
		if setup_service is None:
			return {
				"signals": signals,
				"setups": None,
				"actionable": [],
			}

		setups = await setup_service.get_setups(ticker_id, timeframe=timeframe)
		return {
			"signals": signals,
			"setups": setups,
			"actionable": setups.actionable,
		}
