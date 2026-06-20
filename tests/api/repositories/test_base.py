from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import UUID, Column, String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import declarative_base
from uuid6 import uuid7

from swingtraderai.api.repositories.base import BaseRepository, TenantAwareRepository
from swingtraderai.db.models.market import Exchange, Ticker
from swingtraderai.db.models.market_quote import MarketQuoteSnapshot


class TestBaseRepository:
	"""Тесты для базового репозитория"""

	@pytest.fixture
	def repo(self, session: AsyncSession):
		"""Создает репозиторий для Ticker"""
		return BaseRepository(session, Ticker)

	@pytest.mark.asyncio
	async def test_get_by_id_found(self, repo: BaseRepository, sample_ticker: Ticker):
		"""Тест получения записи по ID - запись найдена"""
		result = await repo.get_by_id(sample_ticker.id)

		assert result is not None
		assert result.id == sample_ticker.id
		assert result.symbol == sample_ticker.symbol

	@pytest.mark.asyncio
	async def test_get_by_id_not_found(self, repo: BaseRepository):
		"""Тест получения записи по ID - запись не найдена"""
		non_existent_id = uuid7()
		result = await repo.get_by_id(non_existent_id)

		assert result is None

	@pytest.mark.asyncio
	async def test_get_all_without_filters(
		self, repo: BaseRepository, session: AsyncSession, sample_exchange
	):
		"""Тест получения всех записей без фильтров"""
		# Создаем несколько тикеров
		tickers = []
		for i in range(3):
			ticker = Ticker(
				symbol=f"TEST_{i}",
				asset_type="stock",
				exchange_id=sample_exchange.id,
				base_currency="USD",
				quote_currency="USD",
				is_active=True,
			)
			session.add(ticker)
			tickers.append(ticker)
		await session.commit()

		result = await repo.get_all()

		assert len(result) >= 3
		assert all(isinstance(t, Ticker) for t in result)

	@pytest.mark.asyncio
	async def test_get_all_with_filters(
		self, repo: BaseRepository, session: AsyncSession, sample_exchange
	):
		"""Тест получения записей с фильтрами"""
		# Создаем тикеры с разными символами
		ticker1 = Ticker(
			symbol="AAPL",
			asset_type="stock",
			exchange_id=sample_exchange.id,
			base_currency="USD",
			quote_currency="USD",
			is_active=True,
		)
		ticker2 = Ticker(
			symbol="GOOGL",
			asset_type="stock",
			exchange_id=sample_exchange.id,
			base_currency="USD",
			quote_currency="USD",
			is_active=True,
		)
		session.add_all([ticker1, ticker2])
		await session.commit()

		result = await repo.get_all(symbol="AAPL")

		assert len(result) == 1
		assert result[0].symbol == "AAPL"

	@pytest.mark.asyncio
	async def test_get_all_with_pagination(
		self, repo: BaseRepository, session: AsyncSession, sample_exchange
	):
		"""Тест пагинации"""
		# Создаем 5 тикеров
		for i in range(5):
			ticker = Ticker(
				symbol=f"PAGE_{i}",
				asset_type="stock",
				exchange_id=sample_exchange.id,
				base_currency="USD",
				quote_currency="USD",
				is_active=True,
			)
			session.add(ticker)
		await session.commit()

		# Первая страница - 2 записи
		result_page1 = await repo.get_all(skip=0, limit=2)
		assert len(result_page1) == 2

		# Вторая страница - 2 записи
		result_page2 = await repo.get_all(skip=2, limit=2)
		assert len(result_page2) == 2

		# Третья страница - 1 запись
		result_page3 = await repo.get_all(skip=4, limit=2)
		assert len(result_page3) == 1

	@pytest.mark.asyncio
	async def test_create_from_dict(
		self, repo: BaseRepository, session: AsyncSession, sample_exchange
	):
		"""Тест создания записи из словаря"""
		ticker_data = {
			"symbol": "MSFT",
			"asset_type": "stock",
			"exchange_id": sample_exchange.id,
			"base_currency": "USD",
			"quote_currency": "USD",
			"is_active": True,
		}

		result = await repo.create(ticker_data)

		assert result is not None
		assert result.symbol == "MSFT"
		assert result.id is not None

		# Проверяем, что запись действительно сохранена
		db_result = await session.get(Ticker, result.id)
		assert db_result is not None

	@pytest.mark.asyncio
	async def test_create_from_object(
		self, repo: BaseRepository, session: AsyncSession, sample_exchange
	):
		"""Тест создания записи из объекта"""
		ticker = Ticker(
			symbol="TSLA",
			asset_type="stock",
			exchange_id=sample_exchange.id,
			base_currency="USD",
			quote_currency="USD",
			is_active=True,
		)

		result = await repo.create(ticker)

		assert result is not None
		assert result.symbol == "TSLA"
		assert result.id is not None

	@pytest.mark.asyncio
	async def test_update_from_dict(self, repo: BaseRepository, sample_ticker: Ticker):
		"""Тест обновления записи из словаря"""
		update_data = {
			"symbol": "UPDATED",
			"is_active": False,
		}

		result = await repo.update(sample_ticker.id, update_data)

		assert result is not None
		assert result.symbol == "UPDATED"
		assert result.is_active is False

	@pytest.mark.asyncio
	async def test_update_from_object(
		self, repo: BaseRepository, sample_ticker: Ticker
	):
		"""Тест обновления записи из объекта"""
		updated_ticker = Ticker(
			symbol="UPDATED_OBJ",
			is_active=False,
		)

		result = await repo.update(sample_ticker.id, updated_ticker)

		assert result is not None
		assert result.symbol == "UPDATED_OBJ"
		assert result.is_active is False

	@pytest.mark.asyncio
	async def test_update_not_found(self, repo: BaseRepository):
		"""Тест обновления несуществующей записи"""
		non_existent_id = uuid7()
		result = await repo.update(non_existent_id, {"symbol": "NEW"})

		assert result is None

	@pytest.mark.asyncio
	async def test_delete_found(
		self, repo: BaseRepository, session: AsyncSession, sample_ticker: Ticker
	):
		"""Тест удаления существующей записи"""
		ticker_id = sample_ticker.id

		result = await repo.delete(ticker_id)

		assert result is True

		# Проверяем, что запись удалена
		db_result = await session.get(Ticker, ticker_id)
		assert db_result is None

	@pytest.mark.asyncio
	async def test_delete_not_found(self, repo: BaseRepository):
		"""Тест удаления несуществующей записи"""
		non_existent_id = uuid7()
		result = await repo.delete(non_existent_id)

		assert result is False


