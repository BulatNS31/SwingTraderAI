import pytest

from swingtraderai.backtesting.config import (
	AmbiguousBarPolicy,
	BacktestConfig,
)
from swingtraderai.backtesting.execution import (
	ExitCheckResult,
	Fill,
	check_stop_and_target,
	create_entry_fill,
	create_exit_fill,
)
from swingtraderai.backtesting.models import ExitReason, Side


class TestFillDataclasses:
	def test_fill_is_immutable(self):
		fill = Fill(
			price=100.0,
			quantity=10.0,
			commission=1.0,
			slippage_amount=0.5,
			side=Side.LONG,
			is_entry=True,
		)

		with pytest.raises(AttributeError):
			fill.price = 101.0

	def test_exit_check_result_defaults(self):
		result = ExitCheckResult(hit=False)

		assert result.hit is False
		assert result.reason is None
		assert result.fill_price is None


class TestCreateEntryFill:
	@pytest.mark.parametrize(
		"side,expected_price",
		[
			(Side.LONG, 100.1),
			(Side.SHORT, 99.9),
		],
	)
	def test_entry_price_includes_slippage(
		self,
		side,
		expected_price,
	):
		config = BacktestConfig(
			commission_pct=0.001,
			slippage_pct=0.001,
			fixed_commission=0,
		)

		fill = create_entry_fill(
			raw_price=100.0,
			quantity=10.0,
			side=side,
			config=config,
		)

		assert fill.price == pytest.approx(expected_price)
		assert fill.side is side
		assert fill.is_entry is True
		assert fill.quantity == 10.0

	def test_long_entry_fill(self):
		config = BacktestConfig(
			commission_pct=0.001,
			slippage_pct=0.001,
			fixed_commission=5,
		)

		fill = create_entry_fill(
			raw_price=100.0,
			quantity=10.0,
			side=Side.LONG,
			config=config,
		)

		# Filled price = 100 * 1.001 = 100.1
		# Notional = 100.1 * 10 = 1001
		# Commission = 1001 * 0.001 + 5 = 6.001
		assert fill.price == pytest.approx(100.1)
		assert fill.commission == pytest.approx(6.001)

		# Slippage = |100.1 - 100| * 10 = 1
		assert fill.slippage_amount == pytest.approx(1.0)

	def test_short_entry_fill(self):
		config = BacktestConfig(
			commission_pct=0.001,
			slippage_pct=0.001,
			fixed_commission=5,
		)

		fill = create_entry_fill(
			raw_price=100.0,
			quantity=10.0,
			side=Side.SHORT,
			config=config,
		)

		# Filled price = 100 * 0.999 = 99.9
		# Notional = 999
		# Commission = 999 * 0.001 + 5 = 5.999
		assert fill.price == pytest.approx(99.9)
		assert fill.commission == pytest.approx(5.999)
		assert fill.slippage_amount == pytest.approx(1.0)

	def test_entry_without_costs(self):
		config = BacktestConfig(
			commission_pct=0,
			slippage_pct=0,
			fixed_commission=0,
		)

		fill = create_entry_fill(
			raw_price=100.0,
			quantity=10.0,
			side=Side.LONG,
			config=config,
		)

		assert fill.price == pytest.approx(100.0)
		assert fill.commission == pytest.approx(0.0)
		assert fill.slippage_amount == pytest.approx(0.0)

	def test_entry_fill_uses_quantity(self):
		config = BacktestConfig(
			commission_pct=0,
			slippage_pct=0.001,
			fixed_commission=0,
		)

		fill = create_entry_fill(
			raw_price=100.0,
			quantity=25.0,
			side=Side.LONG,
			config=config,
		)

		assert fill.quantity == 25.0
		assert fill.slippage_amount == pytest.approx(2.5)


