from datetime import datetime

import pandas as pd
import pytest

from swingtraderai.backtesting.config import (
	BacktestConfig,
	StopLossMode,
	TakeProfitMode,
)
from swingtraderai.backtesting.models import Side
from swingtraderai.backtesting.signal_generator import (
	SignalGenerator,
	_calculate_composite_signal,
	_default_sl_tp,
	_extract_signal_value,
	_side_from_signal_type,
	_simple_atr,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_config(**overrides):
	values = {
		"initial_capital": 100_000.0,
		"stop_loss_mode": StopLossMode.FIXED_PCT,
		"stop_loss_pct": 0.05,
		"take_profit_mode": TakeProfitMode.FIXED_PCT,
		"take_profit_pct": 0.10,
	}
	values.update(overrides)
	return BacktestConfig(**values)


def make_ohlcv(
	prices,
	*,
	high_offset=1.0,
	low_offset=1.0,
):
	return pd.DataFrame(
		{
			"open": prices,
			"high": [p + high_offset for p in prices],
			"low": [p - low_offset for p in prices],
			"close": prices,
			"volume": [1_000.0] * len(prices),
		}
	)


def make_generator(monkeypatch, config=None):
	"""
	Disable real indicator-registry loading.

	This keeps unit tests independent from the live indicator system.
	"""
	monkeypatch.setattr(
		SignalGenerator,
		"_try_load_registry",
		lambda self: None,
	)

	return SignalGenerator(config or make_config())


# ---------------------------------------------------------------------------
# _extract_signal_value
# ---------------------------------------------------------------------------


class TestExtractSignalValue:
	def test_reads_signal_value_attribute(self):
		result = type("Result", (), {"signal_value": 1.5})()

		assert _extract_signal_value(result) == pytest.approx(1.5)

	def test_reads_signal_attribute_strong_buy(self):
		result = type("Result", (), {"signal": "STRONG_BUY"})()

		assert _extract_signal_value(result) == pytest.approx(2.0)

	def test_reads_signal_attribute_buy(self):
		result = type("Result", (), {"signal": "BUY"})()

		assert _extract_signal_value(result) == pytest.approx(1.0)

	def test_reads_signal_attribute_neutral(self):
		result = type("Result", (), {"signal": "NEUTRAL"})()

		assert _extract_signal_value(result) == pytest.approx(0.0)

	def test_reads_signal_attribute_sell(self):
		result = type("Result", (), {"signal": "SELL"})()

		assert _extract_signal_value(result) == pytest.approx(-1.0)

	def test_reads_signal_attribute_strong_sell(self):
		result = type("Result", (), {"signal": "STRONG_SELL"})()

		assert _extract_signal_value(result) == pytest.approx(-2.0)

	@pytest.mark.parametrize(
		("signal", "expected"),
		[
			("bullish", 1.0),
			("bearish", -1.0),
		],
	)
	def test_reads_lowercase_signal_values(self, signal, expected):
		result = type("Result", (), {"signal": signal})()

		assert _extract_signal_value(result) == pytest.approx(expected)

	def test_unknown_signal_attribute_returns_zero(self):
		result = type("Result", (), {"signal": "UNKNOWN"})()

		assert _extract_signal_value(result) == 0.0

	def test_reads_signal_value_from_dict(self):
		assert _extract_signal_value({"signal_value": 1.75}) == pytest.approx(1.75)

	def test_reads_signal_from_dict(self):
		assert _extract_signal_value({"signal": "SELL"}) == pytest.approx(-1.0)

	def test_unknown_dict_signal_returns_zero(self):
		assert _extract_signal_value({"signal": "WHATEVER"}) == 0.0

	@pytest.mark.parametrize(
		("value", "expected"),
		[
			(1, 1.0),
			(-2, -2.0),
			(1.5, 1.5),
			(0.0, 0.0),
		],
	)
	def test_numeric_values_are_converted_to_float(
		self,
		value,
		expected,
	):
		assert _extract_signal_value(value) == pytest.approx(expected)

	@pytest.mark.parametrize(
		"value",
		[
			None,
			"BUY",
			[],
			(),
			object(),
		],
	)
	def test_unsupported_values_return_zero(self, value):
		assert _extract_signal_value(value) == 0.0

	def test_signal_value_attribute_has_priority_over_signal(self):
		result = type(
			"Result",
			(),
			{
				"signal_value": 2.0,
				"signal": "SELL",
			},
		)()

		assert _extract_signal_value(result) == pytest.approx(2.0)

	def test_dict_signal_value_has_priority_over_signal(self):
		result = {
			"signal_value": 2.0,
			"signal": "SELL",
		}

		assert _extract_signal_value(result) == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# _calculate_composite_signal
# ---------------------------------------------------------------------------


class TestCalculateCompositeSignal:
	def test_empty_results_are_neutral(self):
		result = _calculate_composite_signal({})

		assert result == (
			"NEUTRAL",
			1,
			"Нет данных от индикаторов",
		)

	def test_zero_signals_are_neutral(self):
		result = _calculate_composite_signal(
			{
				"rsi": {"signal_value": 0},
				"ema": {"signal_value": 0},
			}
		)

		assert result == (
			"NEUTRAL",
			1,
			"Сигналы отсутствуют",
		)

	def test_buy_dominates(self):
		signal_type, strength, message = _calculate_composite_signal(
			{
				"rsi": {"signal_value": 1.0},
				"ema": {"signal_value": 0.5},
				"macd": {"signal_value": -0.5},
			}
		)

		assert signal_type == "BUY"
		assert strength == 7
		assert "Бычий сигнал" in message
		assert "7/10" in message

	def test_strong_buy(self):
		signal_type, strength, message = _calculate_composite_signal(
			{
				"rsi": {"signal_value": 2.0},
				"ema": {"signal_value": 1.0},
			}
		)

		assert signal_type == "STRONG_BUY"
		assert strength == 10
		assert "Сильный бычий сигнал" in message

	def test_sell_dominates(self):
		signal_type, strength, message = _calculate_composite_signal(
			{
				"rsi": {"signal_value": -1.0},
				"ema": {"signal_value": -0.5},
				"macd": {"signal_value": 0.5},
			}
		)

		assert signal_type == "SELL"
		assert strength == 7
		assert "Медвежий сигнал" in message

	def test_strong_sell(self):
		signal_type, strength, message = _calculate_composite_signal(
			{
				"rsi": {"signal_value": -2.0},
				"ema": {"signal_value": -1.0},
			}
		)

		assert signal_type == "STRONG_SELL"
		assert strength == 10
		assert "Сильный медвежий сигнал" in message

	def test_equal_buy_and_sell_is_neutral(self):
		result = _calculate_composite_signal(
			{
				"buy": {"signal_value": 1.0},
				"sell": {"signal_value": -1.0},
			}
		)

		assert result == (
			"NEUTRAL",
			5,
			"Рынок в нейтральном состоянии",
		)

	def test_strength_is_capped_at_ten(self):
		signal_type, strength, _ = _calculate_composite_signal(
			{
				"a": {"signal_value": 100.0},
			}
		)

		assert signal_type == "STRONG_BUY"
		assert strength == 10

	def test_negative_values_contribute_to_sell_score(self):
		signal_type, strength, _ = _calculate_composite_signal(
			{
				"a": -1.0,
				"b": -2.0,
			}
		)

		assert signal_type == "STRONG_SELL"
		assert strength == 10


# ---------------------------------------------------------------------------
# _side_from_signal_type
# ---------------------------------------------------------------------------


class TestSideFromSignalType:
	@pytest.mark.parametrize(
		("signal_type", "expected"),
		[
			("BUY", Side.LONG),
			("STRONG_BUY", Side.LONG),
			("SELL", Side.SHORT),
			("STRONG_SELL", Side.SHORT),
			("NEUTRAL", Side.NEUTRAL),
			("UNKNOWN", Side.NEUTRAL),
			("", Side.NEUTRAL),
		],
	)
	def test_maps_signal_type_to_side(self, signal_type, expected):
		assert _side_from_signal_type(signal_type) is expected


# ---------------------------------------------------------------------------
# _default_sl_tp
# ---------------------------------------------------------------------------


class TestDefaultSlTp:
	def test_neutral_has_no_sl_or_tp(self):
		config = make_config()

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.NEUTRAL,
			config=config,
		)

		assert sl is None
		assert tp is None

	def test_fixed_pct_long(self):
		config = make_config(
			stop_loss_pct=0.05,
			take_profit_pct=0.10,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.LONG,
			config=config,
		)

		assert sl == pytest.approx(95.0)
		assert tp == pytest.approx(110.0)

	def test_fixed_pct_short(self):
		config = make_config(
			stop_loss_pct=0.05,
			take_profit_pct=0.10,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.SHORT,
			config=config,
		)

		assert sl == pytest.approx(105.0)
		assert tp == pytest.approx(90.0)

	def test_atr_stop_and_target_long(self):
		config = make_config(
			stop_loss_mode=StopLossMode.ATR_MULTIPLE,
			stop_loss_atr_mult=2.0,
			take_profit_mode=TakeProfitMode.ATR_MULTIPLE,
			take_profit_atr_mult=3.0,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.LONG,
			config=config,
			atr=5.0,
		)

		assert sl == pytest.approx(90.0)
		assert tp == pytest.approx(115.0)

	def test_atr_stop_and_target_short(self):
		config = make_config(
			stop_loss_mode=StopLossMode.ATR_MULTIPLE,
			stop_loss_atr_mult=2.0,
			take_profit_mode=TakeProfitMode.ATR_MULTIPLE,
			take_profit_atr_mult=3.0,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.SHORT,
			config=config,
			atr=5.0,
		)

		assert sl == pytest.approx(110.0)
		assert tp == pytest.approx(85.0)

	def test_atr_stop_is_not_created_without_valid_atr(self):
		config = make_config(
			stop_loss_mode=StopLossMode.ATR_MULTIPLE,
			stop_loss_atr_mult=2.0,
			take_profit_mode=TakeProfitMode.FIXED_PCT,
			take_profit_pct=0.10,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.LONG,
			config=config,
			atr=None,
		)

		assert sl is None
		assert tp == pytest.approx(110.0)

	@pytest.mark.parametrize("atr", [0.0, -1.0])
	def test_non_positive_atr_is_ignored(self, atr):
		config = make_config(
			stop_loss_mode=StopLossMode.ATR_MULTIPLE,
			stop_loss_atr_mult=2.0,
			take_profit_mode=TakeProfitMode.ATR_MULTIPLE,
			take_profit_atr_mult=3.0,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.LONG,
			config=config,
			atr=atr,
		)

		assert sl is None
		assert tp is None

	def test_rr_target_for_long(self):
		config = make_config(
			stop_loss_mode=StopLossMode.FIXED_PCT,
			stop_loss_pct=0.05,
			take_profit_mode=TakeProfitMode.RR_RATIO,
			risk_reward_ratio=2.0,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.LONG,
			config=config,
		)

		assert sl == pytest.approx(95.0)
		assert tp == pytest.approx(110.0)

	def test_rr_target_for_short(self):
		config = make_config(
			stop_loss_mode=StopLossMode.FIXED_PCT,
			stop_loss_pct=0.05,
			take_profit_mode=TakeProfitMode.RR_RATIO,
			risk_reward_ratio=2.0,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.SHORT,
			config=config,
		)

		assert sl == pytest.approx(105.0)
		assert tp == pytest.approx(90.0)

	def test_rr_target_is_not_created_without_stop_loss(self):
		config = make_config(
			stop_loss_mode=StopLossMode.ATR_MULTIPLE,
			take_profit_mode=TakeProfitMode.RR_RATIO,
			risk_reward_ratio=2.0,
		)

		sl, tp = _default_sl_tp(
			entry_ref=100.0,
			side=Side.LONG,
			config=config,
			atr=None,
		)

		assert sl is None
		assert tp is None


