from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from swingtraderai.api.services.ticker_service import TickerService
from swingtraderai.api.services.watchlist_service import WatchlistService
from swingtraderai.db.models.market import Exchange, MarketData, Ticker
from swingtraderai.schemas.watchlist import WatchlistCreate


@pytest_asyncio.fixture
async def sample_ticker(session: AsyncSession, sample_exchange: Exchange) -> Ticker:
	"""Создаёт тестовый тикер AAPL"""
	ticker = Ticker(
		symbol="GOOGL",
		asset_type="stock",
		exchange_id=sample_exchange.id,
		base_currency="USD",
		quote_currency="USD",
		is_active=True,
	)
	session.add(ticker)
	await session.flush()
	await session.refresh(ticker)
	return ticker


@pytest_asyncio.fixture
async def ticker(
	session: AsyncSession, sample_exchange: Exchange
) -> AsyncGenerator[Ticker, None]:
	"""Создает тестовую биржу и тикер, связывая их через ID"""
	test_ticker = Ticker(
		symbol="AAPL",
		asset_type="stock",
		exchange_id=sample_exchange.id,
		base_currency="USD",
		quote_currency="USD",
		is_active=True,
	)

	session.add(test_ticker)
	await session.flush()
	await session.refresh(test_ticker)

	yield test_ticker


@pytest_asyncio.fixture
async def ticker_service(session: AsyncSession) -> TickerService:
	return TickerService(session)


@pytest_asyncio.fixture
async def sample_exchange(session: AsyncSession) -> Exchange:
	"""Создаёт тестовую биржу"""
	exchange = Exchange(
		name="NASDAQ",
		code=f"NSDQ_{uuid7().hex[:8]}",
		timezone="America/New_York",
		currency="USD",
	)
	session.add(exchange)
	await session.flush()
	await session.refresh(exchange)
	return exchange


@pytest_asyncio.fixture
async def sample_market_data(
	session: AsyncSession, sample_ticker: Ticker
) -> list[MarketData]:
	"""Создаёт исторические данные"""
	now = datetime.now(timezone.utc)
	data = []

	for i in range(50):
		md = MarketData(
			ticker_id=sample_ticker.id,
			timeframe="1d",
			timestamp=now - timedelta(days=i),
			open=Decimal("150") + Decimal(i),
			high=Decimal("155") + Decimal(i),
			low=Decimal("148") + Decimal(i),
			close=Decimal("152") + Decimal(i) * Decimal("0.5"),
			volume=Decimal(100_000 + i * 1_000),
			source="test",
		)
		data.append(md)

	session.add_all(data)
	await session.commit()
	return data


@pytest_asyncio.fixture
async def watchlist(watchlist_service, user):
	watchlist_in = WatchlistCreate(name="Sample Watchlist", description="For testing")
	return await watchlist_service.create_watchlist(
		tenant_id=user.tenant_id, user_id=user.id, watchlist_in=watchlist_in
	)


@pytest_asyncio.fixture
async def watchlist_service(session):
	return WatchlistService(session)
