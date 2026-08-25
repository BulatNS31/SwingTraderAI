from datetime import datetime, timezone
from typing import Any, Dict, List
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.repositories.ticker_repository import TickerRepository
from swingtraderai.db.models.market import MarketData, Ticker
from swingtraderai.schemas.ticker import OHLCVDataOut, TickerCreate


class TickerService:
	"""Сервис для управления тикерами"""

	def __init__(self, session: AsyncSession):
		self.session = session
		self.repo = TickerRepository(session)

	async def create(self, ticker_in: TickerCreate) -> Ticker:
		existing = await self.repo.get_by_symbol(ticker_in.symbol)
		if existing:
			raise HTTPException(
				status_code=400, detail="Ticker with this symbol already exists"
			)

		ticker = await self.repo.create(ticker_in.model_dump())
		return ticker

	async def get_all(self, skip: int = 0, limit: int = 100) -> List[Ticker]:
		return await self.repo.get_all(skip, limit)

	async def get_by_id(self, ticker_id: UUID) -> Ticker:
		ticker = await self.repo.get_by_id(ticker_id)
		if not ticker:
			raise HTTPException(status_code=404, detail="Ticker not found")
		return ticker

	async def get_or_create(
		self, symbol: str, exchange_id: UUID | None = None, name: str | None = None
	) -> Ticker:
		"""Получает тикер из БД или создает его, если он отсутствует."""
		symbol = symbol.upper().strip()

		# 1. Сначала пытаемся найти существующий тикер через репозиторий
		ticker = await self.repo.get_by_symbol(symbol)
		if ticker:
			return ticker

		# 2. Если тикер не найден, подготавливаем схему для создания
		ticker_data = TickerCreate(
			symbol=symbol,
			asset_type="stock",
			exchange_id=exchange_id,
			is_active=False,
		)

		# 3. Безопасное создание с обработкой состояния гонки (Race Condition)
		try:
			# Создаем точку сохранения (savepoint), чтобы откат не ломал всю транзакцию
			async with self.session.begin_nested():
				ticker = await self.repo.create(ticker_data.model_dump())
				return ticker
		except Exception:
			# Если запись создалась параллельным потоком, извлекаем её
			ticker = await self.repo.get_by_symbol(symbol)
			if ticker:
				return ticker
			raise

	async def search(self, q: str, limit: int = 20) -> List[Ticker]:
		if len(q) < 1:
			raise HTTPException(status_code=400, detail="Search query too short")
		return await self.repo.search(q, limit)

	async def bulk_create(self, tickers_in: List[TickerCreate]) -> List[Ticker]:
		if len(tickers_in) > 500:
			raise HTTPException(status_code=400, detail="Too many tickers (max 500)")
		return await self.repo.bulk_create_or_update(
			[t.model_dump() for t in tickers_in]
		)

	async def get_active_by_exchange(
		self,
		exchange_id: UUID,
	) -> List[Ticker]:
		"""
		Возвращает только активные тикеры выбранной биржи.
		Используется для MarketSyncService.
		"""

		return await self.repo.get_active_by_exchange(exchange_id)

	async def get_historical_data(
		self,
		ticker_id: UUID,
		timeframe: str = "1d",
		limit: int = 500,
		start_date: datetime | None = None,
		end_date: datetime | None = None,
	) -> List[OHLCVDataOut]:
		"""Получение исторических OHLCV данных"""

		# Проверяем существование тикера
		ticker = await self.repo.get_by_id(ticker_id)
		if not ticker:
			raise HTTPException(status_code=404, detail="Ticker not found")

		stmt = (
			select(MarketData)
			.where(MarketData.ticker_id == ticker_id)
			.where(MarketData.timeframe == timeframe)
			.order_by(MarketData.timestamp.desc())
			.limit(limit)
		)

		if start_date:
			stmt = stmt.where(MarketData.timestamp >= start_date)
		if end_date:
			stmt = stmt.where(MarketData.timestamp <= end_date)

		result = await self.session.execute(stmt)
		data = result.scalars().all()

		return [OHLCVDataOut.model_validate(d) for d in data]

	async def get_technical_indicators(
		self,
		ticker_id: UUID,
		period: str = "1h",
		indicators: str = "",
	) -> Dict[str, Any]:
		"""Получение технических индикаторов"""
		ticker = await self.repo.get_by_id(ticker_id)
		if not ticker:
			raise HTTPException(status_code=404, detail="Ticker not found")

		# Получаем данные для расчёта
		stmt = (
			select(MarketData)
			.where(MarketData.ticker_id == ticker_id)
			.where(MarketData.timeframe == period)
			.order_by(MarketData.timestamp.desc())
			.limit(200)
		)

		result = await self.session.execute(stmt)
		data = result.scalars().all()

		if not data:
			raise HTTPException(
				status_code=404, detail="No market data found for indicators"
			)

		# Сортируем по времени
		data = sorted(data, key=lambda x: x.timestamp or datetime.min)
		prices = [d.close for d in data if d.close is not None]

		indicators_list = [
			i.strip().lower() for i in indicators.split(",") if i.strip()
		]

		result_indicators: Dict[str, Any] = {}

		for ind in indicators_list:
			# Здесь будет вызов ваших функций расчёта индикаторов
			if ind == "rsi":
				# result_indicators["rsi"] = calculate_rsi(prices)
				pass
			elif ind == "macd":
				# macd, signal, hist = calculate_macd(prices)
				# result_indicators["macd"] = {"macd": macd, ...}
				pass
			elif ind.startswith("sma"):
				# period_num = int(ind[3:]) if ind[3:].isdigit() else 20
				# result_indicators[ind] = calculate_sma(prices, period_num)
				pass

		return {
			"ticker_id": str(ticker_id),
			"period": period,
			"indicators": result_indicators,
			"data_points": len(prices),
			"timestamp": datetime.now(timezone.utc),
		}

	async def get_trading_signals(
		self,
		ticker_id: UUID,
		period: str = "1h",
	) -> Dict[str, Any]:
		"""Получение торговых сигналов от ML модели"""
		ticker = await self.repo.get_by_id(ticker_id)
		if not ticker:
			raise HTTPException(status_code=404, detail="Ticker not found")

		# Получаем последние данные
		stmt = (
			select(MarketData)
			.where(MarketData.ticker_id == ticker_id)
			.where(MarketData.timeframe == period)
			.order_by(MarketData.timestamp.desc())
			.limit(100)
		)

		result = await self.session.execute(stmt)
		data = result.scalars().all()

		if not data:
			raise HTTPException(
				status_code=404, detail="No data found for signal generation"
			)

		# Здесь будет вызов ML модели
		# signal_result = predict_signal(ticker.symbol, data)

		# Заглушка
		return {
			"ticker_id": str(ticker_id),
			"period": period,
			"signal": "buy",  # buy / sell / hold
			"confidence": 0.78,
			"reason": "Bullish pattern detected by AI model",
			"timestamp": datetime.now(timezone.utc),
		}
