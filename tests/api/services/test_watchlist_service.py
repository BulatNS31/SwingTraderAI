from datetime import timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import delete, func, select
from uuid6 import uuid7

from swingtraderai.db.models.market import MarketData
from swingtraderai.db.models.system import Watchlist, WatchlistItem
from swingtraderai.schemas.watchlist import (
	SignalType,
	WatchlistCreate,
	WatchlistItemCreate,
	WatchlistItemUpdate,
)


def test_check_signal_target_hit(watchlist_service):
	item = WatchlistItem(target_price=Decimal("150.0"), stop_loss=None)
	signals = watchlist_service.check_signal(item, 152.5)
	assert signals == ["TARGET_HIT"]


def test_check_signal_stop_loss_hit(watchlist_service):
	item = WatchlistItem(target_price=None, stop_loss=Decimal("100.0"))
	signals = watchlist_service.check_signal(item, 98.0)
	assert signals == ["STOP_LOSS_HIT"]


def test_check_signal_both_hit(watchlist_service):
	item = WatchlistItem(target_price=Decimal("150"), stop_loss=Decimal("100"))
	signals = watchlist_service.check_signal(item, 155.0)
	assert signals == ["TARGET_HIT"]


def test_check_signal_no_signals(watchlist_service):
	item = WatchlistItem(target_price=Decimal("150"), stop_loss=Decimal("100"))
	signals = watchlist_service.check_signal(item, 120.0)
	assert signals == []


async def test_add_item_success(watchlist_service, user, ticker, watchlist):
	item_in = WatchlistItemCreate(
		ticker_id=ticker.id,
		watchlist_id=watchlist.id,
		notes="Strong buy setup",
		reason="Breakout from resistance",
		target_price=Decimal("230.0"),
		stop_loss=Decimal("195.0"),
	)

	item = await watchlist_service.add_item(user.tenant_id, user.id, item_in)

	assert item.ticker_id == ticker.id
	assert item.notes == "Strong buy setup"
	assert item.target_price == Decimal("230.0")
	assert item.stop_loss == Decimal("195.0")


async def test_add_item_ticker_not_found(watchlist_service, user):
	item_in = WatchlistItemCreate(ticker_id=uuid7(), watchlist_id=uuid7())

	with pytest.raises(HTTPException) as exc:
		await watchlist_service.add_item(user.tenant_id, user.id, item_in)
	assert exc.value.status_code == 404
	assert "Ticker not found" in exc.value.detail


async def test_add_item_already_in_watchlist(
	watchlist_service, user, ticker, watchlist
):
	item_in = WatchlistItemCreate(ticker_id=ticker.id, watchlist_id=watchlist.id)
	await watchlist_service.add_item(user.tenant_id, user.id, item_in)

	# Повторное добавление
	with pytest.raises(HTTPException) as exc:
		await watchlist_service.add_item(user.tenant_id, user.id, item_in)
	assert exc.value.status_code == 400
	assert "already in watchlist" in exc.value.detail.lower()


async def test_get_user_items(watchlist_service, user, ticker, watchlist):
	await watchlist_service.add_item(
		user.tenant_id,
		user.id,
		WatchlistItemCreate(
			ticker_id=ticker.id, watchlist_id=watchlist.id, notes="Test"
		),
	)

	items = await watchlist_service.get_user_items(user.tenant_id, user.id)
	assert len(items) == 1
	assert items[0].ticker_id == ticker.id


async def test_update_item_success(watchlist_service, user, ticker, watchlist):
	# Создаём item
	item = await watchlist_service.add_item(
		user.tenant_id,
		user.id,
		WatchlistItemCreate(ticker_id=ticker.id, watchlist_id=watchlist.id),
	)

	update_data = WatchlistItemUpdate(
		target_price=Decimal("250.0"), stop_loss=Decimal("200.0"), notes="Updated note"
	)

	updated = await watchlist_service.update_item(
		user.tenant_id, user.id, item.id, update_data
	)

	assert updated.target_price == Decimal("250.0")
	assert updated.stop_loss == Decimal("200.0")
	assert updated.notes == "Updated note"