class TestCreateExitFill:
	@pytest.mark.parametrize(
		"side,expected_price",
		[
			(Side.LONG, 99.9),
			(Side.SHORT, 100.1),
		],
	)
	def test_exit_price_includes_slippage(
		self,
		side,
		expected_price,
	):
		config = BacktestConfig(
			commission_pct=0.001,
			slippage_pct=0.001,
			fixed_commission=0,
		)

		fill = create_exit_fill(
			raw_price=100.0,
			quantity=10.0,
			side=side,
			config=config,
		)

		assert fill.price == pytest.approx(expected_price)
		assert fill.side is side
		assert fill.is_entry is False
		assert fill.quantity == 10.0

	def test_long_exit_fill(self):
		config = BacktestConfig(
			commission_pct=0.001,
			slippage_pct=0.001,
			fixed_commission=5,
		)

		fill = create_exit_fill(
			raw_price=100.0,
			quantity=10.0,
			side=Side.LONG,
			config=config,
		)

		# Filled price = 99.9
		# Notional = 999
		# Commission = 999 * 0.001 + 5 = 5.999
		assert fill.price == pytest.approx(99.9)
		assert fill.commission == pytest.approx(5.999)
		assert fill.slippage_amount == pytest.approx(1.0)

	def test_short_exit_fill(self):
		config = BacktestConfig(
			commission_pct=0.001,
			slippage_pct=0.001,
			fixed_commission=5,
		)

		fill = create_exit_fill(
			raw_price=100.0,
			quantity=10.0,
			side=Side.SHORT,
			config=config,
		)

		# Filled price = 100.1
		# Notional = 1001
		# Commission = 1001 * 0.001 + 5 = 6.001
		assert fill.price == pytest.approx(100.1)
		assert fill.commission == pytest.approx(6.001)
		assert fill.slippage_amount == pytest.approx(1.0)

	def test_exit_without_costs(self):
		config = BacktestConfig(
			commission_pct=0,
			slippage_pct=0,
			fixed_commission=0,
		)

		fill = create_exit_fill(
			raw_price=100.0,
			quantity=10.0,
			side=Side.LONG,
			config=config,
		)

		assert fill.price == pytest.approx(100.0)
		assert fill.commission == pytest.approx(0.0)
		assert fill.slippage_amount == pytest.approx(0.0)


