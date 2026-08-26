import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from swingtraderai.db.models.analysis import Analysis, Signal
from swingtraderai.db.models.market import Exchange, Ticker


@pytest.mark.asyncio
async def test_analysis_creation_and_defaults(session: AsyncSession):
	"""Проверка создания Analysis + дефолтные значения + JSONB"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="ETHUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()
	await session.commit()
	await session.refresh(ticker)

	analysis = Analysis(
		ticker_id=ticker.id,
		timeframe="4h",
		model="groq-llama3-70b",
		trend="bullish",
		confidence=Decimal("0.784"),
		summary="Ожидается продолжение роста после пробоя уровня 3800",
		raw_llm_output={
			"prompt_tokens": 1245,
			"completion_tokens": 289,
			"reasoning": "volume + RSI divergence",
		},
		indicators={
			"rsi_14": 68.7,
			"macd": {"value": 42.13, "signal": 31.89, "histogram": 10.24},
			"ema_50": 3742.15,
		},
	)

	session.add(analysis)
	await session.commit()
	await session.refresh(analysis)

	assert isinstance(analysis.id, uuid.UUID)
	assert analysis.ticker_id == ticker.id
	assert analysis.timeframe == "4h"
	assert analysis.trend == "bullish"
	assert analysis.confidence == 0.784
	assert isinstance(analysis.summary, str)
	assert isinstance(analysis.raw_llm_output, dict)
	assert isinstance(analysis.indicators, dict)
	assert analysis.raw_llm_output["prompt_tokens"] == 1245

	assert isinstance(analysis.created_at, datetime)
	assert analysis.created_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_analysis_minimal_creation(session: AsyncSession, ticker: Ticker):
	"""Минимальный анализ — проверка nullable полей"""
	analysis = Analysis(ticker_id=ticker.id)
	session.add(analysis)
	await session.commit()
	await session.refresh(analysis)

	assert analysis.timeframe is None
	assert analysis.model is None
	assert analysis.trend is None
	assert analysis.confidence is None
	assert analysis.summary is None
	assert analysis.raw_llm_output is None
	assert analysis.indicators is None


@pytest.mark.asyncio
async def test_signal_creation_and_numeric_fields(
	session: AsyncSession, ticker: Ticker
):
	"""Создание сигнала + проверка Decimal полей"""
	analysis = Analysis(ticker_id=ticker.id, timeframe="1h", trend="bearish")
	session.add(analysis)
	await session.commit()
	await session.refresh(analysis)

	signal = Signal(
		analysis_id=analysis.id,
		ticker_id=ticker.id,
		signal_type="SHORT",
		strength=Decimal("0.89"),
		entry_price=Decimal("148.75"),
		stop_loss=Decimal("156.40"),
		take_profit=Decimal("132.10"),
		status="pending",
		reason="Пробой вниз + дивергенция на MACD",
	)

	session.add(signal)
	await session.commit()
	await session.refresh(signal)

	assert isinstance(signal.id, uuid.UUID)
	assert signal.analysis_id == analysis.id
	assert signal.ticker_id == ticker.id
	assert signal.signal_type == "SHORT"
	assert signal.strength == 0.89
	assert signal.stop_loss == Decimal("156.40")
	assert signal.take_profit == Decimal("132.10")
	assert signal.status == "pending"

	assert isinstance(signal.created_at, datetime)
	assert signal.created_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_signal_minimal_and_nullables(session: AsyncSession, ticker: Ticker):
	analysis = Analysis(ticker_id=ticker.id)
	session.add(analysis)
	await session.commit()
	await session.refresh(analysis)

	signal = Signal(analysis_id=analysis.id, ticker_id=ticker.id, signal_type="NEUTRAL")

	session.add(signal)
	await session.commit()
	await session.refresh(signal)

	assert signal.strength is None
	assert signal.entry_price is None
	assert signal.stop_loss is None
	assert signal.take_profit is None
	assert signal.reason is None
	assert signal.status is None


@pytest.mark.asyncio
async def test_foreign_key_violation_analysis(session: AsyncSession):
	"""Попытка создать Analysis с несуществующим ticker_id"""
	fake_uuid = uuid.uuid4()

	analysis = Analysis(ticker_id=fake_uuid, timeframe="1d")
	session.add(analysis)

	with pytest.raises(IntegrityError):
		await session.commit()


@pytest.mark.asyncio
async def test_foreign_key_violation_signal(session: AsyncSession, ticker: Ticker):
	"""Попытка создать Signal с несуществующим analysis_id"""
	fake_analysis_id = uuid7()

	signal = Signal(
		analysis_id=fake_analysis_id, ticker_id=ticker.id, signal_type="LONG"
	)
	session.add(signal)

	with pytest.raises(IntegrityError):
		await session.commit()
