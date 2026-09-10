import pytest

from swingtraderai.backtesting.config import BacktestConfig
from swingtraderai.backtesting.costs import (
	apply_slippage_to_price,
	commission_cost,
	slippage_cost,
	total_roundtrip_cost,
)


class TestCommissionCost:
	def test_percentage_commission(self):
		config = BacktestConfig(commission_pct=0.001, fixed_commission=0)

		assert commission_cost(10_000, config) == pytest.approx(10.0)

	def test_fixed_commission(self):
		config = BacktestConfig(commission_pct=0, fixed_commission=5)

		assert commission_cost(10_000, config) == pytest.approx(5.0)

	def test_percentage_and_fixed_commission_are_combined(self):
		config = BacktestConfig(
			commission_pct=0.001,
			fixed_commission=5,
		)

		assert commission_cost(10_000, config) == pytest.approx(15.0)

	def test_negative_notional_uses_absolute_value(self):
		config = BacktestConfig(
			commission_pct=0.001,
			fixed_commission=5,
		)

		assert commission_cost(-10_000, config) == pytest.approx(15.0)

	def test_zero_notional_still_has_fixed_commission(self):
		config = BacktestConfig(
			commission_pct=0.001,
			fixed_commission=5,
		)

		assert commission_cost(0, config) == pytest.approx(5.0)

	def test_zero_notional_without_fixed_commission_is_zero(self):
		config = BacktestConfig(
			commission_pct=0.001,
			fixed_commission=0,
		)

		assert commission_cost(0, config) == pytest.approx(0.0)


class TestSlippageCost:
	def test_percentage_slippage(self):
		config = BacktestConfig(slippage_pct=0.001)

		assert slippage_cost(10_000, config) == pytest.approx(10.0)

	def test_negative_notional_uses_absolute_value(self):
		config = BacktestConfig(slippage_pct=0.001)

		assert slippage_cost(-10_000, config) == pytest.approx(10.0)

	def test_zero_notional_is_zero(self):
		config = BacktestConfig(slippage_pct=0.001)

		assert slippage_cost(0, config) == pytest.approx(0.0)

	def test_zero_slippage_is_zero(self):
		config = BacktestConfig(slippage_pct=0)

		assert slippage_cost(10_000, config) == pytest.approx(0.0)


class TestApplySlippageToPrice:
	@pytest.mark.parametrize(
		"price, slip, expected",
		[
			(100.0, 0.001, 100.1),
			(50.0, 0.01, 50.5),
			(200.0, 0.005, 201.0),
		],
	)
	def test_long_entry_price_increases(self, price, slip, expected):
		config = BacktestConfig(slippage_pct=slip)

		result = apply_slippage_to_price(
			price=price,
			side="long",
			is_entry=True,
			config=config,
		)

		assert result == pytest.approx(expected)

	@pytest.mark.parametrize(
		"price, slip, expected",
		[
			(100.0, 0.001, 99.9),
			(50.0, 0.01, 49.5),
			(200.0, 0.005, 199.0),
		],
	)
	def test_long_exit_price_decreases(self, price, slip, expected):
		config = BacktestConfig(slippage_pct=slip)

		result = apply_slippage_to_price(
			price=price,
			side="long",
			is_entry=False,
			config=config,
		)

		assert result == pytest.approx(expected)

	@pytest.mark.parametrize(
		"price, slip, expected",
		[
			(100.0, 0.001, 99.9),
			(50.0, 0.01, 49.5),
			(200.0, 0.005, 199.0),
		],
	)
	def test_short_entry_price_decreases(self, price, slip, expected):
		config = BacktestConfig(slippage_pct=slip)

		result = apply_slippage_to_price(
			price=price,
			side="short",
			is_entry=True,
			config=config,
		)

		assert result == pytest.approx(expected)

	@pytest.mark.parametrize(
		"price, slip, expected",
		[
			(100.0, 0.001, 100.1),
			(50.0, 0.01, 50.5),
			(200.0, 0.005, 201.0),
		],
	)
	def test_short_exit_price_increases(self, price, slip, expected):
		config = BacktestConfig(slippage_pct=slip)

		result = apply_slippage_to_price(
			price=price,
			side="short",
			is_entry=False,
			config=config,
		)

		assert result == pytest.approx(expected)

	def test_unknown_side_leaves_price_unchanged(self):
		config = BacktestConfig(slippage_pct=0.01)

		result = apply_slippage_to_price(
			price=100.0,
			side="unknown",
			is_entry=True,
			config=config,
		)

		assert result == 100.0

	def test_unknown_side_is_unchanged_on_exit(self):
		config = BacktestConfig(slippage_pct=0.01)

		result = apply_slippage_to_price(
			price=100.0,
			side="unknown",
			is_entry=False,
			config=config,
		)

		assert result == 100.0

	def test_zero_slippage_does_not_change_price(self):
		config = BacktestConfig(slippage_pct=0)

		assert apply_slippage_to_price(
			price=100.0,
			side="long",
			is_entry=True,
			config=config,
		) == pytest.approx(100.0)

		assert apply_slippage_to_price(
			price=100.0,
			side="long",
			is_entry=False,
			config=config,
		) == pytest.approx(100.0)

	def test_price_is_unchanged_for_zero_price(self):
		config = BacktestConfig(slippage_pct=0.01)

		assert apply_slippage_to_price(
			price=0,
			side="long",
			is_entry=True,
			config=config,
		) == pytest.approx(0.0)


class TestTotalRoundtripCost:
	def test_roundtrip_cost_sums_both_legs(self):
		config = BacktestConfig(
			commission_pct=0.001,
			fixed_commission=5,
			slippage_pct=0.002,
		)

		entry_notional = 10_000
		exit_notional = 11_000

		# Entry:
		# commission = 10 + 5
		# slippage = 20
		#
		# Exit:
		# commission = 11 + 5
		# slippage = 22
		#
		# Total = 73
		assert total_roundtrip_cost(
			entry_notional,
			exit_notional,
			config,
		) == pytest.approx(73.0)

	def test_roundtrip_cost_uses_absolute_notionals(self):
		config = BacktestConfig(
			commission_pct=0.001,
			fixed_commission=5,
			slippage_pct=0.002,
		)

		positive = total_roundtrip_cost(
			10_000,
			11_000,
			config,
		)

		negative = total_roundtrip_cost(
			-10_000,
			-11_000,
			config,
		)

		assert negative == pytest.approx(positive)

	def test_roundtrip_cost_with_zero_percent_costs(self):
		config = BacktestConfig(
			commission_pct=0,
			fixed_commission=5,
			slippage_pct=0,
		)

		assert total_roundtrip_cost(
			10_000,
			20_000,
			config,
		) == pytest.approx(10.0)

	def test_roundtrip_cost_with_no_costs_is_zero(self):
		config = BacktestConfig(
			commission_pct=0,
			fixed_commission=0,
			slippage_pct=0,
		)

		assert total_roundtrip_cost(
			10_000,
			20_000,
			config,
		) == pytest.approx(0.0)

	def test_roundtrip_cost_is_sum_of_individual_costs(self):
		config = BacktestConfig(
			commission_pct=0.0005,
			fixed_commission=2,
			slippage_pct=0.0005,
		)

		entry_notional = 12_345.67
		exit_notional = 13_579.24

		expected = (
			commission_cost(entry_notional, config)
			+ commission_cost(exit_notional, config)
			+ slippage_cost(entry_notional, config)
			+ slippage_cost(exit_notional, config)
		)

		assert total_roundtrip_cost(
			entry_notional,
			exit_notional,
			config,
		) == pytest.approx(expected)
