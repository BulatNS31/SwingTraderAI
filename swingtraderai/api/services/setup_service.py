from __future__ import annotations

from typing import Any, Optional
from uuid import UUID

import pandas as pd

from swingtraderai.ml.setups.scanner import SetupScanner
from swingtraderai.schemas.trade_setup import TradeSetup, TradeSetupList


class SetupService:
	"""
	Сервис торговых сценариев.

	Детерминированный слой: OHLCV → SetupScanner → TradeSetupList.
	ML и AI подключаются позже поверх setup'ов.
	"""

	def __init__(
		self,
		ticker_service: Any,
		*,
		scanner: Optional[SetupScanner] = None,
	) -> None:
		self.ticker_service = ticker_service
		self.scanner = scanner or SetupScanner(
			use_divergence=True,
			use_false_breakout=True,
			use_bsu_bpu=True,
			require_trend_align=True,
			only_last_bar=True,  # realtime: только последний бар
		)

	async def get_setups(
		self,
		ticker_id: UUID,
		*,
		timeframe: str = "1h",
		limit: int = 300,
		symbol: Optional[str] = None,
		only_actionable: bool = False,
		min_rr: float = 1.5,
		min_strength: int = 5,
		scan_history: bool = False,
	) -> TradeSetupList:
		"""
		scan_history=True → only_last_bar=False (для бэктеста / отладки).
		"""
		data = await self.ticker_service.get_historical_data(
			ticker_id=ticker_id,
			timeframe=timeframe,
			limit=limit,
		)

		resolved_symbol = symbol or await self._resolve_symbol(ticker_id)

		if not data:
			return TradeSetupList(
				symbol=resolved_symbol,
				timeframe=timeframe,
				as_of=pd.Timestamp.utcnow().to_pydatetime(),
				setups=[],
			)

		df = pd.DataFrame([d.model_dump() for d in data])
		df.columns = [str(c).lower() for c in df.columns]

		scanner = self.scanner
		if scan_history and scanner.only_last_bar:
			scanner = SetupScanner(
				use_divergence=self.scanner.use_divergence,
				use_false_breakout=self.scanner.use_false_breakout,
				use_bsu_bpu=self.scanner.use_bsu_bpu,
				require_trend_align=self.scanner.require_trend_align,
				only_last_bar=False,
			)

		result = scanner.scan(
			df,
			symbol=resolved_symbol,
			timeframe=timeframe,
			ticker_id=ticker_id,
			prepare=True,
		)

		if only_actionable:
			result = TradeSetupList(
				symbol=result.symbol,
				timeframe=result.timeframe,
				as_of=result.as_of,
				setups=[
					s
					for s in result.setups
					if s.is_actionable(min_rr=min_rr, min_strength=min_strength)
				],
			)

		return result

	async def get_latest_setup(
		self,
		ticker_id: UUID,
		*,
		timeframe: str = "1h",
		limit: int = 300,
		symbol: Optional[str] = None,
	) -> Optional[TradeSetup]:
		"""Один «лучший» setup с последнего бара (по strength, затем R:R)."""
		result = await self.get_setups(
			ticker_id,
			timeframe=timeframe,
			limit=limit,
			symbol=symbol,
			only_actionable=False,
			scan_history=False,
		)
		if not result.setups:
			return None

		return max(
			result.setups,
			key=lambda s: (
				s.signal_strength,
				s.risk.reward_risk or 0.0,
				1 if s.volume.confirmed else 0,
			),
		)

	async def _resolve_symbol(self, ticker_id: UUID) -> str:
		try:
			ticker = await self.ticker_service.get_ticker(ticker_id)
			if ticker is None:
				return str(ticker_id)
			for attr in ("symbol", "ticker", "code", "name"):
				val = getattr(ticker, attr, None)
				if val:
					return str(val)
			if isinstance(ticker, dict):
				return str(ticker.get("symbol") or ticker.get("ticker") or ticker_id)
		except Exception:
			pass
		return str(ticker_id)
