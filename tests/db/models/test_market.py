import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from swingtraderai.db.models.market import Exchange, MarketData, Ticker


@pytest.mark.asyncio
async def test_ticker_creation_and_defaults(session: AsyncSession):
	"""Проверка создания Ticker + значения по умолчанию"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="ADAUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()

	await session.refresh(ticker)

	assert isinstance(ticker.id, uuid.UUID)
	assert ticker.symbol == "ADAUSDT"
	assert ticker.asset_type == "CRYPTO"
	assert ticker.exchange_id == binance.id
	assert ticker.base_currency == "BTC"
	assert ticker.quote_currency == "USDT"
	assert ticker.is_active is True

	assert isinstance(ticker.created_at, datetime)
	assert ticker.created_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_ticker_minimal_creation(session: AsyncSession):
	"""Минимальный тикер — проверка обязательных полей и дефолтов"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="ADAUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()
	await session.refresh(ticker)

	assert ticker.base_currency == "BTC"
	assert ticker.quote_currency == "USDT"
	assert ticker.is_active is True
	assert isinstance(ticker.id, uuid.UUID)


@pytest.mark.asyncio
async def test_ticker_symbol_unique_constraint(session: AsyncSession):
	"""Проверка уникальности symbol"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="ADAUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()

	t1 = Ticker(
		symbol="XRPUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	t2 = Ticker(
		symbol="XRPUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)

	session.add(t1)
	await session.commit()

	session.add(t2)
	with pytest.raises(IntegrityError):
		await session.commit()


@pytest.mark.asyncio
async def test_ticker_unique_symbol_per_exchange(session: AsyncSession):
	"""Уникальность symbol + exchange_id (одинаковый symbol на разных биржах — ок)"""
	binance = Exchange(name="Binance", code="BINANCE")
	bybit = Exchange(name="Bybit", code="BYBIT")
	session.add_all([binance, bybit])
	await session.commit()

	t1 = Ticker(
		symbol="BTCUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
	)
	t2 = Ticker(
		symbol="BTCUSDT",
		asset_type="CRYPTO",
		exchange_id=bybit.id,
	)

	session.add_all([t1, t2])
	await session.commit()
	await session.refresh(t1)
	await session.refresh(t2)

	assert t1.symbol == t2.symbol
	assert t1.exchange_id != t2.exchange_id


@pytest.mark.asyncio
async def test_ticker_same_symbol_same_exchange_forbidden(session: AsyncSession):
	"""Одинаковый symbol + одинаковый exchange_id → IntegrityError"""
	exchange = Exchange(name="Binance", code="BINANCE")
	session.add(exchange)
	await session.commit()

	t1 = Ticker(symbol="ETHUSDT", asset_type="CRYPTO", exchange_id=exchange.id)
	t2 = Ticker(symbol="ETHUSDT", asset_type="CRYPTO", exchange_id=exchange.id)

	session.add(t1)
	await session.commit()

	session.add(t2)
	with pytest.raises(IntegrityError):
		await session.commit()


@pytest.mark.asyncio
async def test_market_data_creation_and_relationship(session: AsyncSession):
	"""Создание MarketData + связь с Ticker + проверка Decimal"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="ADAUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()
	await session.refresh(ticker)

	now = datetime.now(timezone.utc)

	md = MarketData(
		ticker_id=ticker.id,
		timeframe="1h",
		timestamp=now,
		open=Decimal("1.2345"),
		high=Decimal("1.2567"),
		low=Decimal("1.2100"),
		close=Decimal("1.2456"),
		volume=Decimal("1234567.89"),
	)

	session.add(md)
	await session.commit()
	await session.refresh(md)

	assert isinstance(md.id, uuid.UUID)
	assert md.ticker_id == ticker.id
	assert md.timeframe == "1h"
	assert md.timestamp == now
	assert md.open == Decimal("1.2345")
	assert md.high == Decimal("1.2567")
	assert md.low == Decimal("1.2100")
	assert md.close == Decimal("1.2456")
	assert md.volume == Decimal("1234567.89")

	assert isinstance(md.created_at, datetime)
	assert md.created_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_market_data_default_timestamp(session: AsyncSession):
	"""Проверка автоматического заполнения timestamp, если не указан"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="ADAUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()
	await session.refresh(ticker)

	md = MarketData(
		ticker_id=ticker.id,
		timeframe="15m",
		close=Decimal("142.75"),
		volume=Decimal("987654.32"),
	)

	session.add(md)
	await session.commit()
	await session.refresh(md)

	assert md.timestamp is not None
	assert isinstance(md.timestamp, datetime)
	assert md.timestamp.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_market_data_unique_constraint_violation(session: AsyncSession):
	"""Проверка уникального ограничения (ticker_id, timeframe, timestamp)"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="LINKUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()
	await session.refresh(ticker)

	ts = datetime(2025, 6, 15, 14, 30, tzinfo=timezone.utc)

	md1 = MarketData(
		ticker_id=ticker.id, timeframe="30m", timestamp=ts, close=Decimal("18.45")
	)

	md2 = MarketData(
		ticker_id=ticker.id, timeframe="30m", timestamp=ts, close=Decimal("18.60")
	)

	session.add(md1)
	await session.commit()

	session.add(md2)
	with pytest.raises(IntegrityError):
		await session.commit()


