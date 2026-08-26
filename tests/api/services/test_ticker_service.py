from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from swingtraderai.api.services.ticker_service import TickerService
from swingtraderai.db.models.market import Exchange, Ticker
from swingtraderai.schemas.ticker import OHLCVDataOut, TickerCreate


async def test_create_ticker_success(
	ticker_service: TickerService, sample_exchange: Exchange, session: AsyncSession
):
	"""Успешное создание тикера"""
	ticker_in = TickerCreate(
		symbol="TSLA",
		asset_type="stock",
		base_currency="USD",
		quote_currency="USD",
		exchange_id=sample_exchange.id,
		is_active=True,
	)

	ticker = await ticker_service.create(ticker_in)

	assert ticker.symbol == "TSLA"
	assert ticker.asset_type == "stock"
	assert ticker.id is not None


async def test_create_ticker_already_exists(
	ticker_service: TickerService,
	sample_ticker: Ticker,
	sample_exchange: Exchange,
):
	"""Попытка создать тикер с уже существующим символом"""
	ticker_in = TickerCreate(
		symbol=sample_ticker.symbol,
		asset_type="stock",
		base_currency="USD",
		quote_currency="USD",
		exchange_id=sample_exchange.id,
		is_active=True,
	)

	with pytest.raises(HTTPException) as exc:
		await ticker_service.create(ticker_in)

	assert exc.value.status_code == 400
	assert "already exists" in exc.value.detail.lower()


async def test_get_all(ticker_service: TickerService, sample_ticker: Ticker):
	tickers = await ticker_service.get_all(skip=0, limit=10)
	assert len(tickers) >= 1
	assert any(t.id == sample_ticker.id for t in tickers)


async def test_get_by_id_success(ticker_service: TickerService, sample_ticker: Ticker):
	ticker = await ticker_service.get_by_id(sample_ticker.id)
	assert ticker.id == sample_ticker.id
	assert ticker.symbol == sample_ticker.symbol


async def test_get_by_id_not_found(ticker_service: TickerService):
	with pytest.raises(HTTPException) as exc:
		await ticker_service.get_by_id(uuid7())
	assert exc.value.status_code == 404
	assert exc.value.detail == "Ticker not found"


async def test_search_success(ticker_service: TickerService, sample_ticker: Ticker):
	results = await ticker_service.search(q="GOOG", limit=5)
	assert len(results) >= 1
	assert any(t.symbol == "GOOGL" for t in results)


async def test_search_too_short_query(ticker_service: TickerService):
	with pytest.raises(HTTPException) as exc:
		await ticker_service.search(q="", limit=10)
	assert exc.value.status_code == 400
	assert "too short" in exc.value.detail.lower()


async def test_bulk_create_success(
	ticker_service: TickerService,
	sample_exchange: Exchange,
):
	tickers_in = [
		TickerCreate(
			symbol="NVDA",
			asset_type="stock",
			base_currency="USD",
			quote_currency="USD",
			exchange_id=sample_exchange.id,
		),
		TickerCreate(
			symbol="AMZN",
			asset_type="stock",
			base_currency="USD",
			quote_currency="USD",
			exchange_id=sample_exchange.id,
		),
	]

	created = await ticker_service.bulk_create(tickers_in)
	assert len(created) == 2


async def test_bulk_create_too_many(ticker_service: TickerService):
	tickers_in = [
		TickerCreate(
			symbol=f"TICK{i}",
			asset_type="stock",
			base_currency="USD",
			quote_currency="USD",
		)
		for i in range(600)
	]

	with pytest.raises(HTTPException) as exc:
		await ticker_service.bulk_create(tickers_in)
	assert exc.value.status_code == 400
	assert "max 500" in exc.value.detail


async def test_get_historical_data_success(
	ticker_service: TickerService, sample_ticker: Ticker, sample_market_data
):
	data = await ticker_service.get_historical_data(
		ticker_id=sample_ticker.id,
		timeframe="1d",
		limit=20,
	)

	assert len(data) > 0
	assert isinstance(data[0], OHLCVDataOut)
	assert data[0].ticker_id == UUID(bytes=sample_ticker.id.bytes)


async def test_get_historical_data_with_date_filter(
	ticker_service: TickerService, sample_ticker: Ticker, sample_market_data
):
	end_date = datetime.now(timezone.utc)
	start_date = end_date - timedelta(days=10)

	data = await ticker_service.get_historical_data(
		ticker_id=sample_ticker.id,
		timeframe="1d",
		start_date=start_date,
		end_date=end_date,
		limit=100,
	)

	assert len(data) > 0


async def test_get_historical_data_ticker_not_found(ticker_service: TickerService):
	with pytest.raises(HTTPException) as exc:
		await ticker_service.get_historical_data(ticker_id=uuid7())
	assert exc.value.status_code == 404


async def test_get_technical_indicators_success(
	ticker_service: TickerService, sample_ticker: Ticker, sample_market_data
):
	result = await ticker_service.get_technical_indicators(
		ticker_id=sample_ticker.id,
		period="1d",
		indicators="rsi,sma20,macd",
	)

	assert result["ticker_id"] == str(sample_ticker.id)
	assert result["period"] == "1d"
	assert result["data_points"] > 0
	assert "indicators" in result


async def test_get_technical_indicators_no_data(
	ticker_service: TickerService, sample_ticker: Ticker
):
	with pytest.raises(HTTPException) as exc:
		await ticker_service.get_technical_indicators(
			ticker_id=sample_ticker.id, period="1h"
		)
	assert exc.value.status_code == 404


async def test_get_trading_signals_success(
	ticker_service: TickerService, sample_ticker: Ticker, sample_market_data
):
	result = await ticker_service.get_trading_signals(
		ticker_id=sample_ticker.id, period="1d"
	)

	assert result["ticker_id"] == str(sample_ticker.id)
	assert result["signal"] in ["buy", "sell", "hold"]
	assert "confidence" in result


async def test_get_trading_signals_no_data(
	ticker_service: TickerService, sample_ticker: Ticker
):
	with pytest.raises(HTTPException) as exc:
		await ticker_service.get_trading_signals(
			ticker_id=sample_ticker.id, period="1h"
		)
	assert exc.value.status_code == 404
