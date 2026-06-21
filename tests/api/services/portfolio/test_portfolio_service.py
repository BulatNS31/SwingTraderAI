from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from uuid6 import uuid7

from swingtraderai.api.services.portfolio.portfolio_service import PortfolioService
from swingtraderai.db.models.market import Ticker
from swingtraderai.schemas.portfolio import PortfolioCreate, PortfolioUpdate
from swingtraderai.schemas.portfolio_transaction import PortfolioTransactionCreate


class TestPortfolioService:
	"""Тесты для PortfolioService"""

	@pytest.fixture
	async def portfolio_service(self, session):
		return PortfolioService(session)

	@pytest.fixture
	async def ticker_btc(self, session):
		ticker = Ticker(
			symbol="BTCUSDT",
			asset_type="crypto",
			exchange_id=None,
			base_currency="BTC",
			quote_currency="USD",
			is_active=True,
		)
		session.add(ticker)
		await session.flush()
		await session.refresh(ticker)
		return ticker

	async def test_create_portfolio_success(self, portfolio_service, user):
		"""Тест: успешное создание портфеля"""
		portfolio_in = PortfolioCreate(
			name="My Portfolio",
			description="Test description",
		)

		result = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		assert result is not None
		assert result.name == "My Portfolio"
		assert result.description == "Test description"
		assert result.user_id == user.id
		assert result.tenant_id == user.tenant_id

	async def test_create_portfolio_without_description(self, portfolio_service, user):
		"""Тест: создание портфеля без описания"""
		portfolio_in = PortfolioCreate(name="My Portfolio")

		result = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		assert result is not None
		assert result.name == "My Portfolio"
		assert result.description is None

	async def test_get_portfolio_success(self, portfolio_service, user):
		"""Тест: успешное получение портфеля"""
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		result = await portfolio_service.get_portfolio(
			tenant_id=user.tenant_id, portfolio_id=portfolio.id
		)

		assert result is not None
		assert result.id == portfolio.id
		assert result.name == "My Portfolio"

	async def test_get_portfolio_not_found(self, portfolio_service, user):
		"""Тест: ошибка при получении несуществующего портфеля"""
		non_existent_id = uuid7()

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.get_portfolio(
				tenant_id=user.tenant_id, portfolio_id=non_existent_id
			)

		assert exc.value.status_code == 404
		assert "Portfolio not found" in str(exc.value.detail)

	async def test_list_portfolios_empty(self, portfolio_service, user):
		"""Тест: список портфелей пуст"""
		result = await portfolio_service.list_portfolios(
			tenant_id=user.tenant_id, user_id=user.id
		)

		assert result == []

	async def test_list_portfolios_with_items(self, portfolio_service, user):
		"""Тест: список портфелей с элементами"""
		for i in range(3):
			portfolio_in = PortfolioCreate(name=f"Portfolio {i + 1}")
			await portfolio_service.create_portfolio(
				tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
			)

		result = await portfolio_service.list_portfolios(
			tenant_id=user.tenant_id, user_id=user.id
		)

		assert len(result) == 3
		assert all(p.user_id == user.id for p in result)

	async def test_list_portfolios_with_pagination(self, portfolio_service, user):
		"""Тест: пагинация списка портфелей"""
		for i in range(5):
			portfolio_in = PortfolioCreate(name=f"Portfolio {i + 1}")
			await portfolio_service.create_portfolio(
				tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
			)

		result_page1 = await portfolio_service.list_portfolios(
			tenant_id=user.tenant_id, user_id=user.id, skip=0, limit=2
		)
		assert len(result_page1) == 2

		result_page2 = await portfolio_service.list_portfolios(
			tenant_id=user.tenant_id, user_id=user.id, skip=2, limit=2
		)
		assert len(result_page2) == 2

		result_page3 = await portfolio_service.list_portfolios(
			tenant_id=user.tenant_id, user_id=user.id, skip=4, limit=2
		)
		assert len(result_page3) == 1

	async def test_update_portfolio_success(self, portfolio_service, user):
		"""Тест: успешное обновление портфеля"""
		portfolio_in = PortfolioCreate(name="Old Name")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		update_data = PortfolioUpdate(name="New Name", description="New Description")

		result = await portfolio_service.update_portfolio(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			portfolio_update=update_data,
		)

		assert result.name == "New Name"
		assert result.description == "New Description"

	async def test_update_portfolio_partial(self, portfolio_service, user):
		"""Тест: частичное обновление портфеля"""
		portfolio_in = PortfolioCreate(
			name="My Portfolio", description="Old Description"
		)
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		update_data = PortfolioUpdate(name="Updated Name")

		result = await portfolio_service.update_portfolio(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			portfolio_update=update_data,
		)

		assert result.name == "Updated Name"
		assert result.description == "Old Description"

	async def test_update_portfolio_not_found(self, portfolio_service, user):
		"""Тест: ошибка при обновлении несуществующего портфеля"""
		non_existent_id = uuid7()
		update_data = PortfolioUpdate(name="New Name")

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.update_portfolio(
				tenant_id=user.tenant_id,
				user_id=user.id,
				portfolio_id=non_existent_id,
				portfolio_update=update_data,
			)

		assert exc.value.status_code == 404
		assert "Portfolio not found" in str(exc.value.detail)

	async def test_update_portfolio_wrong_user(
		self, portfolio_service, user, other_user
	):
		"""Тест: ошибка при обновлении портфеля другого пользователя"""
		# Создаем портфель для первого пользователя
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		update_data = PortfolioUpdate(name="Hacked")

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.update_portfolio(
				tenant_id=user.tenant_id,
				user_id=other_user.id,
				portfolio_id=portfolio.id,
				portfolio_update=update_data,
			)

		assert exc.value.status_code == 403
		assert "Forbidden" in str(exc.value.detail)

	async def test_delete_portfolio_success(self, portfolio_service, user):
		"""Тест: успешное удаление портфеля"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="To Delete")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Удаляем портфель
		result = await portfolio_service.delete_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_id=portfolio.id
		)

		assert result is True

		# Проверяем, что портфель удален
		with pytest.raises(HTTPException) as exc:
			await portfolio_service.get_portfolio(
				tenant_id=user.tenant_id, portfolio_id=portfolio.id
			)
		assert exc.value.status_code == 404

	async def test_delete_portfolio_not_found(self, portfolio_service, user):
		"""Тест: ошибка при удалении несуществующего портфеля"""
		non_existent_id = uuid7()

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.delete_portfolio(
				tenant_id=user.tenant_id, user_id=user.id, portfolio_id=non_existent_id
			)

		assert exc.value.status_code == 404
		assert "Portfolio not found" in str(exc.value.detail)

	async def test_delete_portfolio_wrong_user(
		self, portfolio_service, user, other_user
	):
		"""Тест: ошибка при удалении портфеля другого пользователя"""
		# Создаем портфель для первого пользователя
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Пытается удалить второй пользователь
		with pytest.raises(HTTPException) as exc:
			await portfolio_service.delete_portfolio(
				tenant_id=user.tenant_id,
				user_id=other_user.id,
				portfolio_id=portfolio.id,
			)

		assert exc.value.status_code == 403
		assert "Forbidden" in str(exc.value.detail)

	async def test_add_transaction_buy(self, portfolio_service, user, ticker):
		"""Тест: добавление BUY транзакции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Добавляем BUY транзакцию
		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		transaction = await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=transaction_in,
		)

		assert transaction is not None
		assert transaction.side == "BUY"
		assert transaction.quantity == Decimal("10")
		assert transaction.price == Decimal("100.00")
		assert transaction.portfolio_id == portfolio.id
		assert transaction.ticker_id == ticker.id

		# Проверяем, что позиция создалась
		position = await portfolio_service.position_repo.get_active_by_ticker(
			tenant_id=user.tenant_id,
			user_id=user.id,
			ticker_id=ticker.id,
			position_type="long",
		)
		assert position is not None
		assert position.quantity == Decimal("10")
		assert position.average_buy_price == Decimal("100.00")
		assert position.total_cost == Decimal("1000.00")

	async def test_add_transaction_sell(self, portfolio_service, user, ticker):
		"""Тест: добавление SELL транзакции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Сначала BUY
		buy_transaction = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=buy_transaction,
		)

		# Затем SELL
		sell_transaction = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="SELL",
			quantity=Decimal("5"),
			price=Decimal("120.00"),
		)

		transaction = await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=sell_transaction,
		)

		assert transaction is not None
		assert transaction.side == "SELL"
		assert transaction.quantity == Decimal("5")
		assert transaction.price == Decimal("120.00")

		position = await portfolio_service.position_repo.get_active_by_ticker(
			tenant_id=user.tenant_id,
			user_id=user.id,
			ticker_id=ticker.id,
			position_type="long",
		)
		assert position is not None
		assert position.quantity == Decimal("5")
		assert position.average_buy_price == Decimal("100.00")
		assert position.total_cost == Decimal("500.00")

	async def test_add_transaction_portfolio_not_found(
		self, portfolio_service, user, ticker
	):
		"""Тест: ошибка при добавлении транзакции в несуществующий портфель"""
		non_existent_id = uuid7()
		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.add_transaction(
				tenant_id=user.tenant_id,
				user_id=user.id,
				portfolio_id=non_existent_id,
				transaction_in=transaction_in,
			)

		assert exc.value.status_code == 404
		assert "Portfolio not found" in str(exc.value.detail)

	async def test_add_transaction_wrong_user(
		self, portfolio_service, user, other_user, ticker
	):
		"""Тест: ошибка при добавлении транзакции в портфель другого пользователя"""
		# Создаем портфель для первого пользователя
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Второй пользователь пытается добавить транзакцию
		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.add_transaction(
				tenant_id=user.tenant_id,
				user_id=other_user.id,
				portfolio_id=portfolio.id,
				transaction_in=transaction_in,
			)

		assert exc.value.status_code == 403
		assert "Forbidden" in str(exc.value.detail)

	async def test_add_transaction_ticker_not_found(self, portfolio_service, user):
		"""Тест: ошибка при добавлении транзакции с несуществующим тикером"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		non_existent_ticker_id = uuid7()
		transaction_in = PortfolioTransactionCreate(
			ticker_id=non_existent_ticker_id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.add_transaction(
				tenant_id=user.tenant_id,
				user_id=user.id,
				portfolio_id=portfolio.id,
				transaction_in=transaction_in,
			)

		assert exc.value.status_code == 404
		assert "Ticker not found" in str(exc.value.detail)

	async def test_add_transaction_sell_without_position(
		self, portfolio_service, user, ticker
	):
		"""Тест: ошибка при продаже без активной позиции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="SELL",
			quantity=Decimal("5"),
			price=Decimal("120.00"),
		)

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.add_transaction(
				tenant_id=user.tenant_id,
				user_id=user.id,
				portfolio_id=portfolio.id,
				transaction_in=transaction_in,
			)

		assert exc.value.status_code == 400
		assert "No active position to sell" in str(exc.value.detail)

	async def test_add_transaction_sell_exceeds_position(
		self, portfolio_service, user, ticker
	):
		"""Тест: ошибка при продаже больше, чем есть в позиции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# BUY 10
		buy_transaction = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=buy_transaction,
		)

		# SELL 15 (больше чем есть)
		sell_transaction = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="SELL",
			quantity=Decimal("15"),
			price=Decimal("120.00"),
		)

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.add_transaction(
				tenant_id=user.tenant_id,
				user_id=user.id,
				portfolio_id=portfolio.id,
				transaction_in=sell_transaction,
			)

		assert exc.value.status_code == 400
		assert "Sell quantity exceeds active position" in str(exc.value.detail)

	async def test_add_transaction_with_custom_executed_at(
		self, portfolio_service, user, ticker
	):
		"""Тест: добавление транзакции с кастомной датой выполнения"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		custom_date = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
			executed_at=custom_date,
		)

		transaction = await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=transaction_in,
		)

		assert transaction.executed_at == custom_date

	async def test_add_transaction_with_auto_executed_at(
		self, portfolio_service, user, ticker
	):
		"""Тест: автоматическая установка даты выполнения транзакции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		transaction = await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=transaction_in,
		)

		assert transaction.executed_at is not None
		assert transaction.executed_at.tzinfo == timezone.utc

	async def test_close_position_success(self, portfolio_service, user, ticker):
		"""Тест: успешное закрытие позиции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Создаем позицию
		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=transaction_in,
		)

		# Получаем позицию
		position = await portfolio_service.position_repo.get_active_by_ticker(
			tenant_id=user.tenant_id,
			user_id=user.id,
			ticker_id=ticker.id,
			position_type="long",
		)

		# Закрываем позицию
		result = await portfolio_service.close_position(
			tenant_id=user.tenant_id, position_id=position.id
		)

		assert result is True

		closed_position = await portfolio_service.position_repo.get_by_id(
			tenant_id=user.tenant_id, id=position.id
		)
		assert closed_position.closed_at is not None

	async def test_close_position_not_found(self, portfolio_service, user):
		"""Тест: ошибка при закрытии несуществующей позиции"""
		non_existent_id = uuid7()

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.close_position(
				tenant_id=user.tenant_id, position_id=non_existent_id
			)

		assert exc.value.status_code == 404
		assert "Position not found" in str(exc.value.detail)

	async def test_close_position_already_closed(self, portfolio_service, user, ticker):
		"""Тест: попытка закрыть уже закрытую позицию"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Создаем позицию
		transaction_in = PortfolioTransactionCreate(
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=transaction_in,
		)

		# Получаем позицию
		position = await portfolio_service.position_repo.get_active_by_ticker(
			tenant_id=user.tenant_id,
			user_id=user.id,
			ticker_id=ticker.id,
			position_type="long",
		)

		# Закрываем позицию
		await portfolio_service.close_position(
			tenant_id=user.tenant_id, position_id=position.id
		)

		# Пытаемся закрыть снова
		result = await portfolio_service.close_position(
			tenant_id=user.tenant_id, position_id=position.id
		)

		assert result is False

	async def test_recalculate_position_buy_new(self, portfolio_service, user, ticker):
		"""Тест: создание новой позиции при BUY"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		position = await portfolio_service.recalculate_position(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		assert position is not None
		assert position.quantity == Decimal("10")
		assert position.average_buy_price == Decimal("100.00")
		assert position.total_cost == Decimal("1000.00")
		assert position.position_type == "long"

	async def test_recalculate_position_buy_existing(
		self, portfolio_service, user, ticker
	):
		"""Тест: обновление существующей позиции при BUY"""
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		await portfolio_service.recalculate_position(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		position = await portfolio_service.recalculate_position(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("5"),
			price=Decimal("120.00"),
		)

		assert position is not None
		assert position.quantity == Decimal("15")
		# Средняя цена: (10*100 + 5*120) / 15 = (1000 + 600) / 15 = 106.67
		expected_avg = (Decimal("1000.00") + Decimal("600.00")) / Decimal("15")
		assert float(position.average_buy_price) == pytest.approx(
			float(expected_avg), rel=1e-5
		)
		assert position.total_cost == Decimal("1600.00")

	async def test_recalculate_position_sell_partial(
		self, portfolio_service, user, ticker
	):
		"""Тест: частичная продажа позиции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# BUY
		await portfolio_service.recalculate_position(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		# SELL partial
		position = await portfolio_service.recalculate_position(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			ticker_id=ticker.id,
			side="SELL",
			quantity=Decimal("3"),
			price=Decimal("120.00"),
		)

		assert position is not None
		assert position.quantity == Decimal("7")
		assert position.average_buy_price == Decimal("100.00")  # Не меняется
		assert position.total_cost == Decimal("700.00")
		assert position.closed_at is None

	async def test_recalculate_position_sell_full(
		self, portfolio_service, user, ticker
	):
		"""Тест: полная продажа позиции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# BUY
		await portfolio_service.recalculate_position(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			ticker_id=ticker.id,
			side="BUY",
			quantity=Decimal("10"),
			price=Decimal("100.00"),
		)

		# SELL all
		position = await portfolio_service.recalculate_position(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			ticker_id=ticker.id,
			side="SELL",
			quantity=Decimal("10"),
			price=Decimal("120.00"),
		)

		assert position is not None
		assert position.quantity == Decimal("0")
		assert position.closed_at is not None

	async def test_recalculate_position_invalid_side(
		self, portfolio_service, user, ticker
	):
		"""Тест: ошибка при невалидной стороне транзакции"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		with pytest.raises(HTTPException) as exc:
			await portfolio_service.recalculate_position(
				tenant_id=user.tenant_id,
				user_id=user.id,
				portfolio_id=portfolio.id,
				ticker_id=ticker.id,
				side="INVALID",
				quantity=Decimal("10"),
				price=Decimal("100.00"),
			)

		assert exc.value.status_code == 400
		assert "Invalid transaction side" in str(exc.value.detail)

	async def test_multiple_transactions_complex_scenario(
		self, portfolio_service, user, ticker, ticker_btc
	):
		"""Тест: сложный сценарий с несколькими транзакциями"""
		# Создаем портфель
		portfolio_in = PortfolioCreate(name="My Portfolio")
		portfolio = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# BUY AAPL 10 @ 100
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=PortfolioTransactionCreate(
				ticker_id=ticker.id,
				side="BUY",
				quantity=Decimal("10"),
				price=Decimal("100.00"),
			),
		)

		# BUY AAPL 5 @ 120
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=PortfolioTransactionCreate(
				ticker_id=ticker.id,
				side="BUY",
				quantity=Decimal("5"),
				price=Decimal("120.00"),
			),
		)

		# BUY BTC 0.5 @ 50000
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=PortfolioTransactionCreate(
				ticker_id=ticker_btc.id,
				side="BUY",
				quantity=Decimal("0.5"),
				price=Decimal("50000.00"),
			),
		)

		# SELL AAPL 7 @ 130
		await portfolio_service.add_transaction(
			tenant_id=user.tenant_id,
			user_id=user.id,
			portfolio_id=portfolio.id,
			transaction_in=PortfolioTransactionCreate(
				ticker_id=ticker.id,
				side="SELL",
				quantity=Decimal("7"),
				price=Decimal("130.00"),
			),
		)

		# Проверяем позицию AAPL
		aapl_position = await portfolio_service.position_repo.get_active_by_ticker(
			tenant_id=user.tenant_id,
			user_id=user.id,
			ticker_id=ticker.id,
			position_type="long",
		)
		assert aapl_position is not None
		assert aapl_position.quantity == Decimal("8")  # 10 + 5 - 7 = 8
		expected_avg = (Decimal("1000.00") + Decimal("600.00")) / Decimal("15")
		assert float(aapl_position.average_buy_price) == pytest.approx(
			float(expected_avg), rel=1e-5
		)
		expected_total_cost = Decimal("8") * expected_avg
		assert float(aapl_position.total_cost) == pytest.approx(
			float(expected_total_cost), rel=1e-5
		)

		# Проверяем позицию BTC
		btc_position = await portfolio_service.position_repo.get_active_by_ticker(
			tenant_id=user.tenant_id,
			user_id=user.id,
			ticker_id=ticker_btc.id,
			position_type="long",
		)
		assert btc_position is not None
		assert btc_position.quantity == Decimal("0.5")
		assert btc_position.average_buy_price == Decimal("50000.00")

	async def test_tenant_isolation(self, portfolio_service, user, other_user):
		"""Тест: изоляция по tenant_id"""
		# Создаем портфель для первого пользователя
		portfolio_in = PortfolioCreate(name="User1 Portfolio")
		portfolio1 = await portfolio_service.create_portfolio(
			tenant_id=user.tenant_id, user_id=user.id, portfolio_in=portfolio_in
		)

		# Создаем портфель для второго пользователя
		portfolio_in2 = PortfolioCreate(name="User2 Portfolio")
		portfolio2 = await portfolio_service.create_portfolio(
			tenant_id=other_user.tenant_id,
			user_id=other_user.id,
			portfolio_in=portfolio_in2,
		)

		# Проверяем, что пользователь видит только свои портфели
		list1 = await portfolio_service.list_portfolios(
			tenant_id=user.tenant_id, user_id=user.id
		)
		assert len(list1) == 1
		assert list1[0].id == portfolio1.id

		list2 = await portfolio_service.list_portfolios(
			tenant_id=other_user.tenant_id, user_id=other_user.id
		)
		assert len(list2) == 1
		assert list2[0].id == portfolio2.id
