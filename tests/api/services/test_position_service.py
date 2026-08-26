from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid6 import uuid7

from swingtraderai.api.services.position_service import PositionService
from swingtraderai.db.models.market import Exchange, Ticker
from swingtraderai.schemas.user import PositionCreate, PositionUpdate


@pytest.fixture
async def position_service(session):
	return PositionService(session)


@pytest.fixture
async def ticker_aapl(session: AsyncSession, sample_exchange: Exchange):
	ticker = Ticker(
		symbol="AAPL",
		asset_type="stock",
		base_currency="USD",
		exchange_id=sample_exchange.id,
		quote_currency="USD",
		is_active=True,
	)
	session.add(ticker)
	await session.flush()
	await session.refresh(ticker)
	return ticker


@pytest.fixture
async def ticker_btc(session: AsyncSession, sample_exchange: Exchange):
	ticker = Ticker(
		symbol="BTCUSDT",
		asset_type="crypto",
		base_currency="BTC",
		quote_currency="USD",
		exchange_id=sample_exchange.id,
		is_active=True,
	)
	session.add(ticker)
	await session.flush()
	await session.refresh(ticker)
	return ticker


async def test_add_position_success(position_service, user, ticker_aapl):
	position_in = PositionCreate(
		ticker_id=ticker_aapl.id,
		position_type="long",
		quantity=Decimal("10.5"),
		average_entry_price=Decimal("215.75"),
		notes="Test position",
	)

	position = await position_service.add_position(
		tenant_id=user.tenant_id, user_id=user.id, position_in=position_in
	)

	assert position.id is not None
	assert position.tenant_id == user.tenant_id
	assert position.user_id == user.id
	assert position.ticker_id == ticker_aapl.id
	assert position.position_type == "long"
	assert position.quantity == Decimal("10.5")
	assert position.average_buy_price == Decimal("215.75")
	assert position.total_cost == Decimal("10.5") * Decimal("215.75")
	assert position.notes == "Test position"


async def test_add_position_ticker_not_found(position_service, user):
	position_in = PositionCreate(
		ticker_id=uuid7(),
		position_type="long",
		quantity=Decimal("1"),
		average_entry_price=Decimal("100"),
	)

	with pytest.raises(HTTPException) as exc:
		await position_service.add_position(user.tenant_id, user.id, position_in)
	assert exc.value.status_code == 404
	assert exc.value.detail == "Ticker not found"


async def test_add_position_already_exists(position_service, user, ticker_aapl):
	# Создаём первую позицию
	position_in = PositionCreate(
		ticker_id=ticker_aapl.id,
		position_type="long",
		quantity=Decimal("5"),
		average_entry_price=Decimal("200"),
	)
	await position_service.add_position(user.tenant_id, user.id, position_in)

	# Пытаемся создать вторую такую же
	with pytest.raises(HTTPException) as exc:
		await position_service.add_position(user.tenant_id, user.id, position_in)

	assert exc.value.status_code == 400
	assert "Active long position for this ticker already exists" in exc.value.detail


async def test_add_short_position_total_cost_negative(
	position_service, user, ticker_aapl
):
	position_in = PositionCreate(
		ticker_id=ticker_aapl.id,
		position_type="short",
		quantity=Decimal("8"),
		average_entry_price=Decimal("230"),
	)

	position = await position_service.add_position(user.tenant_id, user.id, position_in)

	assert position.total_cost < 0


async def test_get_user_positions(position_service, user, ticker_aapl, ticker_btc):
	positions_data = [
		{"ticker": ticker_aapl, "type": "long", "qty": Decimal("10")},
		{"ticker": ticker_btc, "type": "short", "qty": Decimal("0.5")},
	]

	for data in positions_data:
		pos_in = PositionCreate(
			ticker_id=data["ticker"].id,
			position_type=data["type"],
			quantity=data["qty"],
			average_entry_price=Decimal("100"),
		)
		await position_service.add_position(user.tenant_id, user.id, pos_in)

	positions = await position_service.get_user_positions(user.tenant_id, user.id)

	assert len(positions) == 2
	assert {p.position_type for p in positions} == {"long", "short"}


async def test_get_user_positions_only_closed(position_service, user, ticker_aapl):
	# Активная
	await position_service.add_position(
		user.tenant_id,
		user.id,
		PositionCreate(
			ticker_id=ticker_aapl.id,
			position_type="long",
			quantity=Decimal("5"),
			average_entry_price=Decimal("200"),
		),
	)

	positions = await position_service.get_user_positions(
		user.tenant_id, user.id, closed=True
	)
	assert len(positions) == 0