@pytest.mark.asyncio
async def test_market_data_nullable_ohlcv_fields(session: AsyncSession):
	"""Проверка, что OHLCV могут быть NULL"""
	binance = Exchange(name="Binance", code="BINANCE")
	session.add(binance)
	await session.commit()
	ticker = Ticker(
		symbol="LINKUSDT",
		asset_type="CRYPTO",
		exchange_id=binance.id,
		base_currency="BTC",
		quote_currency="USDT",
	)
	session.add(ticker)
	await session.commit()
	await session.refresh(ticker)

	md = MarketData(ticker_id=ticker.id, timeframe="1d")

	session.add(md)
	await session.commit()
	await session.refresh(md)

	assert md.open is None
	assert md.high is None
	assert md.low is None
	assert md.close is None
	assert md.volume is None


@pytest.mark.asyncio
async def test_market_data_ingested_at_autofill(session: AsyncSession, ticker: Ticker):
	"""Проверка автоматического заполнения ingested_at"""
	md = MarketData(
		ticker_id=ticker.id,
		timeframe="4h",
		timestamp=datetime(2025, 12, 1, 10, 0, tzinfo=timezone.utc),
		close=Decimal("0.4123"),
	)

	session.add(md)
	await session.commit()
	await session.refresh(md)

	assert md.ingested_at is not None
	assert isinstance(md.ingested_at, datetime)
	assert md.ingested_at.tzinfo == timezone.utc
	assert (datetime.now(timezone.utc) - md.ingested_at).total_seconds() < 5


@pytest.mark.asyncio
async def test_market_data_source_field_variants(session: AsyncSession, ticker: Ticker):
	"""Поле source — можно указывать, можно None"""
	md1 = MarketData(
		ticker_id=ticker.id,
		timeframe="1d",
		timestamp=datetime.now(timezone.utc),
		source="binance_api_v3",
	)
	md2 = MarketData(
		ticker_id=ticker.id,
		timeframe="1w",
		timestamp=datetime.now(timezone.utc),
		source=None,
	)

	session.add_all([md1, md2])
	await session.commit()

	await session.refresh(md1)
	await session.refresh(md2)

	assert md1.source == "binance_api_v3"
	assert md2.source is None


@pytest.mark.asyncio
async def test_market_data_missing_ticker_id_forbidden(session: AsyncSession):
	"""Создание MarketData без ticker_id → ForeignKey violation"""
	md = MarketData(
		timeframe="1h",
		timestamp=datetime.now(timezone.utc),
	)

	session.add(md)
	with pytest.raises(IntegrityError):
		await session.commit()


@pytest.mark.asyncio
async def test_timestamps_are_utc_aware(session: AsyncSession, ticker: Ticker):
	md = MarketData(
		ticker_id=ticker.id,
		timeframe="5m",
		timestamp=datetime(2026, 3, 20, 14, 30, tzinfo=timezone.utc),
	)
	session.add(md)
	await session.commit()
	await session.refresh(md)

	assert ticker.created_at.tzinfo == timezone.utc
	assert md.created_at.tzinfo == timezone.utc
	assert md.ingested_at.tzinfo == timezone.utc
	assert md.timestamp.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_exchange_creation_and_defaults(session: AsyncSession):
	"""Проверка создания Exchange и значений по умолчанию"""
	exchange = Exchange(
		name="Binance",
		code="BINANCE",
	)

	session.add(exchange)
	await session.commit()
	await session.refresh(exchange)

	assert isinstance(exchange.id, uuid.UUID)
	assert exchange.name == "Binance"
	assert exchange.code == "BINANCE"

	assert exchange.timezone == "UTC"
	assert exchange.currency == "USD"

	assert isinstance(exchange.created_at, datetime)
	assert exchange.created_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_exchange_unique_name(session: AsyncSession):
	"""name должен быть уникальным"""
	ex1 = Exchange(name="Binance", code="BINANCE")
	ex2 = Exchange(name="Binance", code="BINANCE2")

	session.add(ex1)
	await session.commit()

	session.add(ex2)

	with pytest.raises(IntegrityError):
		await session.commit()

	await session.rollback()


@pytest.mark.asyncio
async def test_exchange_unique_code(session: AsyncSession):
	"""code должен быть уникальным"""
	ex1 = Exchange(name="Binance", code="BINANCE")
	ex2 = Exchange(name="Coinbase", code="BINANCE")

	session.add(ex1)
	await session.commit()

	session.add(ex2)

	with pytest.raises(IntegrityError):
		await session.commit()

	await session.rollback()


@pytest.mark.asyncio
async def test_exchange_tickers_relationship(session: AsyncSession):
	"""Проверка relationship Exchange -> Ticker"""
	exchange = Exchange(name="Binance", code="BINANCE")
	session.add(exchange)
	await session.commit()
	await session.refresh(exchange)

	ticker = Ticker(
		symbol="BTCUSDT",
		asset_type="CRYPTO",
		exchange_id=exchange.id,
		base_currency="BTC",
		quote_currency="USDT",
	)

	session.add(ticker)
	await session.commit()

	result = await session.execute(
		select(Exchange)
		.options(selectinload(Exchange.tickers))
		.where(Exchange.id == exchange.id)
	)
	exchange = result.scalar_one()

	assert len(exchange.tickers) == 1
	assert exchange.tickers[0].symbol == "BTCUSDT"
	assert exchange.tickers[0].exchange_id == exchange.id


@pytest.mark.asyncio
async def test_exchange_delete_cascade(session: AsyncSession):
	"""Проверка cascade delete для тикеров"""
	exchange = Exchange(name="Binance", code="BINANCE")
	session.add(exchange)
	await session.commit()
	await session.refresh(exchange)

	ticker = Ticker(
		symbol="ETHUSDT",
		asset_type="CRYPTO",
		exchange_id=exchange.id,
		base_currency="ETH",
		quote_currency="USDT",
	)

	session.add(ticker)
	await session.commit()

	await session.delete(exchange)
	await session.commit()

	result = await session.get(Ticker, ticker.id)
	assert result is None