# ---------------------------------------------------------------------------
# _simple_atr
# ---------------------------------------------------------------------------


class TestSimpleAtr:
	def test_returns_none_when_history_is_too_short(self):
		df = make_ohlcv(range(14))

		assert _simple_atr(df, window=14) is None

	def test_calculates_atr(self):
		# Constant true range of 2.
		prices = [100.0] * 16
		df = pd.DataFrame(
			{
				"high": [101.0] * 16,
				"low": [99.0] * 16,
				"close": prices,
			}
		)

		assert _simple_atr(df, window=14) == pytest.approx(2.0)

	def test_uses_previous_close_for_true_range(self):
		df = pd.DataFrame(
			{
				"high": [
					100.0,
					100.0,
					110.0,
				],
				"low": [
					100.0,
					100.0,
					110.0,
				],
				"close": [
					100.0,
					100.0,
					110.0,
				],
			}
		)

		# Need a small window to expose the gap calculation.
		atr = _simple_atr(df, window=2)

		assert atr == pytest.approx(5.0)

	def test_returns_float(self):
		prices = [100.0] * 16
		df = pd.DataFrame(
			{
				"high": [102.0] * 16,
				"low": [98.0] * 16,
				"close": prices,
			}
		)

		result = _simple_atr(df, window=14)

		assert isinstance(result, float)


