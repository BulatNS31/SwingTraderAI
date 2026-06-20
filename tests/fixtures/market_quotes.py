from datetime import datetime, timezone
from decimal import Decimal

import pytest_asyncio

from swingtraderai.db.models.market_quote import MarketQuoteSnapshot


@pytest_asyncio.fixture
async def market_quote(ticker, user):
	return MarketQuoteSnapshot(
		ticker_id=ticker.id,
		tenant_id=user.tenant_id,
		price=Decimal("100"),
		change_percent=Decimal("1.5"),
		volume=Decimal("1000"),
		updated_at=datetime.now(timezone.utc),
	)


@pytest_asyncio.fixture
def market_quote_factory():
	def factory(
		ticker_id,
		tenant_id,
		price="100",
		change_percent="1.5",
		volume="1000",
	):
		return MarketQuoteSnapshot(
			ticker_id=ticker_id,
			tenant_id=tenant_id,
			price=Decimal(price),
			change_percent=Decimal(change_percent),
			volume=Decimal(volume),
			updated_at=datetime.now(timezone.utc),
		)

	return factory