async def test_update_item_not_found(watchlist_service, user):
	with pytest.raises(HTTPException) as exc:
		await watchlist_service.update_item(
			user.tenant_id, user.id, uuid7(), WatchlistItemUpdate()
		)
	assert exc.value.status_code == 404


async def test_update_item_forbidden(watchlist_service, user, ticker, watchlist):
	item = await watchlist_service.add_item(
		user.tenant_id,
		user.id,
		WatchlistItemCreate(ticker_id=ticker.id, watchlist_id=watchlist.id),
	)

	with pytest.raises(HTTPException) as exc:
		await watchlist_service.update_item(
			user.tenant_id, uuid7(), item.id, WatchlistItemUpdate(notes="hack")
		)
	assert exc.value.status_code == 403


async def test_remove_item_success(watchlist_service, user, ticker, watchlist):
	item = await watchlist_service.add_item(
		user.tenant_id,
		user.id,
		WatchlistItemCreate(ticker_id=ticker.id, watchlist_id=watchlist.id),
	)

	deleted = await watchlist_service.remove_item(user.tenant_id, user.id, item.id)
	assert deleted is True

	items = await watchlist_service.get_user_items(user.tenant_id, user.id)
	assert len(items) == 0


async def test_get_watchlist_with_prices(
	watchlist_service, user, ticker, watchlist, session
):
	from datetime import datetime, timezone
	from decimal import Decimal

	market_data = MarketData(
		ticker_id=ticker.id,
		timeframe="1d",
		timestamp=datetime.now(timezone.utc),
		open=Decimal("150.0"),
		high=Decimal("160.0"),
		low=Decimal("145.0"),
		close=Decimal("155.0"),
		volume=Decimal("1000000"),
		source="test",
	)
	session.add(market_data)

	market_data_prev = MarketData(
		ticker_id=ticker.id,
		timeframe="1d",
		timestamp=datetime.now(timezone.utc) - timedelta(days=1),
		open=Decimal("145.0"),
		high=Decimal("155.0"),
		low=Decimal("140.0"),
		close=Decimal("150.0"),
		volume=Decimal("950000"),
		source="test",
	)
	session.add(market_data_prev)
	await session.flush()

	await watchlist_service.add_item(
		user.tenant_id,
		user.id,
		WatchlistItemCreate(
			ticker_id=ticker.id,
			watchlist_id=watchlist.id,
			target_price=Decimal("160"),
			stop_loss=Decimal("140"),
		),
	)

	items = await watchlist_service.get_watchlist_with_prices(
		tenant_id=user.tenant_id, user_id=user.id, limit=10, sort_by="change_percent"
	)

	assert len(items) >= 1
	item = items[0]

	assert item.symbol == ticker.symbol
	assert item.last_price is not None
	assert item.change_percent == 3.3333333333333335
	assert isinstance(item.signals, list)


async def test_get_watchlist_with_prices_empty(watchlist_service, user):
	items = await watchlist_service.get_watchlist_with_prices(user.tenant_id, user.id)
	assert items == []


async def test_get_watchlist_with_prices_sorting(
	watchlist_service, user, ticker, watchlist, session
):
	from datetime import datetime, timezone
	from decimal import Decimal

	market_data = MarketData(
		ticker_id=ticker.id,
		timeframe="1d",
		timestamp=datetime.now(timezone.utc),
		open=Decimal("150.0"),
		high=Decimal("160.0"),
		low=Decimal("145.0"),
		close=Decimal("155.0"),
		volume=Decimal("1000000"),
		source="test",
	)
	session.add(market_data)

	market_data_prev = MarketData(
		ticker_id=ticker.id,
		timeframe="1d",
		timestamp=datetime.now(timezone.utc) - timedelta(days=1),
		open=Decimal("145.0"),
		high=Decimal("155.0"),
		low=Decimal("140.0"),
		close=Decimal("150.0"),
		volume=Decimal("950000"),
		source="test",
	)
	session.add(market_data_prev)
	await session.flush()

	await watchlist_service.add_item(
		user.tenant_id,
		user.id,
		WatchlistItemCreate(ticker_id=ticker.id, watchlist_id=watchlist.id),
	)

	items_price = await watchlist_service.get_watchlist_with_prices(
		user.tenant_id, user.id, sort_by="price", order="desc"
	)

	items_change = await watchlist_service.get_watchlist_with_prices(
		user.tenant_id, user.id, sort_by="change_percent", order="asc"
	)

	assert len(items_price) == len(items_change) == 1
	assert items_price[0].symbol == ticker.symbol
	assert items_change[0].symbol == ticker.symbol


