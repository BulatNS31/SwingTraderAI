from datetime import datetime, timezone
from decimal import Decimal

from swingtraderai.api.services.market_data.market_data_service import MarketDataService
from swingtraderai.schemas.market_data import MarketQuoteSchema


def test_detect_market_types():
	mds = MarketDataService()
	assert mds._detect_market("BTC/USDT") == "crypto"
	assert mds._detect_market("ETH/USDT") == "crypto"
	assert mds._detect_market("SBER.ME") == "moex"
	assert mds._detect_market("GAZP.ME") == "moex"
	assert mds._detect_market("AAPL") == "us"
	assert mds._detect_market("SPY") == "us"


def test_market_quote_schema_validation():
	q = MarketQuoteSchema(
		symbol="AAPL",
		price=Decimal("123.45"),
		change_percent=1.23,
		volume=1000.0,
		exchange_code="NASDAQ",
		updated_at=datetime.now(timezone.utc),
	)

	assert q.symbol == "AAPL"
	assert q.price == Decimal("123.45")
	assert q.change_percent == 1.23
	assert q.volume == 1000.0
	assert q.exchange_code == "NASDAQ"
	assert isinstance(q.updated_at, datetime)