# ============================================================
# Тесты для TenantAwareRepository
# ============================================================

Base = declarative_base()


class TestModelWithoutId(Base):
	"""Тестовая модель БЕЗ поля id"""

	__tablename__ = "test_models_without_id"
	__test__ = False

	tenant_id = Column(UUID, primary_key=True)
	name = Column(String, nullable=False)


class TestTenantAwareRepository:
	"""Тесты для tenant-aware репозитория"""

	@pytest.fixture
	def repo(self, session: AsyncSession):
		"""Создает tenant-aware репозиторий для MarketQuoteSnapshot"""
		return TenantAwareRepository(session, MarketQuoteSnapshot)

	@pytest.fixture
	def tenant_id(self) -> UUID:
		"""Создает tenant ID"""
		return uuid7()

	@pytest.fixture
	def another_tenant_id(self) -> UUID:
		"""Создает другой tenant ID"""
		return uuid7()

	@pytest.fixture
	async def sample_quote(
		self,
		session: AsyncSession,
		repo: TenantAwareRepository,
		ticker: Ticker,
		tenant_id: UUID,
	) -> MarketQuoteSnapshot:
		"""Создает тестовую котировку"""
		quote = MarketQuoteSnapshot(
			ticker_id=ticker.id,
			price=Decimal("150.50"),
			change_percent=Decimal("2.5"),
			volume=Decimal("1000000"),
			updated_at=datetime.now(timezone.utc),
		)
		result = await repo.create(tenant_id, quote)
		return result

	@pytest.mark.asyncio
	async def test_get_by_id_found(
		self,
		repo: TenantAwareRepository,
		sample_quote: MarketQuoteSnapshot,
		tenant_id: UUID,
	):
		"""Тест получения записи по ID - запись найдена"""
		result = await repo.get_by_id(tenant_id, sample_quote.ticker_id)

		assert result is not None
		assert result.ticker_id == sample_quote.ticker_id
		assert result.tenant_id == tenant_id

	@pytest.mark.asyncio
	async def test_get_by_id_not_found(
		self, repo: TenantAwareRepository, tenant_id: UUID
	):
		"""Тест получения записи по ID - запись не найдена"""
		non_existent_id = uuid7()
		result = await repo.get_by_id(tenant_id, non_existent_id)

		assert result is None

	@pytest.mark.asyncio
	async def test_get_by_id_wrong_tenant(
		self,
		repo: TenantAwareRepository,
		sample_quote: MarketQuoteSnapshot,
		another_tenant_id: UUID,
	):
		"""Тест получения записи - запись принадлежит другому tenant"""
		result = await repo.get_by_id(another_tenant_id, sample_quote.ticker_id)

		assert result is None

	@pytest.mark.asyncio
	async def test_get_all_for_tenant(
		self,
		repo: TenantAwareRepository,
		session: AsyncSession,
		ticker: Ticker,
		tenant_id: UUID,
		sample_exchange: Exchange,
		another_tenant_id: UUID,
	):
		"""Тест получения всех записей для tenant"""
		tickers = []
		for i in range(3):
			ticker = Ticker(
				symbol=f"TEST{i}",
				asset_type="stock",
				exchange_id=sample_exchange.id,
				base_currency="USD",
				quote_currency="USD",
				is_active=True,
			)
			session.add(ticker)
			tickers.append(ticker)

		await session.commit()

		for i, ticker in enumerate(tickers):
			quote = MarketQuoteSnapshot(
				ticker_id=ticker.id,
				price=Decimal("100") + Decimal(i),
				change_percent=Decimal("1.5"),
				volume=Decimal("1000000"),
				updated_at=datetime.now(timezone.utc),
			)
			await repo.create(tenant_id, quote)

		ticker_other = Ticker(
			symbol="OTHER",
			asset_type="stock",
			exchange_id=sample_exchange.id,
			base_currency="USD",
			quote_currency="USD",
			is_active=True,
		)
		session.add(ticker_other)
		await session.commit()

		quote_other = MarketQuoteSnapshot(
			ticker_id=ticker_other.id,
			price=Decimal("200"),
			change_percent=Decimal("3.0"),
			volume=Decimal("2000000"),
			updated_at=datetime.now(timezone.utc),
		)
		await repo.create(another_tenant_id, quote_other)

		result = await repo.get_all(tenant_id)

		assert len(result) == 3
		assert all(q.tenant_id == tenant_id for q in result)

	@pytest.mark.asyncio
	async def test_get_all_with_filters(
		self,
		repo: TenantAwareRepository,
		session: AsyncSession,
		ticker: Ticker,
		sample_exchange: Exchange,
		tenant_id: UUID,
	):
		"""Тест получения записей с фильтрами по tenant"""
		# Создаем записи с разными ценами
		ticker_2 = Ticker(
			symbol="TEST2",
			asset_type="stock",
			exchange_id=sample_exchange.id,
			base_currency="USD",
			quote_currency="USD",
			is_active=True,
		)
		session.add(ticker_2)
		await session.commit()
		quote1 = MarketQuoteSnapshot(
			ticker_id=ticker.id,
			price=Decimal("100.50"),
			change_percent=Decimal("1.5"),
			volume=Decimal("1000000"),
			updated_at=datetime.now(timezone.utc),
		)
		quote2 = MarketQuoteSnapshot(
			ticker_id=ticker_2.id,
			price=Decimal("200.75"),
			change_percent=Decimal("2.5"),
			volume=Decimal("2000000"),
			updated_at=datetime.now(timezone.utc),
		)
		await repo.create(tenant_id, quote1)
		await repo.create(tenant_id, quote2)

		# Фильтруем по цене
		result = await repo.get_all(tenant_id, price=Decimal("200.75"))

		assert len(result) == 1
		assert result[0].price == Decimal("200.75")

	@pytest.mark.asyncio
	async def test_get_all_with_pagination(
		self,
		repo: TenantAwareRepository,
		tenant_id: UUID,
		sample_exchange: Exchange,
		session: AsyncSession,
	):
		"""Тест пагинации для tenant-aware репозитория"""

		tickers = []
		for i in range(5):
			ticker = Ticker(
				symbol=f"TEST{i}",
				asset_type="stock",
				exchange_id=sample_exchange.id,
				base_currency="USD",
				quote_currency="USD",
				is_active=True,
			)
			session.add(ticker)
			tickers.append(ticker)

		await session.commit()

		for i, ticker in enumerate(tickers):
			quote = MarketQuoteSnapshot(
				ticker_id=ticker.id,
				price=Decimal("100") + Decimal(i),
				change_percent=Decimal("1.5"),
				volume=Decimal("1000000"),
				updated_at=datetime.now(timezone.utc),
			)
			await repo.create(tenant_id, quote)

		result_page1 = await repo.get_all(tenant_id, skip=0, limit=2)
		assert len(result_page1) == 2

		result_page2 = await repo.get_all(tenant_id, skip=2, limit=2)
		assert len(result_page2) == 2

		result_page3 = await repo.get_all(tenant_id, skip=4, limit=2)
		assert len(result_page3) == 1

	@pytest.mark.asyncio
	async def test_create_from_dict(
		self, repo: TenantAwareRepository, ticker: Ticker, tenant_id: UUID
	):
		"""Тест создания записи из словаря с tenant_id"""
		quote_data = {
			"ticker_id": ticker.id,
			"price": Decimal("150.50"),
			"change_percent": Decimal("2.5"),
			"volume": Decimal("1000000"),
			"updated_at": datetime.now(timezone.utc),
		}

		result = await repo.create(tenant_id, quote_data)

		assert result is not None
		assert result.ticker_id == ticker.id
		assert result.tenant_id == tenant_id
		assert result.price == Decimal("150.50")

	@pytest.mark.asyncio
	async def test_create_from_object(
		self, repo: TenantAwareRepository, ticker: Ticker, tenant_id: UUID
	):
		"""Тест создания записи из объекта с tenant_id"""
		quote = MarketQuoteSnapshot(
			ticker_id=ticker.id,
			price=Decimal("150.50"),
			change_percent=Decimal("2.5"),
			volume=Decimal("1000000"),
			updated_at=datetime.now(timezone.utc),
		)

		result = await repo.create(tenant_id, quote)

		assert result is not None
		assert result.ticker_id == ticker.id
		assert result.tenant_id == tenant_id

	@pytest.mark.asyncio
	async def test_create_should_override_tenant_id(
		self,
		repo: TenantAwareRepository,
		ticker: Ticker,
		tenant_id: UUID,
		another_tenant_id: UUID,
	):
		"""Тест: tenant_id в объекте переопределяется переданным"""
		quote = MarketQuoteSnapshot(
			ticker_id=ticker.id,
			tenant_id=another_tenant_id,
			price=Decimal("150.50"),
			change_percent=Decimal("2.5"),
			volume=Decimal("1000000"),
			updated_at=datetime.now(timezone.utc),
		)

		result = await repo.create(tenant_id, quote)

		# tenant_id должен быть переопределен
		assert result.tenant_id == tenant_id
		assert result.tenant_id != another_tenant_id

	@pytest.mark.asyncio
	async def test_delete_found(
		self,
		repo: TenantAwareRepository,
		session: AsyncSession,
		sample_quote: MarketQuoteSnapshot,
		tenant_id: UUID,
	):
		"""Тест удаления существующей записи"""
		quote_id = sample_quote.ticker_id

		result = await repo.delete(tenant_id, quote_id)

		assert result is True

		# Проверяем, что запись удалена
		db_result = await session.get(MarketQuoteSnapshot, quote_id)
		assert db_result is None

	@pytest.mark.asyncio
	async def test_delete_not_found(self, repo: TenantAwareRepository, tenant_id: UUID):
		"""Тест удаления несуществующей записи"""
		non_existent_id = uuid7()
		result = await repo.delete(tenant_id, non_existent_id)

		assert result is False

	@pytest.mark.asyncio
	async def test_delete_wrong_tenant(
		self,
		repo: TenantAwareRepository,
		sample_quote: MarketQuoteSnapshot,
		another_tenant_id: UUID,
	):
		"""Тест удаления записи, принадлежащей другому tenant"""
		result = await repo.delete(another_tenant_id, sample_quote.ticker_id)

		assert result is False

		db_result = await repo.get_by_id(another_tenant_id, sample_quote.ticker_id)
		assert db_result is None

	async def test_get_by_id_raises_error_if_no_id_column(self, session: AsyncSession):
		"""Тест: ошибка, если у модели нет поля id"""
		repo = TenantAwareRepository(session, TestModelWithoutId)

		with pytest.raises(AttributeError) as exc_info:
			await repo.get_by_id(tenant_id=uuid7(), id=uuid7())

		# Проверяем сообщение ошибки
		error_message = str(exc_info.value)
		assert "must have an 'id' column" in error_message
		assert "TestModelWithoutId" in error_message


