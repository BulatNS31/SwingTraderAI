from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Tuple
from uuid import UUID

import pandas as pd

from swingtraderai.indicators.registry import registry
from swingtraderai.schemas.indicators import (
	IndicatorValue,
	SignalOut,
	TechnicalIndicatorsOut,
)


class IndicatorService:
	def __init__(self, ticker_service: Any) -> None:
		self.ticker_service = ticker_service

	async def get_indicators(
		self,
		ticker_id: UUID,
		indicators: List[str],
		timeframe: str = "1h",
		limit: int = 500,
	) -> TechnicalIndicatorsOut:
		data = await self.ticker_service.get_historical_data(
			ticker_id=ticker_id, timeframe=timeframe, limit=limit
		)

		df = pd.DataFrame([d.model_dump() for d in data])

		result = {}
		for ind_name in indicators:
			indicator = registry.get(ind_name)
			if indicator:
				ind_result = indicator.calculate(df)
				if hasattr(ind_result, "model_dump"):
					result[ind_name] = IndicatorValue(**ind_result.model_dump())
				elif isinstance(ind_result, dict):
					result[ind_name] = IndicatorValue(**ind_result)
				else:
					result[ind_name] = IndicatorValue(value=None)

		timestamp: datetime
		current_price: float

		if not df.empty:
			last_time = df.iloc[-1].time
			if isinstance(last_time, datetime):
				timestamp = last_time
			else:
				timestamp = pd.to_datetime(last_time).to_pydatetime()

			last_close = df.iloc[-1].close
			if isinstance(last_close, (int, float)):
				current_price = float(last_close)
			else:
				current_price = 0.0
		else:
			timestamp = datetime.now(timezone.utc)
			current_price = 0.0

		symbol = "..."

		return TechnicalIndicatorsOut(
			ticker_id=ticker_id,
			symbol=symbol,
			timeframe=timeframe,
			timestamp=timestamp,
			current_price=current_price,
			indicators=result,
		)

	async def get_signals(
		self,
		ticker_id: UUID,
		period: str = "1h",
	) -> List[SignalOut]:
		data = await self.ticker_service.get_historical_data(
			ticker_id=ticker_id, timeframe=period, limit=100
		)

		if not data:
			return [
				SignalOut(
					type="NEUTRAL",
					strength=1,
					message="Недостаточно данных для анализа",
					indicators_used=[],
				)
			]

		df = pd.DataFrame([d.model_dump() for d in data])
		indicator_results: Dict[str, Any] = {}

		for ind_name, indicator in registry._indicators.items():
			try:
				result = indicator.calculate(df)
				indicator_results[ind_name] = result
			except Exception:
				continue

		signal_type, strength, message = self._calculate_composite_signal(
			indicator_results
		)

		return [
			SignalOut(
				type=signal_type,
				strength=strength,
				message=message,
				indicators_used=list(indicator_results.keys()),
			)
		]

	def _calculate_composite_signal(
		self, indicator_results: Dict[str, Any]
	) -> Tuple[
		Literal["STRONG_BUY", "BUY", "NEUTRAL", "SELL", "STRONG_SELL"], int, str
	]:
		"""Возвращает строго типизированный сигнал"""
		if not indicator_results:
			return "NEUTRAL", 1, "Нет данных от индикаторов"

		buy_score = 0.0
		sell_score = 0.0
		details = []

		for ind_name, result in indicator_results.items():
			value = self._extract_signal_value(result)

			if value > 0:
				buy_score += value
				details.append(f"{ind_name}: BUY ({value:.2f})")
			elif value < 0:
				sell_score += abs(value)
				details.append(f"{ind_name}: SELL ({abs(value):.2f})")
			else:
				details.append(f"{ind_name}: NEUTRAL")

		total = buy_score + sell_score
		if total == 0:
			return "NEUTRAL", 1, "Сигналы отсутствуют"

		if buy_score > sell_score:
			strength = int(min(10, 1 + (buy_score / total) * 9))
			if strength >= 8:
				return (
					"STRONG_BUY",
					strength,
					f"Сильный бычий сигнал (сила: {strength}/10)",
				)
			else:
				return "BUY", strength, f"Бычий сигнал (сила: {strength}/10)"
		elif sell_score > buy_score:
			strength = int(min(10, 1 + (sell_score / total) * 9))
			if strength >= 8:
				return (
					"STRONG_SELL",
					strength,
					f"Сильный медвежий сигнал (сила: {strength}/10)",
				)
			else:
				return "SELL", strength, f"Медвежий сигнал (сила: {strength}/10)"
		else:
			return "NEUTRAL", 5, "Рынок в нейтральном состоянии"

	def _extract_signal_value(self, result: Any) -> float:
		"""Извлечение сигнального значения"""
		if hasattr(result, "signal_value"):
			return float(result.signal_value)
		if hasattr(result, "signal"):
			signal_map = {
				"STRONG_BUY": 2.0,
				"BUY": 1.0,
				"NEUTRAL": 0.0,
				"SELL": -1.0,
				"STRONG_SELL": -2.0,
				"bullish": 1.0,
				"bearish": -1.0,
			}
			return signal_map.get(result.signal, 0.0)
		if isinstance(result, dict):
			if "signal_value" in result:
				return float(result["signal_value"])
			if "signal" in result:
				signal_map = {
					"STRONG_BUY": 2.0,
					"BUY": 1.0,
					"NEUTRAL": 0.0,
					"SELL": -1.0,
					"STRONG_SELL": -2.0,
					"bullish": 1.0,
					"bearish": -1.0,
				}
				return signal_map.get(result["signal"], 0.0)
		if isinstance(result, (int, float)):
			return float(result)

		return 0.0