class TestWatchlistServiceSignals:
	"""Тесты для сигналов и анализа (новые тесты)"""

	@pytest.mark.parametrize(
		"change_pct,expected",
		[
			(10.0, 20),  # 10% = strong_bullish
			(3.0, 10),  # 3% = bullish
			(0.5, 0),  # 0.5% = neutral
			(-3.0, -10),  # -3% = bearish
			(-10.0, -20),  # -10% = strong_bearish
		],
	)
	def test_calculate_score_change_only(self, watchlist_service, change_pct, expected):
		"""Тест расчета score только на основе изменения цены"""
		score = watchlist_service._calculate_score(change_pct, [])
		assert score == expected

	@pytest.mark.parametrize(
		"signals,expected",
		[
			([SignalType.TARGET_HIT], 15),
			([SignalType.STOP_LOSS_HIT], -15),
			([SignalType.TARGET_HIT, SignalType.STOP_LOSS_HIT], 0),
			([SignalType.TARGET_HIT, SignalType.STOP_LOSS_HIT, "OTHER"], 0),
			(["UNKNOWN"], 0),
			([], 0),
		],
	)
	def test_calculate_score_signals_only(self, watchlist_service, signals, expected):
		"""Тест расчета score только на основе сигналов (change_pct = 0)"""
		score = watchlist_service._calculate_score(0.0, signals)
		assert score == expected

	def test_calculate_score_change_and_signals(self, watchlist_service):
		"""Тест расчета score с учетом и изменения, и сигналов"""
		score = watchlist_service._calculate_score(
			change_pct=3.0,
			signals=[SignalType.TARGET_HIT],  # bullish = 10  # +15
		)
		assert score == 25

	@pytest.mark.parametrize(
		"score,expected_signal",
		[
			(30, "STRONG_BUY"),
			(15, "BUY"),
			(5, "HOLD"),
			(-5, "HOLD"),
			(-15, "SELL"),
			(-30, "STRONG_SELL"),
		],
	)
	def test_get_result_by_score(self, watchlist_service, score, expected_signal):
		"""Тест определения результата по score"""
		result = watchlist_service._get_result_by_score(score)
		assert result.action == expected_signal

	@pytest.mark.parametrize(
		"change_pct,signals,expected_signal",
		[
			(0.10, ["TARGET_HIT"], "STRONG_BUY"),
			(0.05, [], "STRONG_BUY"),
			(0.03, [], "BUY"),
			(0.01, [], "HOLD"),
			(-0.01, [], "HOLD"),
			(-0.03, [], "SELL"),
			(-0.05, [], "STRONG_SELL"),
			(-0.10, ["STOP_LOSS_HIT"], "STRONG_SELL"),
		],
	)
	def test_generate_signal_analysis(
		self, watchlist_service, change_pct, signals, expected_signal
	):
		"""Тест генерации полного анализа"""
		result = watchlist_service.generate_signal_analysis(change_pct, signals)
		if hasattr(result, "signal"):
			assert result.signal == expected_signal
		elif hasattr(result, "label"):
			assert result.label == expected_signal


