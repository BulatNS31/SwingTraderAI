import pytest
from pydantic import ValidationError

from swingtraderai.backtesting.config import (
	AmbiguousBarPolicy,
	BacktestConfig,
	EntryMode,
	PositionSizingMode,
	StopLossMode,
	TakeProfitMode,
)


class TestBacktestConfigDefaults:
	def test_default_values(self):
		config = BacktestConfig()

		assert config.initial_capital == 100_000.0
		assert config.warmup_bars == 50

		assert config.entry_mode == EntryMode.NEXT_OPEN
		assert config.ambiguous_bar_policy == AmbiguousBarPolicy.CONSERVATIVE
		assert config.allow_short is False

		assert config.commission_pct == 0.0005
		assert config.slippage_pct == 0.0005
		assert config.fixed_commission == 0.0

		assert config.position_sizing_mode == (PositionSizingMode.FIXED_PERCENT_EQUITY)
		assert config.position_size == 1.0
		assert config.risk_per_trade == 0.01
		assert config.max_position_pct == 0.25
		assert config.max_positions == 1

		assert config.stop_loss_mode == StopLossMode.FIXED_PCT
		assert config.stop_loss_pct == 0.02
		assert config.stop_loss_atr_mult == 1.5

		assert config.take_profit_mode == TakeProfitMode.RR_RATIO
		assert config.take_profit_pct == 0.04
		assert config.take_profit_atr_mult == 3.0
		assert config.risk_reward_ratio == 2.0

		assert config.trailing_stop is False
		assert config.trailing_stop_pct is None
		assert config.trailing_stop_atr_mult is None

		assert config.max_bars_in_trade is None

		assert config.use_ml is False
		assert config.signal_threshold == 5
		assert config.signal_types_long == ("BUY", "STRONG_BUY")
		assert config.signal_types_short == ("SELL", "STRONG_SELL")

		assert config.model_version is None
		assert config.notes is None

	def test_default_config_is_long_only(self):
		config = BacktestConfig()

		assert config.allow_short is False

	def test_default_entry_mode_is_next_open(self):
		config = BacktestConfig()

		assert config.entry_mode is EntryMode.NEXT_OPEN

	def test_default_ambiguous_bar_policy_is_conservative(self):
		config = BacktestConfig()

		assert config.ambiguous_bar_policy is AmbiguousBarPolicy.CONSERVATIVE


class TestEnums:
	def test_entry_mode_values(self):
		assert EntryMode.NEXT_OPEN.value == "next_open"
		assert EntryMode.CURRENT_CLOSE.value == "current_close"

	def test_ambiguous_bar_policy_values(self):
		assert AmbiguousBarPolicy.CONSERVATIVE.value == "conservative"
		assert AmbiguousBarPolicy.OPTIMISTIC.value == "optimistic"
		assert AmbiguousBarPolicy.SKIP.value == "skip"

	def test_position_sizing_mode_values(self):
		assert PositionSizingMode.FIXED_QUANTITY.value == "fixed_quantity"
		assert PositionSizingMode.FIXED_PERCENT_EQUITY.value == "fixed_percent_equity"
		assert PositionSizingMode.RISK_BASED.value == "risk_based"

	def test_stop_loss_mode_values(self):
		assert StopLossMode.FIXED_PCT.value == "fixed_pct"
		assert StopLossMode.ATR_MULTIPLE.value == "atr_multiple"
		assert StopLossMode.SIGNAL.value == "signal"

	def test_take_profit_mode_values(self):
		assert TakeProfitMode.FIXED_PCT.value == "fixed_pct"
		assert TakeProfitMode.ATR_MULTIPLE.value == "atr_multiple"
		assert TakeProfitMode.SIGNAL.value == "signal"
		assert TakeProfitMode.RR_RATIO.value == "rr_ratio"


class TestBacktestConfigValidation:
	@pytest.mark.parametrize(
		"field,value",
		[
			("initial_capital", 0),
			("initial_capital", -1),
			("warmup_bars", -1),
			("commission_pct", -0.001),
			("slippage_pct", -0.001),
			("fixed_commission", -1),
			("position_size", 0),
			("position_size", -1),
			("risk_per_trade", 0),
			("risk_per_trade", 1.01),
			("max_position_pct", 0),
			("max_position_pct", 1.01),
			("max_positions", 0),
			("stop_loss_pct", 0),
			("stop_loss_atr_mult", 0),
			("take_profit_pct", 0),
			("take_profit_atr_mult", 0),
			("risk_reward_ratio", 0),
			("signal_threshold", 0),
			("signal_threshold", 11),
		],
	)
	def test_invalid_field_values_are_rejected(self, field, value):
		with pytest.raises(ValidationError):
			BacktestConfig(**{field: value})

	@pytest.mark.parametrize(
		"field,value",
		[
			("initial_capital", 0.01),
			("warmup_bars", 0),
			("commission_pct", 0),
			("slippage_pct", 0),
			("fixed_commission", 0),
			("position_size", 0.0001),
			("risk_per_trade", 1.0),
			("max_position_pct", 1.0),
			("max_positions", 1),
			("signal_threshold", 1),
			("signal_threshold", 10),
		],
	)
	def test_boundary_values_are_accepted(self, field, value):
		config = BacktestConfig(**{field: value})

		assert getattr(config, field) == value

	def test_extra_fields_are_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(unknown_option=True)

	def test_invalid_entry_mode_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(entry_mode="invalid")

	def test_invalid_ambiguous_bar_policy_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(ambiguous_bar_policy="invalid")