async def test_update_position_success(position_service, user, ticker_aapl):
	# Создаём позицию
	pos_in = PositionCreate(
		ticker_id=ticker_aapl.id,
		position_type="long",
		quantity=Decimal("10"),
		average_entry_price=Decimal("200"),
	)
	position = await position_service.add_position(user.tenant_id, user.id, pos_in)

	# Обновляем
	update_data = PositionUpdate(
		quantity=Decimal("15"), average_entry_price=Decimal("210"), notes="Updated note"
	)

	updated = await position_service.update_position(
		user.tenant_id, user.id, position.id, update_data
	)

	assert updated.quantity == Decimal("15")
	assert updated.average_buy_price == Decimal("210")
	assert updated.notes == "Updated note"
	assert updated.total_cost == Decimal("15") * Decimal("210")


async def test_update_position_not_found(position_service, user):
	with pytest.raises(HTTPException) as exc:
		await position_service.update_position(
			user.tenant_id, user.id, uuid7(), PositionUpdate()
		)
	assert exc.value.status_code == 404


async def test_update_position_forbidden(position_service, user, ticker_aapl):
	# Создаём позицию от первого пользователя
	pos = await position_service.add_position(
		user.tenant_id,
		user.id,
		PositionCreate(
			ticker_id=ticker_aapl.id,
			position_type="long",
			quantity=Decimal("1"),
			average_entry_price=Decimal("100"),
		),
	)

	other_user_id = uuid7()

	with pytest.raises(HTTPException) as exc:
		await position_service.update_position(
			user.tenant_id, other_user_id, pos.id, PositionUpdate(notes="hack")
		)
	assert exc.value.status_code == 403


async def test_update_closed_position_forbidden(position_service, user, ticker_aapl):
	pos_in = PositionCreate(
		ticker_id=ticker_aapl.id,
		position_type="long",
		quantity=Decimal("10"),
		average_entry_price=Decimal("200"),
	)
	position = await position_service.add_position(user.tenant_id, user.id, pos_in)

	# Закрываем позицию
	position.closed_at = datetime(2025, 5, 6, 0, 0, 0, tzinfo=timezone.utc)
	await position_service.repo.session.commit()

	with pytest.raises(HTTPException) as exc:
		await position_service.update_position(
			user.tenant_id, user.id, position.id, PositionUpdate(notes="try")
		)
	assert exc.value.status_code == 400
	assert "already closed" in exc.value.detail.lower()


async def test_delete_position_success(position_service, user, ticker_aapl):
	position = await position_service.add_position(
		user.tenant_id,
		user.id,
		PositionCreate(
			ticker_id=ticker_aapl.id,
			position_type="long",
			quantity=Decimal("5"),
			average_entry_price=Decimal("200"),
		),
	)

	deleted = await position_service.delete_position(
		user.tenant_id, user.id, position.id
	)
	assert deleted is True

	# Проверяем, что удалили
	positions = await position_service.get_user_positions(user.tenant_id, user.id)
	assert len(positions) == 0


async def test_delete_position_not_found(position_service, user):
	with pytest.raises(HTTPException) as exc:
		await position_service.delete_position(user.tenant_id, user.id, uuid7())
	assert exc.value.status_code == 404


async def test_delete_position_forbidden(position_service, user, ticker_aapl):
	position = await position_service.add_position(
		user.tenant_id,
		user.id,
		PositionCreate(
			ticker_id=ticker_aapl.id,
			position_type="long",
			quantity=Decimal("1"),
			average_entry_price=Decimal("100"),
		),
	)

	with pytest.raises(HTTPException) as exc:
		await position_service.delete_position(user.tenant_id, uuid7(), position.id)
	assert exc.value.status_code == 403


async def test_get_active_by_ticker(position_service, user, ticker_aapl):
	await position_service.add_position(
		user.tenant_id,
		user.id,
		PositionCreate(
			ticker_id=ticker_aapl.id,
			position_type="short",
			quantity=Decimal("2"),
			average_entry_price=Decimal("220"),
		),
	)

	position = await position_service.get_active_by_ticker(
		user.tenant_id, user.id, ticker_aapl.id, "short"
	)

	assert position is not None
	assert position.position_type == "short"