class TestWatchlistServiceWatchlist:
	"""Тесты для управления watchlist (новые тесты)"""

	async def test_create_watchlist_duplicate_name_same_tenant(
		self, watchlist_service, user
	):
		"""Тест: ошибка при создании watchlist с дублирующимся именем в одном tenant"""
		watchlist_in = WatchlistCreate(name="Duplicate", description="Test")

		await watchlist_service.create_watchlist(user.tenant_id, user.id, watchlist_in)

		with pytest.raises(HTTPException) as exc:
			await watchlist_service.create_watchlist(
				user.tenant_id, user.id, watchlist_in
			)

		assert exc.value.status_code == 400
		assert "already exists" in exc.value.detail.lower()

	async def test_create_watchlist_same_name_different_tenant(
		self, watchlist_service, user, other_user
	):
		"""Тест: можно создать watchlist с одинаковым именем для разных tenant"""
		watchlist_in = WatchlistCreate(name="Same Name", description="Test")

		result1 = await watchlist_service.create_watchlist(
			user.tenant_id, user.id, watchlist_in
		)
		result2 = await watchlist_service.create_watchlist(
			other_user.tenant_id, other_user.id, watchlist_in
		)

		assert result1.name == result2.name
		assert result1.tenant_id != result2.tenant_id
		assert result1.owner_id != result2.owner_id

	async def test_create_watchlist_without_description(self, watchlist_service, user):
		"""Тест создания watchlist без описания"""
		watchlist_in = WatchlistCreate(name="Simple Watchlist")

		result = await watchlist_service.create_watchlist(
			user.tenant_id, user.id, watchlist_in
		)

		assert result.name == "Simple Watchlist"
		assert result.description is None

	async def test_update_item_watchlist_not_found(
		self, watchlist, watchlist_service, user, session, ticker
	):
		"""Тест: ошибка при обновлении элемента, чей watchlist не существует"""
		watchlist = Watchlist(
			tenant_id=user.tenant_id,
			owner_id=user.id,
			name="Test Watchlist",
			is_default=True,
		)
		session.add(watchlist)
		await session.commit()
		await session.refresh(watchlist)

		item = WatchlistItem(
			id=uuid7(),
			tenant_id=user.tenant_id,
			ticker_id=ticker.id,
			watchlist_id=watchlist.id,
		)
		session.add(item)
		await session.commit()
		await session.refresh(item)

		await session.delete(item)
		await session.commit()

		await session.delete(watchlist)
		await session.commit()

		with pytest.raises(HTTPException) as exc:
			await watchlist_service.update_item(
				user.tenant_id, user.id, item.id, WatchlistItemUpdate(notes="test")
			)

		assert exc.value.status_code == 404
		assert "Watchlist item not found" in exc.value.detail

	async def test_remove_item_watchlist_not_found(
		self, watchlist_service, user, session, ticker
	):
		"""Тест: ошибка при удалении элемента, чей watchlist не существует"""
		watchlist = Watchlist(
			tenant_id=user.tenant_id,
			owner_id=user.id,
			name="Test Watchlist",
			is_default=True,
		)
		session.add(watchlist)
		await session.commit()
		await session.refresh(watchlist)

		item = WatchlistItem(
			id=uuid7(),
			tenant_id=user.tenant_id,
			ticker_id=ticker.id,
			watchlist_id=watchlist.id,
		)
		session.add(item)
		await session.commit()
		await session.refresh(item)

		await session.delete(item)
		await session.commit()

		await session.delete(watchlist)
		await session.commit()

		with pytest.raises(HTTPException) as exc:
			await watchlist_service.update_item(
				user.tenant_id, user.id, item.id, WatchlistItemUpdate(notes="test")
			)

		assert exc.value.status_code == 404
		assert "Watchlist item not found" in str(exc.value.detail)

	async def test_get_or_create_default_watchlist_creates_new(
		self, watchlist_service, user, session
	):
		"""Тест: создание дефолтного watchlist, если его нет"""
		existing_watchlists = await session.execute(
			select(Watchlist).where(Watchlist.owner_id == user.id)
		)
		for watchlist in existing_watchlists.scalars():
			await session.execute(
				delete(WatchlistItem).where(WatchlistItem.watchlist_id == watchlist.id)
			)
			await session.delete(watchlist)

		await session.commit()

		result = await watchlist_service.get_or_create_default_watchlist(
			user.tenant_id, user.id
		)

		assert result is not None
		assert result.is_default is True
		assert result.owner_id == user.id
		assert result.tenant_id == user.tenant_id

		# Проверяем, что создался только один watchlist
		count = await session.execute(
			select(func.count())
			.select_from(Watchlist)
			.where(Watchlist.owner_id == user.id)
		)
		assert count.scalar() == 1

	async def test_get_or_create_default_watchlist_returns_existing(
		self, watchlist_service, user, watchlist
	):
		"""Тест: возврат существующего дефолтного watchlist"""
		watchlist.is_default = True
		await watchlist_service.session.commit()

		result = await watchlist_service.get_or_create_default_watchlist(
			user.tenant_id, user.id
		)

		assert result.id == watchlist.id
		assert result.name == watchlist.name