class TestTrailingStopValidation:
	def test_trailing_stop_disabled_without_parameters_is_valid(self):
		config = BacktestConfig(
			trailing_stop=False,
			trailing_stop_pct=None,
			trailing_stop_atr_mult=None,
		)

		assert config.trailing_stop is False

	def test_trailing_stop_requires_configuration(self):
		with pytest.raises(
			ValidationError,
			match="trailing_stop=True requires",
		):
			BacktestConfig(
				trailing_stop=True,
				trailing_stop_pct=None,
				trailing_stop_atr_mult=None,
			)

	def test_trailing_stop_with_percentage_is_valid(self):
		config = BacktestConfig(
			trailing_stop=True,
			trailing_stop_pct=0.02,
		)

		assert config.trailing_stop is True
		assert config.trailing_stop_pct == 0.02

	def test_trailing_stop_with_atr_multiple_is_valid(self):
		config = BacktestConfig(
			trailing_stop=True,
			trailing_stop_atr_mult=2.0,
		)

		assert config.trailing_stop is True
		assert config.trailing_stop_atr_mult == 2.0

	def test_trailing_stop_can_have_both_parameters(self):
		config = BacktestConfig(
			trailing_stop=True,
			trailing_stop_pct=0.02,
			trailing_stop_atr_mult=2.0,
		)

		assert config.trailing_stop_pct == 0.02
		assert config.trailing_stop_atr_mult == 2.0

	def test_negative_trailing_stop_pct_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(
				trailing_stop=True,
				trailing_stop_pct=-0.01,
			)

	def test_zero_trailing_stop_pct_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(
				trailing_stop=True,
				trailing_stop_pct=0,
			)

	def test_negative_trailing_stop_atr_multiple_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(
				trailing_stop=True,
				trailing_stop_atr_mult=-1,
			)

	def test_zero_trailing_stop_atr_multiple_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(
				trailing_stop=True,
				trailing_stop_atr_mult=0,
			)


class TestSignalHelpers:
	@pytest.fixture
	def config(self):
		return BacktestConfig()

	@pytest.mark.parametrize(
		"signal_type",
		["BUY", "STRONG_BUY"],
	)
	def test_is_long_signal(self, config, signal_type):
		assert config.is_long_signal(signal_type) is True

	@pytest.mark.parametrize(
		"signal_type",
		["SELL", "STRONG_SELL"],
	)
	def test_sell_signal_is_not_long_signal(self, config, signal_type):
		assert config.is_long_signal(signal_type) is False

	@pytest.mark.parametrize(
		"signal_type",
		["SELL", "STRONG_SELL"],
	)
	def test_is_short_signal(self, config, signal_type):
		assert config.is_short_signal(signal_type) is True

	@pytest.mark.parametrize(
		"signal_type",
		["BUY", "STRONG_BUY"],
	)
	def test_buy_signal_is_not_short_signal(self, config, signal_type):
		assert config.is_short_signal(signal_type) is False

	@pytest.mark.parametrize(
		"signal_type",
		["HOLD", "UNKNOWN", "", "buy", "sell"],
	)
	def test_unknown_signal_type_is_neither_long_nor_short(
		self,
		config,
		signal_type,
	):
		assert config.is_long_signal(signal_type) is False
		assert config.is_short_signal(signal_type) is False


class TestCustomConfiguration:
	def test_custom_execution_configuration(self):
		config = BacktestConfig(
			initial_capital=50_000,
			warmup_bars=100,
			entry_mode=EntryMode.CURRENT_CLOSE,
			ambiguous_bar_policy=AmbiguousBarPolicy.OPTIMISTIC,
			allow_short=True,
			commission_pct=0.001,
			slippage_pct=0.002,
		)

		assert config.initial_capital == 50_000
		assert config.warmup_bars == 100
		assert config.entry_mode is EntryMode.CURRENT_CLOSE
		assert config.ambiguous_bar_policy is AmbiguousBarPolicy.OPTIMISTIC
		assert config.allow_short is True
		assert config.commission_pct == 0.001
		assert config.slippage_pct == 0.002

	def test_custom_position_sizing_configuration(self):
		config = BacktestConfig(
			position_sizing_mode=PositionSizingMode.RISK_BASED,
			position_size=10,
			risk_per_trade=0.02,
			max_position_pct=0.5,
			max_positions=3,
		)

		assert config.position_sizing_mode is PositionSizingMode.RISK_BASED
		assert config.position_size == 10
		assert config.risk_per_trade == 0.02
		assert config.max_position_pct == 0.5
		assert config.max_positions == 3

	def test_custom_stop_and_target_configuration(self):
		config = BacktestConfig(
			stop_loss_mode=StopLossMode.ATR_MULTIPLE,
			stop_loss_atr_mult=2.5,
			take_profit_mode=TakeProfitMode.ATR_MULTIPLE,
			take_profit_atr_mult=4.0,
		)

		assert config.stop_loss_mode is StopLossMode.ATR_MULTIPLE
		assert config.stop_loss_atr_mult == 2.5
		assert config.take_profit_mode is TakeProfitMode.ATR_MULTIPLE
		assert config.take_profit_atr_mult == 4.0

	def test_optional_metadata(self):
		config = BacktestConfig(
			model_version="v1.2.3",
			notes="test configuration",
		)

		assert config.model_version == "v1.2.3"
		assert config.notes == "test configuration"

	def test_max_bars_in_trade(self):
		config = BacktestConfig(max_bars_in_trade=10)

		assert config.max_bars_in_trade == 10

	def test_zero_max_bars_in_trade_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(max_bars_in_trade=0)

	def test_negative_max_bars_in_trade_is_rejected(self):
		with pytest.raises(ValidationError):
			BacktestConfig(max_bars_in_trade=-1)
