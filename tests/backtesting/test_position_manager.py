from datetime import datetime

import pytest

from swingtraderai.backtesting.config import (
	BacktestConfig,
	PositionSizingMode,
)
from swingtraderai.backtesting.models import ExitReason, Side, Signal
from swingtraderai.backtesting.position_manager import PositionManager


def make_signal(
	*,
	side=Side.LONG,
	score=None,
	signal_score=8,
	entry_reference_price=100.0,
	stop_loss=95.0,
	take_profit=110.0,
	timestamp=None,
	ticker="AAPL",
	timeframe="1h",
	signal_type="BUY",
	market_regime="TRENDING",
	ml_probability=None,
	confidence=None,
	indicators_used=None,
	metadata=None,
):
	final_score = score if score is not None else signal_score

	return Signal(
		side=side,
		signal_score=final_score,
		entry_reference_price=entry_reference_price,
		stop_loss=stop_loss,
		take_profit=take_profit,
		timestamp=timestamp or datetime(2025, 1, 1, 10, 0),
		ticker=ticker,
		timeframe=timeframe,
		signal_type=signal_type,
		market_regime=market_regime,
		ml_probability=ml_probability,
		confidence=confidence,
		indicators_used=indicators_used or [],
		metadata=metadata or {},
	)


@pytest.fixture
def config():
	return BacktestConfig(
		initial_capital=100_000.0,
		commission_pct=0.001,
		slippage_pct=0.001,
		fixed_commission=0.0,
		position_sizing_mode=PositionSizingMode.FIXED_QUANTITY,
		position_size=10.0,
		max_position_pct=1.0,
		signal_threshold=5,
	)


@pytest.fixture
def manager(config):
	return PositionManager(config)


class TestPositionManagerInitialization:
	def test_initial_state(self, config):
		manager = PositionManager(config)

		assert manager.cash == pytest.approx(100_000.0)
		assert manager.equity == pytest.approx(100_000.0)
		assert manager.peak_equity == pytest.approx(100_000.0)
		assert manager.position is None
		assert manager.pending_entry is None
		assert manager.closed_trades == []

	def test_initial_drawdown_is_zero(self, manager):
		assert manager.current_drawdown == pytest.approx(0.0)
		assert manager.current_drawdown_pct == pytest.approx(0.0)