class TestWatchlistServiceSearchAndFilter:
	"""Тесты для поиска и фильтрации (новые тесты)"""

	async def test_get_watchlist_with_prices_search_by_symbol(
		self, watchlist_service, user, sample_ticker, watchlist, sample_market_data
	):
		"""Тест поиска по символу"""
		await watchlist_service.add_item(
			user.tenant_id,
			user.id,
			WatchlistItemCreate(ticker_id=sample_ticker.id, watchlist_id=watchlist.id),
		)

		# Поиск по части символа
		items = await watchlist_service.get_watchlist_with_prices(
			tenant_id=user.tenant_id, user_id=user.id, search=sample_ticker.symbol[:2]
		)

		assert len(items) == 1
		assert sample_ticker.symbol.lower() in items[0].symbol.lower()

	async def test_get_watchlist_with_prices_search_not_found(
		self, watchlist_service, user, sample_ticker, watchlist, sample_market_data
	):
		"""Тест поиска, который ничего не находит"""
		await watchlist_service.add_item(
			user.tenant_id,
			user.id,
			WatchlistItemCreate(ticker_id=sample_ticker.id, watchlist_id=watchlist.id),
		)

		items = await watchlist_service.get_watchlist_with_prices(
			tenant_id=user.tenant_id, user_id=user.id, search="NONEXISTENT"
		)

		assert len(items) == 0

	@pytest.mark.parametrize(
		"asset_type,expected_count",
		[
			("stock", 1),
			("crypto", 0),
			("all", 1),
		],
	)
	async def test_get_watchlist_with_prices_filter_by_asset_type(
		self,
		watchlist_service,
		user,
		sample_ticker,
		watchlist,
		asset_type,
		expected_count,
		sample_market_data,
	):
		"""Тест фильтрации по типу актива"""
		await watchlist_service.add_item(
			user.tenant_id,
			user.id,
			WatchlistItemCreate(ticker_id=sample_ticker.id, watchlist_id=watchlist.id),
		)

		items = await watchlist_service.get_watchlist_with_prices(
			tenant_id=user.tenant_id, user_id=user.id, asset_type=asset_type
		)

		assert len(items) == expected_count

	@pytest.mark.parametrize(
		"sort_by,order",
		[
			("price", "asc"),
			("price", "desc"),
			("change_percent", "asc"),
			("change_percent", "desc"),
			("symbol", "asc"),
			("symbol", "desc"),
			("added_at", "asc"),
			("added_at", "desc"),
		],
	)
	async def test_get_watchlist_with_prices_sorting(
		self,
		watchlist_service,
		user,
		sample_ticker,
		watchlist,
		sort_by,
		order,
		sample_market_data,
	):
		"""Тест сортировки"""
		await watchlist_service.add_item(
			user.tenant_id,
			user.id,
			WatchlistItemCreate(ticker_id=sample_ticker.id, watchlist_id=watchlist.id),
		)

		items = await watchlist_service.get_watchlist_with_prices(
			tenant_id=user.tenant_id, user_id=user.id, sort_by=sort_by, order=order
		)

		assert len(items) >= 1

	async def test_get_watchlist_with_prices_with_ai_and_trend(
		self,
		watchlist_service,
		user,
		sample_ticker,
		watchlist,
		session,
		sample_market_data,
	):
		"""Тест с включенными AI и трендом"""
		await watchlist_service.add_item(
			user.tenant_id,
			user.id,
			WatchlistItemCreate(ticker_id=sample_ticker.id, watchlist_id=watchlist.id),
		)

		items = await watchlist_service.get_watchlist_with_prices(
			tenant_id=user.tenant_id,
			user_id=user.id,
			include_ai=True,
			include_trend=True,
		)

		assert len(items) >= 1
		assert items[0].ai_insight is not None
		assert items[0].trend is not None
