import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from swingtraderai.db.models.analysis import Analysis, Signal
from swingtraderai.db.models.market import Exchange, Ticker
from swingtraderai.db.models.system import Notification, Watchlist, WatchlistItem
from swingtraderai.db.models.user import User


@pytest.mark.asyncio
async def test_notification_creation_and_defaults(
	session: AsyncSession, sample_exchange: Exchange
):
	"""Проверка создания Notification + дефолтные значения"""
	ticker = Ticker(
		symbol="TEST",
		asset_type="crypto",
		exchange_id=sample_exchange.id,
		base_currency="TEST",
		quote_currency="USD",
		is_active=True,
	)
	session.add(ticker)
	await session.commit()
	await session.refresh(ticker)

	analysis = Analysis(ticker_id=ticker.id, timeframe="1h")
	session.add(analysis)
	await session.commit()
	await session.refresh(analysis)

	signal = Signal(
		analysis_id=analysis.id, ticker_id=ticker.id, signal_type="LONG", status="new"
	)
	session.add(signal)
	await session.commit()
	await session.refresh(signal)

	notification = Notification(
		signal_id=signal.id, channel="telegram", sent_to="@TraderIvan", status="sent"
	)

	session.add(notification)
	await session.commit()
	await session.refresh(notification)

	assert isinstance(notification.id, uuid.UUID)
	assert notification.signal_id == signal.id
	assert notification.channel == "telegram"
	assert notification.sent_to == "@TraderIvan"
	assert notification.status == "sent"

	assert isinstance(notification.created_at, datetime)
	assert notification.created_at.tzinfo == timezone.utc


@pytest.mark.asyncio
async def test_notification_minimal_creation(
	session: AsyncSession, sample_exchange: Exchange
):
	"""Минимальное уведомление — проверка nullable полей"""
	ticker = Ticker(
		symbol="TEST",
		asset_type="crypto",
		exchange_id=sample_exchange.id,
		base_currency="TEST",
		quote_currency="USD",
		is_active=True,
	)
	session.add(ticker)
	await session.commit()
	await session.refresh(ticker)

	analysis = Analysis(ticker_id=ticker.id)
	session.add(analysis)
	await session.commit()
	await session.refresh(analysis)

	signal = Signal(analysis_id=analysis.id, ticker_id=ticker.id, signal_type="HOLD")
	session.add(signal)
	await session.commit()
	await session.refresh(signal)

	notif = Notification(signal_id=signal.id)
	session.add(notif)
	await session.commit()
	await session.refresh(notif)

	assert notif.channel is None
	assert notif.sent_to is None
	assert notif.status is None


@pytest.mark.asyncio
async def test_foreign_key_violation_notification(session: AsyncSession):
	"""Попытка создать Notification с несуществующим signal_id"""
	fake_signal_id = uuid.uuid4()

	notification = Notification(
		signal_id=fake_signal_id, channel="email", status="failed"
	)
	session.add(notification)

	with pytest.raises(IntegrityError):
		await session.commit()


@pytest.mark.asyncio
async def test_watchlist_and_items_cascade(
	session: AsyncSession, sample_exchange: Exchange
):
	"""Тест каскадного удаления + загрузки relationship"""
	user = User(
		username="watchlist_user2",
		email="watchlist2@example.com",
		password_hash="hash456",
	)
	session.add(user)
	await session.commit()
	await session.refresh(user)

	t1 = Ticker(
		symbol="BTCUSDT",
		asset_type="crypto",
		exchange_id=sample_exchange.id,
		base_currency="BTC",
		quote_currency="USDT",
		is_active=True,
	)

	t2 = Ticker(
		symbol="ETHUSDT",
		asset_type="crypto",
		exchange_id=sample_exchange.id,
		base_currency="ETH",
		quote_currency="USDT",
		is_active=True,
	)
	session.add_all([t1, t2])
	await session.flush()

	watchlist = Watchlist(name="My Watchlist", owner_id=user.id)
	session.add(watchlist)
	await session.flush()

	item1 = WatchlistItem(watchlist_id=watchlist.id, ticker_id=t1.id)
	item2 = WatchlistItem(watchlist_id=watchlist.id, ticker_id=t2.id)
	session.add_all([item1, item2])
	await session.commit()

	stmt = (
		select(Watchlist)
		.options(selectinload(Watchlist.items))
		.where(Watchlist.id == watchlist.id)
	)
	result = await session.execute(stmt)
	loaded_watchlist = result.scalar_one()

	assert len(loaded_watchlist.items) == 2, (
		f"Expected 2 items, got {len(loaded_watchlist.items)}"
	)

	# === Проверка cascade delete ===
	await session.delete(loaded_watchlist)
	await session.commit()

	# Проверяем, что items удалились
	remaining_items = await session.execute(select(WatchlistItem))
	assert len(remaining_items.scalars().all()) == 0


@pytest.mark.asyncio
async def test_watchlist_item_relationship(
	session: AsyncSession, sample_exchange: Exchange
):
	"""Проверка двусторонней связи"""
	user = User(
		username="watchlist_user",
		email="wl@example.com",
		password_hash="hash123",
	)
	session.add(user)
	await session.commit()
	await session.refresh(user)

	ticker = Ticker(
		symbol="SOLUSDT",
		asset_type="crypto",
		exchange_id=sample_exchange.id,
		base_currency="SOL",
		quote_currency="USDT",
		is_active=True,
	)
	session.add(ticker)
	await session.flush()

	watchlist = Watchlist(name="Test WL", owner_id=user.id)
	session.add(watchlist)
	await session.flush()

	item = WatchlistItem(watchlist_id=watchlist.id, ticker_id=ticker.id)
	session.add(item)
	await session.commit()
	await session.refresh(item)

	assert item.watchlist_id == watchlist.id
	assert item.ticker_id == ticker.id

	assert item.watchlist is not None
	assert item.watchlist.id == watchlist.id

	assert item.ticker is not None
	assert item.ticker.symbol == "SOLUSDT"

	stmt = (
		select(Watchlist)
		.options(selectinload(Watchlist.items))
		.where(Watchlist.id == watchlist.id)
	)
	result = await session.execute(stmt)
	reloaded = result.scalar_one()

	assert len(reloaded.items) == 1
	assert reloaded.items[0].id == item.id


@pytest.mark.asyncio
async def test_watchlist_item_unique_per_watchlist_not_enforced(
	session: AsyncSession,
	sample_exchange: Exchange,
):
	user = User(
		username="dup_user",
		email="dup@example.com",
		password_hash="hash",
	)
	session.add(user)
	await session.commit()
	await session.refresh(user)

	ticker = Ticker(
		symbol="XLMUSDT",
		asset_type="crypto",
		exchange_id=sample_exchange.id,
		base_currency="XLM",
		quote_currency="USDT",
		is_active=True,
	)
	session.add(ticker)
	await session.flush()

	watchlist = Watchlist(name="Duplicates Test", owner_id=user.id)
	session.add(watchlist)
	await session.flush()

	item1 = WatchlistItem(watchlist_id=watchlist.id, ticker_id=ticker.id)
	item2 = WatchlistItem(watchlist_id=watchlist.id, ticker_id=ticker.id)

	session.add_all([item1, item2])
	await session.commit()

	stmt = (
		select(Watchlist)
		.options(selectinload(Watchlist.items))
		.where(Watchlist.id == watchlist.id)
	)
	result = await session.execute(stmt)
	reloaded = result.scalar_one()

	assert len(reloaded.items) == 2