class TestCheckStopAndTarget:
	@pytest.fixture
	def config(self):
		return BacktestConfig(
			ambiguous_bar_policy=AmbiguousBarPolicy.CONSERVATIVE,
		)

	def test_no_exit_when_nothing_is_hit(self, config):
		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=95.0,
			take_profit=110.0,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=105.0,
			bar_low=97.0,
			bar_close=103.0,
			config=config,
		)

		assert result == ExitCheckResult(hit=False)

	def test_long_stop_loss_is_hit(self, config):
		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=95.0,
			take_profit=110.0,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=105.0,
			bar_low=94.0,
			bar_close=98.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(95.0)

	def test_long_take_profit_is_hit(self, config):
		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=95.0,
			take_profit=110.0,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=111.0,
			bar_low=99.0,
			bar_close=108.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TAKE_PROFIT
		assert result.fill_price == pytest.approx(110.0)

	def test_short_stop_loss_is_hit(self, config):
		result = check_stop_and_target(
			side=Side.SHORT,
			stop_loss=105.0,
			take_profit=90.0,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=106.0,
			bar_low=98.0,
			bar_close=103.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(105.0)

	def test_short_take_profit_is_hit(self, config):
		result = check_stop_and_target(
			side=Side.SHORT,
			stop_loss=105.0,
			take_profit=90.0,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=102.0,
			bar_low=89.0,
			bar_close=92.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TAKE_PROFIT
		assert result.fill_price == pytest.approx(90.0)

	@pytest.mark.parametrize(
		"side,stop_loss,take_profit,bar_high,bar_low",
		[
			(Side.LONG, 95.0, 110.0, 110.0, 95.0),
			(Side.SHORT, 105.0, 90.0, 105.0, 90.0),
		],
	)
	def test_exact_touch_counts_as_hit(
		self,
		config,
		side,
		stop_loss,
		take_profit,
		bar_high,
		bar_low,
	):
		result = check_stop_and_target(
			side=side,
			stop_loss=stop_loss,
			take_profit=take_profit,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=bar_high,
			bar_low=bar_low,
			bar_close=100.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(stop_loss)

	def test_only_take_profit_when_stop_is_none(self, config):
		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=None,
			take_profit=110.0,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=111.0,
			bar_low=99.0,
			bar_close=108.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TAKE_PROFIT
		assert result.fill_price == pytest.approx(110.0)

	def test_only_stop_loss_when_take_profit_is_none(self, config):
		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=95.0,
			take_profit=None,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=105.0,
			bar_low=94.0,
			bar_close=98.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(95.0)

	def test_no_stop_and_no_target_means_no_exit(self, config):
		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=None,
			take_profit=None,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=120.0,
			bar_low=80.0,
			bar_close=100.0,
			config=config,
		)

		assert result == ExitCheckResult(hit=False)


class TestTrailingStop:
	def test_long_trailing_stop_replaces_looser_fixed_stop(self):
		config = BacktestConfig()

		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=95.0,
			take_profit=120.0,
			trailing_stop=100.0,
			bar_open=105.0,
			bar_high=110.0,
			bar_low=99.0,
			bar_close=105.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TRAILING_STOP
		assert result.fill_price == pytest.approx(100.0)

	def test_long_fixed_stop_remains_when_trailing_is_looser(self):
		config = BacktestConfig()

		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=100.0,
			take_profit=120.0,
			trailing_stop=95.0,
			bar_open=105.0,
			bar_high=110.0,
			bar_low=99.0,
			bar_close=105.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(100.0)

	def test_short_trailing_stop_replaces_looser_fixed_stop(self):
		config = BacktestConfig()

		result = check_stop_and_target(
			side=Side.SHORT,
			stop_loss=105.0,
			take_profit=80.0,
			trailing_stop=100.0,
			bar_open=95.0,
			bar_high=101.0,
			bar_low=90.0,
			bar_close=95.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TRAILING_STOP
		assert result.fill_price == pytest.approx(100.0)

	def test_short_fixed_stop_remains_when_trailing_is_looser(self):
		config = BacktestConfig()

		result = check_stop_and_target(
			side=Side.SHORT,
			stop_loss=100.0,
			take_profit=80.0,
			trailing_stop=105.0,
			bar_open=95.0,
			bar_high=101.0,
			bar_low=90.0,
			bar_close=95.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(100.0)

	def test_trailing_stop_can_be_used_without_fixed_stop(self):
		config = BacktestConfig()

		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=None,
			take_profit=120.0,
			trailing_stop=100.0,
			bar_open=105.0,
			bar_high=110.0,
			bar_low=99.0,
			bar_close=105.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TRAILING_STOP
		assert result.fill_price == pytest.approx(100.0)

	def test_trailing_stop_equal_to_fixed_stop_is_stop_loss(self):
		config = BacktestConfig()

		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=100.0,
			take_profit=120.0,
			trailing_stop=100.0,
			bar_open=105.0,
			bar_high=110.0,
			bar_low=99.0,
			bar_close=105.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(100.0)


class TestAmbiguousBarPolicy:
	@pytest.mark.parametrize(
		"side,stop_loss,take_profit,bar_high,bar_low",
		[
			(Side.LONG, 95.0, 110.0, 111.0, 94.0),
			(Side.SHORT, 105.0, 90.0, 106.0, 89.0),
		],
	)
	def test_conservative_policy_prefers_stop_loss(
		self,
		side,
		stop_loss,
		take_profit,
		bar_high,
		bar_low,
	):
		config = BacktestConfig(
			ambiguous_bar_policy=AmbiguousBarPolicy.CONSERVATIVE,
		)

		result = check_stop_and_target(
			side=side,
			stop_loss=stop_loss,
			take_profit=take_profit,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=bar_high,
			bar_low=bar_low,
			bar_close=100.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(stop_loss)

	@pytest.mark.parametrize(
		"side,stop_loss,take_profit,bar_high,bar_low",
		[
			(Side.LONG, 95.0, 110.0, 111.0, 94.0),
			(Side.SHORT, 105.0, 90.0, 106.0, 89.0),
		],
	)
	def test_optimistic_policy_prefers_take_profit(
		self,
		side,
		stop_loss,
		take_profit,
		bar_high,
		bar_low,
	):
		config = BacktestConfig(
			ambiguous_bar_policy=AmbiguousBarPolicy.OPTIMISTIC,
		)

		result = check_stop_and_target(
			side=side,
			stop_loss=stop_loss,
			take_profit=take_profit,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=bar_high,
			bar_low=bar_low,
			bar_close=100.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TAKE_PROFIT
		assert result.fill_price == pytest.approx(take_profit)

	@pytest.mark.parametrize(
		"side,stop_loss,take_profit,bar_high,bar_low",
		[
			(Side.LONG, 95.0, 110.0, 111.0, 94.0),
			(Side.SHORT, 105.0, 90.0, 106.0, 89.0),
		],
	)
	def test_skip_policy_keeps_position_open(
		self,
		side,
		stop_loss,
		take_profit,
		bar_high,
		bar_low,
	):
		config = BacktestConfig(
			ambiguous_bar_policy=AmbiguousBarPolicy.SKIP,
		)

		result = check_stop_and_target(
			side=side,
			stop_loss=stop_loss,
			take_profit=take_profit,
			trailing_stop=None,
			bar_open=100.0,
			bar_high=bar_high,
			bar_low=bar_low,
			bar_close=100.0,
			config=config,
		)

		assert result == ExitCheckResult(hit=False)

	def test_conservative_uses_effective_trailing_stop(self):
		config = BacktestConfig(
			ambiguous_bar_policy=AmbiguousBarPolicy.CONSERVATIVE,
		)

		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=95.0,
			take_profit=110.0,
			trailing_stop=100.0,
			bar_open=105.0,
			bar_high=111.0,
			bar_low=99.0,
			bar_close=105.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.STOP_LOSS
		assert result.fill_price == pytest.approx(100.0)

	def test_optimistic_uses_take_profit_with_trailing_stop(self):
		config = BacktestConfig(
			ambiguous_bar_policy=AmbiguousBarPolicy.OPTIMISTIC,
		)

		result = check_stop_and_target(
			side=Side.LONG,
			stop_loss=95.0,
			take_profit=110.0,
			trailing_stop=100.0,
			bar_open=105.0,
			bar_high=111.0,
			bar_low=99.0,
			bar_close=105.0,
			config=config,
		)

		assert result.hit is True
		assert result.reason is ExitReason.TAKE_PROFIT
		assert result.fill_price == pytest.approx(110.0)
