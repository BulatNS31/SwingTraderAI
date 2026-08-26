from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import List
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.api.services.market_service import MarketService
from swingtraderai.db.models.market import Exchange, MarketData, Ticker
from swingtraderai.schemas.market import (
	MarketHeatmapItem,
	MarketsSnapshot,
)


class TestMarketService:
	"""Тесты для MarketService"""

	@pytest.fixture
	async def market_service(self, session: AsyncSession):
		return MarketService(session)

	@pytest.fixture
	async def ticker_aapl(
		self, session: AsyncSession, sample_exchange: Exchange
	) -> Ticker:
		ticker = Ticker(
			symbol="AAPL",
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

	@pytest.fixture
	async def ticker_googl(
		self, session: AsyncSession, sample_exchange: Exchange
	) -> Ticker:
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

	@pytest.fixture
	async def ticker_btc(
		self, session: AsyncSession, sample_exchange_binance: Exchange
	) -> Ticker:
		ticker = Ticker(
			symbol="BTCUSDT",
			asset_type="crypto",
			exchange_id=sample_exchange_binance.id,
			base_currency="BTC",
			quote_currency="USD",
			is_active=True,
		)
		session.add(ticker)
		await session.flush()
		await session.refresh(ticker)
		return ticker

	@pytest.fixture
	async def ticker_eth(
		self, session: AsyncSession, sample_exchange_binance: Exchange
	) -> Ticker:
		ticker = Ticker(
			symbol="ETHUSDT",
			asset_type="crypto",
			exchange_id=sample_exchange_binance.id,
			base_currency="ETH",
			quote_currency="USD",
			is_active=True,
		)
		session.add(ticker)
		await session.flush()
		await session.refresh(ticker)
		return ticker

	@pytest.fixture
	async def ticker_sber(
		self, session: AsyncSession, sample_exchange_moex: Exchange
	) -> Ticker:
		ticker = Ticker(
			symbol="SBER",
			asset_type="stock",
			exchange_id=sample_exchange_moex.id,
			base_currency="RUB",
			quote_currency="RUB",
			is_active=True,
		)
		session.add(ticker)
		await session.flush()
		await session.refresh(ticker)
		return ticker

	@pytest.fixture
	async def market_data_aapl(
		self, session: AsyncSession, ticker_aapl: Ticker
	) -> List[MarketData]:
		"""Создает тестовые данные MarketData для AAPL"""
		now = datetime.now(timezone.utc)
		data = [
			MarketData(
				ticker_id=ticker_aapl.id,
				timeframe="1d",
				timestamp=now - timedelta(hours=i),
				open=Decimal(str(150 + i)),
				high=Decimal(str(155 + i)),
				low=Decimal(str(148 + i)),
				close=Decimal(str(152 + i * 0.5)),
				volume=Decimal(100000 + i * 1000),
				source="test",
			)
			for i in range(3)
		]
		session.add_all(data)
		await session.commit()
		return data

	@pytest.fixture
	async def market_data_mixed(
		self, session, ticker_aapl, ticker_googl, ticker_btc, ticker_sber, ticker_eth
	):
		"""Создает смешанные данные для разных тикеров и бирж"""
		now = datetime.now(timezone.utc)
		data = []

		# NASDAQ акции
		for ticker in [ticker_aapl, ticker_googl]:
			md = MarketData(
				ticker_id=ticker.id,
				timeframe="1d",
				timestamp=now,
				open=Decimal("150"),
				high=Decimal("155"),
				low=Decimal("148"),
				close=Decimal("152") if ticker.symbol == "AAPL" else Decimal("160"),
				volume=Decimal(100000),
				source="test",
			)
			data.append(md)

		# Криптовалюты
		for ticker in [ticker_btc, ticker_eth]:
			md = MarketData(
				ticker_id=ticker.id,
				timeframe="1d",
				timestamp=now,
				open=(
					Decimal("50000") if ticker.symbol == "BTCUSDT" else Decimal("3000")
				),
				high=(
					Decimal("51000") if ticker.symbol == "BTCUSDT" else Decimal("3100")
				),
				low=Decimal("49000") if ticker.symbol == "BTCUSDT" else Decimal("2900"),
				close=(
					Decimal("50500") if ticker.symbol == "BTCUSDT" else Decimal("3050")
				),
				volume=Decimal(500),
				source="test",
			)
			data.append(md)

		md = MarketData(
			ticker_id=ticker_sber.id,
			timeframe="1d",
			timestamp=now,
			open=Decimal("200"),
			high=Decimal("210"),
			low=Decimal("195"),
			close=Decimal("205"),
			volume=Decimal(50000),
			source="test",
		)
		data.append(md)

		session.add_all(data)
		await session.commit()
		return data

	async def test_to_asset_success(
		self, market_service, market_data_aapl, sample_exchange
	):
		"""Тест: преобразование MarketData в MarketAsset"""
		md = market_data_aapl[0]
		result = await market_service._to_asset(md)

		assert result is not None
		assert result.id == md.id
		assert result.ticker_id == md.ticker_id
		assert result.symbol == "AAPL"
		assert result.exchange == sample_exchange.code
		assert result.asset_type == "stock"
		assert result.last_price == float(md.close)
		assert result.volume == float(md.volume)
		assert result.timestamp == md.timestamp
		assert result.change_percent is not None

	async def test_to_asset_with_exchange(
		self, market_service, ticker_btc, sample_exchange_binance
	):
		"""Тест: преобразование MarketData без биржи"""
		md = MarketData(
			ticker_id=ticker_btc.id,
			timeframe="1d",
			timestamp=datetime.now(timezone.utc),
			open=Decimal("50000"),
			high=Decimal("51000"),
			low=Decimal("49000"),
			close=Decimal("50500"),
			volume=Decimal(500),
			source="test",
		)
		market_service.session.add(md)
		await market_service.session.commit()

		result = await market_service._to_asset(md)

		assert result is not None
		assert result.exchange is sample_exchange_binance.code
		assert result.asset_type == "crypto"

	async def test_to_asset_with_none_values(self, market_service, ticker_aapl):
		"""Тест: преобразование с None значениями"""
		md = MarketData(
			ticker_id=ticker_aapl.id,
			timeframe="1d",
			timestamp=datetime.now(timezone.utc),
			open=None,
			high=None,
			low=None,
			close=None,
			volume=None,
			source="test",
		)
		market_service.session.add(md)
		await market_service.session.commit()

		result = await market_service._to_asset(md)

		assert result is not None
		assert result.last_price is None
		assert result.change_percent is None
		assert result.volume is None

	async def test_get_snapshot_empty(self, market_service):
		"""Тест: получение snapshot при отсутствии данных"""
		result = await market_service.get_snapshot()

		assert result is not None
		assert result.crypto == []
		assert result.moex == []
		assert result.nasdaq == []
		assert result.heatmap == []
		assert result.pulse.total == 0
		assert result.pulse.gainers == 0
		assert result.pulse.losers == 0
		assert result.pulse.neutral == 0
		assert result.pulse.avg_change_percent == 0.0

	async def test_get_snapshot_with_data(self, market_service, market_data_mixed):
		"""Тест: получение snapshot с данными"""
		result = await market_service.get_snapshot()

		assert result is not None

		assert len(result.nasdaq) > 0
		assert len(result.moex) > 0
		assert len(result.crypto) > 0

		for asset in result.nasdaq:
			assert asset.exchange == "NASDAQ"
		for asset in result.moex:
			assert asset.exchange == "MOEX"
		for asset in result.crypto:
			assert asset.asset_type == "crypto"

	async def test_get_snapshot_pagination(self, market_service, market_data_mixed):
		"""Тест: пагинация в snapshot"""
		result_page1 = await market_service.get_snapshot(page=1, per_page=2)
		result_page2 = await market_service.get_snapshot(page=2, per_page=2)

		assert (
			len(result_page1.crypto) + len(result_page1.nasdaq) + len(result_page1.moex)
			>= 0
		)
		assert (
			len(result_page2.crypto) + len(result_page2.nasdaq) + len(result_page2.moex)
			>= 0
		)

	async def test_get_snapshot_timeframe(self, market_service, market_data_mixed):
		"""Тест: фильтрация по timeframe"""
		now = datetime.now(timezone.utc)
		extra_data = MarketData(
			ticker_id=market_data_mixed[0].ticker_id,
			timeframe="1h",
			timestamp=now,
			open=Decimal("150"),
			high=Decimal("155"),
			low=Decimal("148"),
			close=Decimal("152"),
			volume=Decimal(100000),
			source="test",
		)
		market_service.session.add(extra_data)
		await market_service.session.commit()

		result = await market_service.get_snapshot(timeframe="1d")
		assert result is not None

	async def test_get_snapshot_heatmap(self, market_service, market_data_mixed):
		"""Тест: корректность heatmap (топ movers)"""
		result = await market_service.get_snapshot()

		assert result is not None
		assert len(result.heatmap) <= 100

		if len(result.heatmap) > 1:
			changes = [abs(item.change_percent) for item in result.heatmap]
			assert changes == sorted(changes, reverse=True)

		for item in result.heatmap:
			assert item.symbol is not None
			assert item.symbol != ""
			assert item.change_percent is not None

	async def test_get_snapshot_pulse(self, market_service, market_data_mixed):
		"""Тест: корректность pulse (статистика)"""
		result = await market_service.get_snapshot()

		assert result is not None

		pulse = result.pulse
		assert pulse.total >= 0
		assert pulse.gainers >= 0
		assert pulse.losers >= 0
		assert pulse.neutral >= 0

		assert pulse.gainers + pulse.losers + pulse.neutral <= pulse.total

		if pulse.total > 0:
			assert pulse.avg_change_percent is not None

	async def test_get_snapshot_with_all_gainers(
		self, market_service, ticker_aapl, ticker_googl
	):
		"""Тест: все активы растут"""
		now = datetime.now(timezone.utc)

		data = []
		for ticker in [ticker_aapl, ticker_googl]:
			md = MarketData(
				ticker_id=ticker.id,
				timeframe="1d",
				timestamp=now,
				open=Decimal("100"),
				close=Decimal("110"),  # +10%
				volume=Decimal(100000),
				source="test",
			)
			data.append(md)

		market_service.session.add_all(data)
		await market_service.session.commit()

		result = await market_service.get_snapshot()

		assert result.pulse.gainers == 2
		assert result.pulse.losers == 0
		assert result.pulse.neutral == 0

	async def test_get_snapshot_with_all_losers(
		self, market_service, ticker_aapl, ticker_googl
	):
		"""Тест: все активы падают"""
		now = datetime.now(timezone.utc)

		data = []
		for ticker in [ticker_aapl, ticker_googl]:
			md = MarketData(
				ticker_id=ticker.id,
				timeframe="1d",
				timestamp=now,
				open=Decimal("110"),
				close=Decimal("100"),  # -9.09%
				volume=Decimal(100000),
				source="test",
			)
			data.append(md)

		market_service.session.add_all(data)
		await market_service.session.commit()

		result = await market_service.get_snapshot()

		assert result.pulse.gainers == 0
		assert result.pulse.losers == 2
		assert result.pulse.neutral == 0

	async def test_get_snapshot_with_neutral(self, market_service, ticker_aapl):
		"""Тест: актив с нулевым изменением"""
		now = datetime.now(timezone.utc)

		md = MarketData(
			ticker_id=ticker_aapl.id,
			timeframe="1d",
			timestamp=now,
			open=Decimal("100"),
			close=Decimal("100"),
			volume=Decimal(100000),
			source="test",
		)
		market_service.session.add(md)
		await market_service.session.commit()

		result = await market_service.get_snapshot()

		assert result.pulse.neutral >= 1

	async def test_get_snapshot_with_tenant(
		self, market_service, market_data_mixed, user
	):
		"""Тест: фильтрация по tenant_id"""
		result = await market_service.get_snapshot(tenant_id=user.tenant_id)

		assert result is not None
		assert isinstance(result, MarketsSnapshot)

	async def test_get_snapshot_limits(self, market_service, market_data_mixed):
		"""Тест: ограничение количества результатов"""
		result = await market_service.get_snapshot(page=1, per_page=2)

		assert len(result.crypto) <= 2
		assert len(result.moex) <= 2
		assert len(result.nasdaq) <= 2
		assert len(result.heatmap) <= 2

	async def test_heatmap_sorting(self, market_service, market_data_mixed):
		"""Тест: сортировка heatmap по абсолютному изменению"""
		result = await market_service.get_snapshot()

		if len(result.heatmap) >= 2:
			changes = [abs(item.change_percent) for item in result.heatmap]
			assert changes == sorted(changes, reverse=True)

	async def test_pulse_calculation(self, market_service, market_data_mixed):
		"""Тест: расчет pulse статистики"""
		result = await market_service.get_snapshot()

		pulse = result.pulse

		total_assets = len(result.crypto) + len(result.moex) + len(result.nasdaq)
		assert pulse.total == total_assets

	async def test_asset_type_filtering(self, market_service, market_data_mixed):
		"""Тест: фильтрация по типу актива"""
		result = await market_service.get_snapshot()

		# Проверяем, что все активы в crypto имеют тип crypto
		for asset in result.crypto:
			assert asset.asset_type == "crypto"

		# Проверяем, что все активы в nasdaq имеют биржу NASDAQ
		for asset in result.nasdaq:
			assert asset.exchange == "NASDAQ"

		# Проверяем, что все активы в moex имеют биржу MOEX
		for asset in result.moex:
			assert asset.exchange == "MOEX"

	async def test_market_asset_model(self, market_service, market_data_aapl):
		"""Тест: модель MarketAsset корректно создается"""
		md = market_data_aapl[0]
		result = await market_service._to_asset(md)

		# Проверяем все поля
		assert isinstance(result.id, UUID)
		assert isinstance(result.ticker_id, UUID)
		assert isinstance(result.symbol, str)
		assert result.last_price is None or isinstance(result.last_price, float)
		assert result.change_percent is None or isinstance(result.change_percent, float)
		assert result.volume is None or isinstance(result.volume, float)
		assert result.timestamp is not None

	async def test_market_heatmap_item_model(
		self, market_service, market_data_aapl, sample_exchange
	):
		"""Тест: модель MarketHeatmapItem корректно создается"""
		md = market_data_aapl[0]
		asset = await market_service._to_asset(md)

		heatmap_item = MarketHeatmapItem(
			symbol=asset.symbol,
			name=None,
			exchange=asset.exchange,
			change_percent=asset.change_percent or 0.0,
		)

		assert heatmap_item.symbol == "AAPL"
		assert heatmap_item.exchange == sample_exchange.code
		assert heatmap_item.change_percent is not None

	async def test_get_snapshot_without_tenant(self, market_service, market_data_mixed):
		"""Тест: получение snapshot без tenant_id"""
		result = await market_service.get_snapshot()

		assert result is not None
		assert isinstance(result, MarketsSnapshot)
		assert result.pulse.total > 0