class TestRepositoryIntegration:
	"""Интеграционные тесты для репозиториев"""

	@pytest.mark.asyncio
	async def test_tenant_isolation(
		self, session: AsyncSession, ticker: Ticker, sample_ticker: Ticker
	):
		"""Тест изоляции tenant'ов"""
		tenant1 = uuid7()
		tenant2 = uuid7()

		repo = TenantAwareRepository(session, MarketQuoteSnapshot)

		quote1 = MarketQuoteSnapshot(
			ticker_id=ticker.id,
			price=Decimal("100"),
			change_percent=Decimal("1.0"),
			volume=Decimal("1000"),
			updated_at=datetime.now(timezone.utc),
		)
		quote2 = MarketQuoteSnapshot(
			ticker_id=sample_ticker.id,
			price=Decimal("200"),
			change_percent=Decimal("2.0"),
			volume=Decimal("2000"),
			updated_at=datetime.now(timezone.utc),
		)

		await repo.create(tenant1, quote1)
		await repo.create(tenant2, quote2)

		result1 = await repo.get_all(tenant1)
		result2 = await repo.get_all(tenant2)

		assert len(result1) == 1
		assert len(result2) == 1
		assert result1[0].tenant_id == tenant1
		assert result2[0].tenant_id == tenant2
		assert result1[0].ticker_id != result2[0].ticker_id