class TestComputeQuantity:
	def test_fixed_quantity(self, config):
		config.position_sizing_mode = PositionSizingMode.FIXED_QUANTITY
		config.position_size = 10.0
		config.max_position_pct = 1.0

		manager = PositionManager(config)

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		assert qty == pytest.approx(10.0)

	def test_fixed_quantity_is_capped_by_max_position_pct(self, config):
		config.position_sizing_mode = PositionSizingMode.FIXED_QUANTITY
		config.position_size = 2_000.0
		config.max_position_pct = 0.25

		manager = PositionManager(config)

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		# 25% of 100_000 = 25_000 notional
		assert qty == pytest.approx(250.0)

	def test_fixed_percent_equity(self, config):
		config.position_sizing_mode = PositionSizingMode.FIXED_PERCENT_EQUITY
		config.position_size = 0.20
		config.max_position_pct = 1.0

		manager = PositionManager(config)

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		# 20% of 100_000 = 20_000 / 100
		assert qty == pytest.approx(200.0)

	def test_fixed_percent_equity_uses_current_equity(self, config):
		config.position_sizing_mode = PositionSizingMode.FIXED_PERCENT_EQUITY
		config.position_size = 0.20
		config.max_position_pct = 1.0

		manager = PositionManager(config)
		manager.equity = 50_000.0

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		assert qty == pytest.approx(100.0)

	def test_risk_based_sizing(self, config):
		config.position_sizing_mode = PositionSizingMode.RISK_BASED
		config.risk_per_trade = 0.01
		config.max_position_pct = 1.0

		manager = PositionManager(config)

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		# Risk = 1_000
		# Risk/unit = 5
		# Quantity = 200
		assert qty == pytest.approx(200.0)

	def test_risk_based_sizing_uses_absolute_stop_distance(self, config):
		config.position_sizing_mode = PositionSizingMode.RISK_BASED
		config.risk_per_trade = 0.01
		config.max_position_pct = 1.0

		manager = PositionManager(config)

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=105.0,
			side=Side.LONG,
		)

		assert qty == pytest.approx(200.0)

	def test_risk_based_without_stop_falls_back_to_percent_equity(
		self,
		config,
	):
		config.position_sizing_mode = PositionSizingMode.RISK_BASED
		config.risk_per_trade = 0.01
		config.max_position_pct = 1.0

		manager = PositionManager(config)

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=None,
			side=Side.LONG,
		)

		# Fallback: 1% equity = 1_000 notional
		assert qty == pytest.approx(10.0)

	def test_risk_based_with_zero_stop_distance_falls_back(
		self,
		config,
	):
		config.position_sizing_mode = PositionSizingMode.RISK_BASED
		config.risk_per_trade = 0.01
		config.max_position_pct = 1.0

		manager = PositionManager(config)

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=100.0,
			side=Side.LONG,
		)

		assert qty == pytest.approx(10.0)

	def test_quantity_is_capped_by_available_cash(self, config):
		config.position_sizing_mode = PositionSizingMode.FIXED_QUANTITY
		config.position_size = 2_000.0
		config.max_position_pct = 1.0
		config.commission_pct = 0.01
		config.slippage_pct = 0.01

		manager = PositionManager(config)
		manager.cash = 10_000.0

		qty = manager._compute_quantity(
			entry_price=100.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		# cost_buffer = 1.02
		expected = 10_000.0 / (100.0 * 1.02)

		assert qty == pytest.approx(expected)

	def test_zero_entry_price_returns_zero(self, manager):
		qty = manager._compute_quantity(
			entry_price=0.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		assert qty == 0.0

	def test_negative_entry_price_returns_zero(self, manager):
		qty = manager._compute_quantity(
			entry_price=-100.0,
			stop_loss=95.0,
			side=Side.LONG,
		)

		assert qty == 0.0


class TestQueueEntry:
	def test_valid_long_signal_is_queued(self, manager):
		signal = make_signal(side=Side.LONG, score=8)

		manager.queue_entry(signal)

		assert manager.pending_entry is signal

	def test_neutral_signal_is_ignored(self, manager):
		signal = make_signal(side=Side.NEUTRAL, score=8)

		manager.queue_entry(signal)

		assert manager.pending_entry is None

	def test_short_signal_is_ignored_when_shorts_are_disabled(
		self,
		manager,
	):
		signal = make_signal(side=Side.SHORT, score=8)

		manager.queue_entry(signal)

		assert manager.pending_entry is None

	def test_short_signal_is_accepted_when_shorts_are_enabled(self, config):
		config.allow_short = True
		manager = PositionManager(config)

		signal = make_signal(side=Side.SHORT, score=8)

		manager.queue_entry(signal)

		assert manager.pending_entry is signal

	def test_weak_signal_is_ignored(self, manager):
		signal = make_signal(
			side=Side.LONG,
			score=4,
		)

		manager.queue_entry(signal)

		assert manager.pending_entry is None

	def test_signal_at_threshold_is_accepted(self, manager):
		signal = make_signal(
			side=Side.LONG,
			score=5,
		)

		manager.queue_entry(signal)

		assert manager.pending_entry is signal

	def test_second_signal_does_not_replace_pending_entry(self, manager):
		first = make_signal(
			side=Side.LONG,
			score=8,
			ticker="FIRST",
		)
		second = make_signal(
			side=Side.LONG,
			score=10,
			ticker="SECOND",
		)

		manager.queue_entry(first)
		manager.queue_entry(second)

		assert manager.pending_entry is first

	def test_signal_is_ignored_when_position_is_open(
		self,
		manager,
	):
		manager.position = object()

		signal = make_signal(side=Side.LONG, score=8)

		manager.queue_entry(signal)

		assert manager.pending_entry is None


class TestTryFillPendingEntry:
	def test_pending_entry_is_filled_at_bar_open(self, manager):
		signal = make_signal(
			side=Side.LONG,
			score=8,
			stop_loss=95.0,
			take_profit=110.0,
		)

		manager.queue_entry(signal)

		bar_time = datetime(2025, 1, 2, 10, 0)

		fill = manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=bar_time,
			bar_index=10,
		)

		assert fill is not None
		assert fill.price == pytest.approx(100.1)
		assert fill.quantity == pytest.approx(10.0)
		assert fill.is_entry is True

		assert manager.position is not None
		assert manager.position.side is Side.LONG
		assert manager.position.quantity == pytest.approx(10.0)
		assert manager.position.entry_price == pytest.approx(100.1)
		assert manager.position.entry_time == bar_time
		assert manager.position.entry_bar_index == 10
		assert manager.position.stop_loss == pytest.approx(95.0)
		assert manager.position.take_profit == pytest.approx(110.0)
		assert manager.position.bars_held == 0

	def test_pending_entry_is_consumed_after_fill(self, manager):
		signal = make_signal()

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		assert manager.pending_entry is None

	def test_no_pending_entry_returns_none(self, manager):
		result = manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		assert result is None
		assert manager.position is None

	def test_pending_entry_is_cleared_when_position_already_exists(
		self,
		manager,
	):
		signal = make_signal()
		manager.pending_entry = signal
		manager.position = object()

		result = manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		assert result is None
		assert manager.pending_entry is None

	def test_entry_rejected_when_quantity_is_zero(self, manager):
		manager.config.position_size = 0.0

		signal = make_signal()
		manager.queue_entry(signal)

		result = manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		assert result is None
		assert manager.position is None

	def test_entry_reduces_cash(self, manager):
		signal = make_signal()
		manager.queue_entry(signal)

		initial_cash = manager.cash

		fill = manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		assert fill is not None

		expected_cost = fill.price * fill.quantity + fill.commission

		assert manager.cash == pytest.approx(initial_cash - expected_cost)


class TestUpdateOnBar:
	def _open_position(self, manager):
		signal = make_signal(
			side=Side.LONG,
			score=8,
			stop_loss=95.0,
			take_profit=110.0,
		)

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

	def test_no_position_returns_none(self, manager):
		result = manager.update_on_bar(
			bar_open=100.0,
			bar_high=105.0,
			bar_low=95.0,
			bar_close=102.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert result is None

	def test_bars_held_is_incremented(self, manager):
		self._open_position(manager)

		manager.update_on_bar(
			bar_open=100.0,
			bar_high=105.0,
			bar_low=99.0,
			bar_close=103.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert manager.position is not None
		assert manager.position.bars_held == 1

	def test_excursions_are_updated(self, manager):
		# Создаем сигнал с более широким стоп-лоссом
		signal = make_signal(
			side=Side.LONG,
			score=8,
			entry_reference_price=100.0,
			stop_loss=50.0,  # <-- Широкий стоп, чтобы не сработал
			take_profit=200.0,  # <-- Широкий тейк, чтобы не сработал
		)

		manager.queue_entry(signal)
		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		assert manager.position is not None

		result = manager.update_on_bar(
			bar_open=100.0,
			bar_high=110.0,
			bar_low=90.0,
			bar_close=105.0,
			bar_time=datetime(2025, 1, 3),
		)

		# Проверяем, что позиция не закрылась
		assert result is None, f"Position should not be closed, but got {result}"
		assert manager.position is not None
		assert manager.position.max_favorable_price == pytest.approx(110.0)
		assert manager.position.max_adverse_price == pytest.approx(90.0)

	def test_take_profit_closes_long_position(self, manager):
		self._open_position(manager)

		trade = manager.update_on_bar(
			bar_open=100.0,
			bar_high=111.0,
			bar_low=99.0,
			bar_close=108.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert trade is not None
		assert trade.exit_reason is ExitReason.TAKE_PROFIT
		assert manager.position is None
		assert len(manager.closed_trades) == 1

	def test_stop_loss_closes_long_position(self, manager):
		self._open_position(manager)

		trade = manager.update_on_bar(
			bar_open=100.0,
			bar_high=103.0,
			bar_low=94.0,
			bar_close=97.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert trade is not None
		assert trade.exit_reason is ExitReason.STOP_LOSS
		assert manager.position is None

	def test_time_exit(self, config):
		config.max_bars_in_trade = 2
		manager = PositionManager(config)

		signal = make_signal(
			stop_loss=50.0,
			take_profit=200.0,
		)
		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		first = manager.update_on_bar(
			bar_open=100.0,
			bar_high=105.0,
			bar_low=99.0,
			bar_close=103.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert first is None
		assert manager.position is not None

		second = manager.update_on_bar(
			bar_open=103.0,
			bar_high=106.0,
			bar_low=102.0,
			bar_close=104.0,
			bar_time=datetime(2025, 1, 4),
		)

		assert second is not None
		assert second.exit_reason is ExitReason.TIME_EXIT
		assert second.bars_held == 2
		assert manager.position is None

	def test_signal_reverse_closes_long_position(self, manager):
		self._open_position(manager)

		reverse_signal = make_signal(
			side=Side.SHORT,
			score=8,
		)

		trade = manager.update_on_bar(
			bar_open=100.0,
			bar_high=104.0,
			bar_low=99.0,
			bar_close=102.0,
			bar_time=datetime(2025, 1, 3),
			signal=reverse_signal,
		)

		assert trade is not None
		assert trade.exit_reason is ExitReason.SIGNAL_REVERSE
		assert manager.position is None

	def test_same_direction_signal_does_not_close_position(
		self,
		manager,
	):
		self._open_position(manager)

		signal = make_signal(
			side=Side.LONG,
			score=10,
		)

		trade = manager.update_on_bar(
			bar_open=100.0,
			bar_high=104.0,
			bar_low=99.0,
			bar_close=102.0,
			bar_time=datetime(2025, 1, 3),
			signal=signal,
		)

		assert trade is None
		assert manager.position is not None

	def test_neutral_signal_does_not_close_position(self, manager):
		self._open_position(manager)

		signal = make_signal(
			side=Side.NEUTRAL,
			score=10,
		)

		trade = manager.update_on_bar(
			bar_open=100.0,
			bar_high=104.0,
			bar_low=99.0,
			bar_close=102.0,
			bar_time=datetime(2025, 1, 3),
			signal=signal,
		)

		assert trade is None
		assert manager.position is not None

	def test_stop_target_has_priority_over_time_exit(self, config):
		config.max_bars_in_trade = 1
		manager = PositionManager(config)

		signal = make_signal(
			stop_loss=95.0,
			take_profit=110.0,
		)
		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		trade = manager.update_on_bar(
			bar_open=100.0,
			bar_high=111.0,
			bar_low=99.0,
			bar_close=108.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert trade is not None
		assert trade.exit_reason is ExitReason.TAKE_PROFIT


class TestTrailingStop:
	def test_long_trailing_stop_moves_up(self):
		config = BacktestConfig(
			initial_capital=100_000,
			position_sizing_mode=PositionSizingMode.FIXED_QUANTITY,
			position_size=10,
			max_position_pct=1.0,
			trailing_stop=True,
			trailing_stop_pct=0.05,
		)

		manager = PositionManager(config)

		signal = make_signal(
			entry_reference_price=100.0,
			stop_loss=80.0,
			take_profit=150.0,
		)

		manager.queue_entry(signal)
		fill = manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		assert fill is not None
		assert manager.position is not None

		# Первый апдейт - цена до 120, трейлинг-стоп = 114
		# bar_low должен быть выше 114, чтобы не сработал стоп
		result = manager.update_on_bar(
			bar_open=100.0,
			bar_high=120.0,
			bar_low=115.0,  # <-- Изменено с 110 на 115 (выше 114)
			bar_close=115.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert result is None
		assert manager.position is not None
		assert manager.position.trailing_stop == pytest.approx(114.0)

		# Второй апдейт - цена растет до 130, трейлинг-стоп должен подняться до 123.5
		# bar_low должен быть выше 123.5, чтобы не сработал стоп
		result2 = manager.update_on_bar(
			bar_open=115.0,
			bar_high=130.0,
			bar_low=124.0,  # <-- Изменено с 118 на 124 (выше 123.5)
			bar_close=125.0,
			bar_time=datetime(2025, 1, 4),
		)

		assert result2 is None
		assert manager.position is not None
		assert manager.position.trailing_stop == pytest.approx(123.5)  # 130 * 0.95

	def test_long_trailing_stop_does_not_move_down(self):
		config = BacktestConfig(
			initial_capital=100_000,
			position_sizing_mode=PositionSizingMode.FIXED_QUANTITY,
			position_size=10,
			max_position_pct=1.0,
			trailing_stop=True,
			trailing_stop_pct=0.05,
		)

		manager = PositionManager(config)

		signal = make_signal(
			entry_reference_price=100.0,
			stop_loss=80.0,  # Далеко, чтобы не сработал
			take_profit=150.0,  # Далеко, чтобы не сработал
		)

		manager.queue_entry(signal)
		fill = manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		# Проверяем, что позиция открылась
		assert fill is not None
		assert manager.position is not None

		# Первый апдейт - цена растет до 120, трейлинг-стоп устанавливается на 114
		# ВАЖНО: bar_low должен быть ВЫШЕ будущего трейлинг-стопа (114)
		result = manager.update_on_bar(
			bar_open=100.0,
			bar_high=120.0,
			bar_low=115.0,  # <-- Изменено с 110 на 115 (выше 114)
			bar_close=115.0,
			bar_time=datetime(2025, 1, 3),
		)

		# Проверяем, что позиция не закрылась
		assert result is None, f"Position should not be closed, but got {result}"
		assert manager.position is not None
		assert manager.position.trailing_stop is not None

		first_stop = manager.position.trailing_stop
		assert first_stop == pytest.approx(114.0)  # 120 * 0.95

		# Второй апдейт - цена снижается, но НЕ достигает трейлинг-стопа
		# Трейлинг-стоп не должен двигаться вниз
		result2 = manager.update_on_bar(
			bar_open=115.0,
			bar_high=116.0,
			bar_low=114.5,  # Выше трейлинг-стопа (114.0)
			bar_close=114.5,
			bar_time=datetime(2025, 1, 4),
		)

		# Проверяем, что позиция все еще открыта
		assert result2 is None, f"Position should not be closed, but got {result2}"
		assert manager.position is not None
		assert manager.position.trailing_stop == pytest.approx(first_stop)

		# Третий апдейт - цена еще немного снижается, но все еще выше трейлинг-стопа
		result3 = manager.update_on_bar(
			bar_open=114.5,
			bar_high=115.0,
			bar_low=114.2,  # Все еще выше трейлинг-стопа (114.0)
			bar_close=114.2,
			bar_time=datetime(2025, 1, 5),
		)

		assert result3 is None, f"Position should not be closed, but got {result3}"
		assert manager.position is not None
		assert manager.position.trailing_stop == pytest.approx(first_stop)


class TestClose:
	def test_close_all_closes_open_position(self, manager):
		signal = make_signal(
			stop_loss=80.0,
			take_profit=150.0,
		)

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		trades = manager.close_all(
			bar_close=110.0,
			bar_time=datetime(2025, 1, 3),
		)

		assert len(trades) == 1
		assert trades[0].exit_reason is ExitReason.END_OF_DATA
		assert manager.position is None
		assert len(manager.closed_trades) == 1

	def test_close_all_without_position_returns_empty_list(
		self,
		manager,
	):
		assert (
			manager.close_all(
				bar_close=100.0,
				bar_time=datetime(2025, 1, 3),
			)
			== []
		)

	def test_closed_trade_contains_entry_and_exit_data(
		self,
		manager,
	):
		signal_time = datetime(2025, 1, 1, 10, 0)

		signal = make_signal(
			timestamp=signal_time,
			ticker="TEST",
			timeframe="1h",
			signal_type="BUY",
			score=9,
			entry_reference_price=100.0,
			stop_loss=95.0,
			take_profit=110.0,
			market_regime="TRENDING",
			ml_probability=0.8,
		)

		manager.queue_entry(signal)

		entry_time = datetime(2025, 1, 2, 10, 0)
		exit_time = datetime(2025, 1, 3, 10, 0)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=entry_time,
			bar_index=5,
		)

		trade = manager.close_all(
			bar_close=110.0,
			bar_time=exit_time,
		)[0]

		assert trade.signal_timestamp == signal_time
		assert trade.ticker == "TEST"
		assert trade.timeframe == "1h"
		assert trade.side is Side.LONG
		assert trade.entry_time == entry_time
		assert trade.exit_time == exit_time
		assert trade.stop_loss == pytest.approx(95.0)
		assert trade.take_profit == pytest.approx(110.0)
		assert trade.signal_score == 9
		assert trade.market_regime == "TRENDING"
		assert trade.signal_type == "BUY"
		assert trade.ml_probability == pytest.approx(0.8)

	def test_profit_trade_has_positive_pnl(self, manager):
		signal = make_signal(
			stop_loss=80.0,
			take_profit=150.0,
		)

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		trade = manager.close_all(
			bar_close=110.0,
			bar_time=datetime(2025, 1, 3),
		)[0]

		assert trade.pnl > 0
		assert trade.pnl_percent > 0

	def test_loss_trade_has_negative_pnl(self, manager):
		signal = make_signal(
			stop_loss=80.0,
			take_profit=150.0,
		)

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		trade = manager.close_all(
			bar_close=90.0,
			bar_time=datetime(2025, 1, 3),
		)[0]

		assert trade.pnl < 0
		assert trade.pnl_percent < 0

	def test_trade_is_added_to_closed_trades(self, manager):
		signal = make_signal()

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		trade = manager.close_all(
			bar_close=105.0,
			bar_time=datetime(2025, 1, 3),
		)[0]

		assert manager.closed_trades == [trade]


class TestMarkToMarket:
	def test_equity_equals_cash_without_position(self, manager):
		manager.cash = 95_000.0

		equity = manager.mark_to_market(100.0)

		assert equity == pytest.approx(95_000.0)
		assert manager.equity == pytest.approx(95_000.0)

	def test_unrealized_profit_increases_equity(self, manager):
		signal = make_signal(
			stop_loss=80.0,
			take_profit=150.0,
		)

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		equity = manager.mark_to_market(110.0)

		assert equity > manager.cash

	def test_unrealized_loss_decreases_equity(self, manager):
		signal = make_signal(
			stop_loss=80.0,
			take_profit=150.0,
		)

		manager.queue_entry(signal)

		manager.try_fill_pending_entry(
			bar_open=100.0,
			bar_time=datetime(2025, 1, 2),
			bar_index=1,
		)

		equity = manager.mark_to_market(90.0)

		assert equity < manager.cash

	def test_peak_equity_does_not_decrease(self, manager):
		# Устанавливаем начальный пик
		manager.cash = 100_000.0
		manager.mark_to_market(100.0)  # equity = 100_000, peak = 100_000

		# Рост
		manager.cash = 120_000.0
		manager.mark_to_market(100.0)  # equity = 120_000, peak = 120_000

		# Падение
		manager.cash = 90_000.0
		manager.mark_to_market(100.0)  # equity = 90_000, peak должен остаться 120_000

		assert manager.peak_equity == pytest.approx(120_000.0)


class TestDrawdown:
	def test_drawdown_is_difference_between_peak_and_equity(
		self,
		manager,
	):
		manager.peak_equity = 120_000.0
		manager.equity = 100_000.0

		assert manager.current_drawdown == pytest.approx(20_000.0)

	def test_drawdown_percentage(self, manager):
		manager.peak_equity = 120_000.0
		manager.equity = 100_000.0

		assert manager.current_drawdown_pct == pytest.approx(20_000.0 / 120_000.0)

	def test_drawdown_is_zero_at_peak(self, manager):
		manager.peak_equity = 100_000.0
		manager.equity = 100_000.0

		assert manager.current_drawdown == pytest.approx(0.0)
		assert manager.current_drawdown_pct == pytest.approx(0.0)

	def test_drawdown_returns_zero_when_peak_is_non_positive(
		self,
		manager,
	):
		manager.peak_equity = 0.0
		manager.equity = 0.0

		assert manager.current_drawdown == pytest.approx(0.0)
		assert manager.current_drawdown_pct == pytest.approx(0.0)
