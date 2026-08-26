from datetime import datetime, timezone
from decimal import Decimal

import pytest
from uuid6 import uuid7

from swingtraderai.api.repositories.market_quote_repository import MarketQuoteRepository
from swingtraderai.db.models.market import Exchange, Ticker
from swingtraderai.schemas.market_data import MarketQuoteSchema


@pytest.mark.usefixtures("session", "ticker", "sample_exchange")
class TestMarketQuoteRepository:
	@pytest.fixture(autouse=True)
	def setup(self, session):
		self.repo = MarketQuoteRepository(session)
		self.session = session

	@pytest.mark.asyncio
	async def test_get_by_symbol(self, ticker, market_quote_factory):
		tenant_id = uuid7()

		quote = market_quote_factory(ticker_id=ticker.id, tenant_id=tenant_id)

		self.session.add(quote)
		await self.session.commit()

		result = await self.repo.get_by_symbol(tenant_id, ticker.symbol)

		assert result is not None
		assert result.ticker_id == ticker.id
		assert result.price == Decimal("100")

	@pytest.mark.asyncio
	async def test_get_by_symbol_returns_none_for_wrong_tenant(
		self, ticker, market_quote_factory
	):
		tenant_id = uuid7()
		other_tenant = uuid7()

		quote = market_quote_factory(
			ticker_id=ticker.id,
			tenant_id=other_tenant,
		)

		self.session.add(quote)
		await self.session.commit()

		result = await self.repo.get_by_symbol(tenant_id, ticker.symbol)

		assert result is None

	@pytest.mark.asyncio
	async def test_get_by_market_type(
		self, ticker, sample_ticker, sample_exchange, market_quote_factory
	):
		tenant_id = uuid7()

		q1 = market_quote_factory(
			ticker_id=ticker.id,
			tenant_id=tenant_id,
		)

		q2 = market_quote_factory(
			ticker_id=sample_ticker.id,
			tenant_id=tenant_id,
		)

		self.session.add_all([q1, q2])
		await self.session.commit()

		result = await self.repo.get_by_market_type(tenant_id, sample_exchange.code)

		assert len(result) == 2
		assert result[0].updated_at >= result[1].updated_at

	@pytest.mark.asyncio
	async def test_upsert_from_quote_insert(
		self, ticker: Ticker, sample_exchange: Exchange
	):
		tenant_id = uuid7()

		quote = MarketQuoteSchema(
			symbol=ticker.symbol,
			price=200.0,
			change_percent=5.0,
			volume=2000,
			exchange_code=sample_exchange.code,
			updated_at=datetime.now(timezone.utc),
		)

		result = await self.repo.upsert_from_quote(tenant_id, ticker.id, quote)

		assert result is not None
		assert result.ticker_id == ticker.id
		assert result.price == Decimal(str(quote.price))

	@pytest.mark.asyncio
	async def test_upsert_from_quote_update(
		self,
		ticker: Ticker,
		market_quote_factory,
		sample_exchange: Exchange,
	):
		tenant_id = uuid7()

		existing = market_quote_factory(
			ticker_id=ticker.id,
			tenant_id=tenant_id,
			price=Decimal("100"),
			change_percent=Decimal("0"),
			volume=Decimal("1000"),
		)

		self.session.add(existing)
		await self.session.commit()

		quote = MarketQuoteSchema(
			symbol=ticker.symbol,
			price=200.0,
			change_percent=5.0,
			volume=2000,
			exchange_code=sample_exchange.code,
			updated_at=datetime.now(timezone.utc),
		)

		result = await self.repo.upsert_from_quote(tenant_id, ticker.id, quote)

		assert result.price == Decimal("200")
		assert result.volume == Decimal("2000")

	@pytest.mark.asyncio
	async def test_list_recent(self, ticker, sample_ticker, market_quote_factory):
		tenant_id = uuid7()

		q1 = market_quote_factory(
			ticker_id=ticker.id,
			tenant_id=tenant_id,
		)

		q2 = market_quote_factory(
			ticker_id=sample_ticker.id,
			tenant_id=tenant_id,
		)

		self.session.add_all([q1, q2])
		await self.session.commit()

		result = await self.repo.list_recent(tenant_id)

		assert len(result) == 2
		assert result[0].updated_at >= result[1].updated_at