# ---------------------------------------------------------------------------
# SignalGenerator initialization
# ---------------------------------------------------------------------------


class TestSignalGeneratorInitialization:
	def test_registry_is_none_when_loading_is_disabled(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		assert generator._registry is None


# ---------------------------------------------------------------------------
# SignalGenerator.generate
# ---------------------------------------------------------------------------


class TestSignalGeneratorGenerate:
	def test_empty_history_returns_neutral_signal(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		timestamp = datetime(2025, 1, 1)

		signal = generator.generate(
			history=pd.DataFrame(),
			ticker="AAPL",
			timeframe="1h",
			bar_timestamp=timestamp,
		)

		assert signal.side is Side.NEUTRAL
		assert signal.signal_type == "NEUTRAL"
		assert signal.signal_score == pytest.approx(1.0)
		assert signal.entry_reference_price == pytest.approx(0.0)
		assert signal.timestamp == timestamp
		assert signal.ticker == "AAPL"
		assert signal.timeframe == "1h"
		assert signal.stop_loss is None
		assert signal.take_profit is None

	def test_columns_are_normalized_to_lowercase(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		received_columns = []

		class FakeIndicator:
			def calculate(self, history):
				received_columns.append(list(history.columns))
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		history = pd.DataFrame(
			{
				"Open": [100.0, 101.0],
				"HIGH": [102.0, 103.0],
				"Low": [99.0, 100.0],
				"CLOSE": [101.0, 102.0],
				"Volume": [1000, 1000],
			}
		)

		signal = generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 2),
		)

		assert received_columns == [["open", "high", "low", "close", "volume"]]
		assert signal.side is Side.LONG

	def test_generate_uses_only_supplied_history(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		observed_lengths = []

		class FakeIndicator:
			def calculate(self, history):
				observed_lengths.append(len(history))
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		history = make_ohlcv([100.0, 101.0, 102.0])

		generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 3),
		)

		assert observed_lengths == [3]

	def test_generator_does_not_mutate_input_columns(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		history = pd.DataFrame(
			{
				"Open": [100.0],
				"HIGH": [101.0],
				"LOW": [99.0],
				"CLOSE": [100.0],
			}
		)

		original_columns = list(history.columns)

		generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 1),
		)

		assert list(history.columns) == original_columns

	def test_registry_indicators_are_used(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 2.0}

		class FakeRegistry:
			_indicators = {
				"indicator_a": FakeIndicator(),
				"indicator_b": FakeIndicator(),
			}

		generator._registry = FakeRegistry()

		history = make_ohlcv([100.0, 101.0])

		signal = generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 2),
		)

		assert signal.side is Side.LONG
		assert signal.signal_type == "STRONG_BUY"
		assert signal.signal_score == pytest.approx(10.0)
		assert signal.indicators_used == [
			"indicator_a",
			"indicator_b",
		]

	def test_failing_indicator_is_skipped(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		class BrokenIndicator:
			def calculate(self, history):
				raise RuntimeError("broken")

		class WorkingIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {
				"broken": BrokenIndicator(),
				"working": WorkingIndicator(),
			}

		generator._registry = FakeRegistry()

		history = make_ohlcv([100.0, 101.0])

		signal = generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 2),
		)

		assert signal.side is Side.LONG
		assert signal.indicators_used == ["working"]

	def test_signal_contains_last_close_as_entry_reference_price(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		history = make_ohlcv([100.0, 105.0, 110.0])

		signal = generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 3),
		)

		assert signal.entry_reference_price == pytest.approx(110.0)

	def test_fixed_sl_tp_are_added_to_generated_signal(
		self,
		monkeypatch,
	):
		config = make_config(
			stop_loss_pct=0.05,
			take_profit_pct=0.10,
		)
		generator = make_generator(monkeypatch, config)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		signal = generator.generate(
			make_ohlcv([100.0]),
			"AAPL",
			"1h",
			datetime(2025, 1, 1),
		)

		assert signal.side is Side.LONG
		assert signal.stop_loss == pytest.approx(95.0)
		assert signal.take_profit == pytest.approx(110.0)

	def test_ml_probability_is_none_when_ml_enabled_but_stub_returns_none(
		self,
		monkeypatch,
	):
		config = make_config(use_ml=True)
		generator = make_generator(monkeypatch, config)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		signal = generator.generate(
			make_ohlcv([100.0]),
			"AAPL",
			"1h",
			datetime(2025, 1, 1),
		)

		assert signal.ml_probability is None

	def test_ml_predictor_is_called_when_ml_is_enabled(
		self,
		monkeypatch,
	):
		config = make_config(use_ml=True)
		generator = make_generator(monkeypatch, config)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		calls = []

		def fake_predict(hist, ticker, timeframe):
			calls.append((len(hist), ticker, timeframe))
			return 0.73

		monkeypatch.setattr(
			generator,
			"_optional_ml_predict",
			fake_predict,
		)

		signal = generator.generate(
			make_ohlcv([100.0, 101.0]),
			"AAPL",
			"1h",
			datetime(2025, 1, 2),
		)

		assert signal.ml_probability == pytest.approx(0.73)
		assert calls == [(2, "AAPL", "1h")]

	def test_regime_is_added_for_long_history(
		self,
		monkeypatch,
	):
		config = make_config()
		generator = make_generator(monkeypatch, config)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		prices = [100.0] * 30
		prices[-1] = 103.0

		signal = generator.generate(
			make_ohlcv(prices),
			"AAPL",
			"1h",
			datetime(2025, 1, 30),
		)

		assert signal.market_regime in {
			"uptrend",
			"downtrend",
			"range",
			"high_vol",
		}

	def test_regime_is_none_for_short_history(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		signal = generator.generate(
			make_ohlcv([100.0] * 29),
			"AAPL",
			"1h",
			datetime(2025, 1, 29),
		)

		assert signal.market_regime is None


# ---------------------------------------------------------------------------
# Fallback indicators
# ---------------------------------------------------------------------------


class TestFallbackIndicators:
	def test_fallback_has_no_indicators_with_very_short_history(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0] * 10)

		results, used = generator._fallback_indicators(history)

		assert results == {}
		assert used == []

	def test_fallback_adds_rsi_after_15_bars(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0] * 15)

		results, used = generator._fallback_indicators(history)

		assert "rsi" in results
		assert "rsi" in used

	def test_fallback_adds_ema_after_21_bars(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0] * 21)

		results, used = generator._fallback_indicators(history)

		assert "ema_cross" in results
		assert "ema_cross" in used

	def test_fallback_rsi_is_neutral_for_flat_prices(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0] * 20)

		results, used = generator._fallback_indicators(history)

		assert results["rsi"]["signal"] == "NEUTRAL"
		assert results["rsi"]["signal_value"] == pytest.approx(0.0)

	def test_fallback_ema_is_neutral_without_cross(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0] * 25)

		results, used = generator._fallback_indicators(history)

		assert results["ema_cross"]["signal"] == "NEUTRAL"
		assert results["ema_cross"]["signal_value"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------


class TestInferRegime:
	def test_short_history_returns_none(self, monkeypatch):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0] * 29)

		assert generator._infer_regime(history) is None

	def test_flat_market_is_range(self, monkeypatch):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0] * 30)

		assert generator._infer_regime(history) == "range"

	def test_strong_uptrend(self, monkeypatch):
		generator = make_generator(monkeypatch)

		prices = list(range(100, 130))
		history = make_ohlcv(prices)

		assert generator._infer_regime(history) == "uptrend"

	def test_strong_downtrend(self, monkeypatch):
		generator = make_generator(monkeypatch)

		prices = list(range(130, 100, -1))
		history = make_ohlcv(prices)

		assert generator._infer_regime(history) == "downtrend"

	def test_high_volatility_has_priority_over_trend(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		prices = [
			100,
			103,
			97,
			105,
			95,
			110,
			90,
			115,
			85,
			120,
			80,
			125,
			75,
			130,
			70,
			135,
			65,
			140,
			60,
			145,
			55,
			150,
			50,
			155,
			45,
			160,
			40,
			165,
			35,
			170,
		]

		history = make_ohlcv(prices)

		assert generator._infer_regime(history) == "high_vol"


# ---------------------------------------------------------------------------
# Point-in-time / look-ahead protection
# ---------------------------------------------------------------------------


class TestPointInTimeBehavior:
	def test_indicator_receives_only_history_passed_to_generate(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		seen_closes = []

		class FakeIndicator:
			def calculate(self, history):
				seen_closes.append(history["close"].tolist())
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		full_history = make_ohlcv([100.0, 101.0, 102.0, 103.0, 104.0])

		generator.generate(
			full_history.iloc[:3],
			"AAPL",
			"1h",
			datetime(2025, 1, 3),
		)

		assert seen_closes == [[100.0, 101.0, 102.0]]

	def test_future_rows_do_not_reach_indicator(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		max_seen_close = []

		class FakeIndicator:
			def calculate(self, history):
				max_seen_close.append(history["close"].max())
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		history = make_ohlcv([100.0, 101.0, 102.0, 999.0])

		generator.generate(
			history.iloc[:3],
			"AAPL",
			"1h",
			datetime(2025, 1, 3),
		)

		assert max_seen_close == [102.0]

	def test_generate_uses_last_row_as_decision_bar(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		class FakeIndicator:
			def calculate(self, history):
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		history = make_ohlcv([100.0, 101.0, 105.0])

		signal = generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 3),
		)

		assert signal.entry_reference_price == pytest.approx(105.0)

	def test_indicator_gets_copy_not_original_dataframe(
		self,
		monkeypatch,
	):
		generator = make_generator(monkeypatch)

		original = None
		received = None

		class FakeIndicator:
			def calculate(self, history):
				nonlocal received
				received = history
				return {"signal_value": 1.0}

		class FakeRegistry:
			_indicators = {"fake": FakeIndicator()}

		generator._registry = FakeRegistry()

		history = make_ohlcv([100.0, 101.0])

		original = history

		generator.generate(
			history,
			"AAPL",
			"1h",
			datetime(2025, 1, 2),
		)

		assert received is not original


# ---------------------------------------------------------------------------
# ML stub
# ---------------------------------------------------------------------------


class TestOptionalMlPredict:
	def test_stub_returns_none(self, monkeypatch):
		generator = make_generator(monkeypatch)

		history = make_ohlcv([100.0])

		assert (
			generator._optional_ml_predict(
				history,
				"AAPL",
				"1h",
			)
			is None
		)
