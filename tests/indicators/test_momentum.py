import pandas as pd

from swingtraderai.indicators.base import IndicatorResult
from swingtraderai.indicators.momentum.momentum import (
	CCIIndicator,
	MACDIndicator,
	RSIIndicator,
	StochasticIndicator,
)
from swingtraderai.indicators.registry import registry


def test_rsi_basic(sample_ohlcv):
	indicator = RSIIndicator("rsi14", length=14)
	result = indicator.calculate(sample_ohlcv)

	assert isinstance(result, IndicatorResult)
	assert result.name == "rsi14"
	assert isinstance(result.value, (float, type(None)))
	assert result.metadata["length"] == 14


def test_rsi_different_lengths(sample_ohlcv):
	for length in [7, 14]:
		indicator = RSIIndicator(f"rsi{length}", length=length)
		result = indicator.calculate(sample_ohlcv)

		assert result.name == f"rsi{length}"
		assert result.metadata["length"] == length


def test_rsi_on_small_dataframe():
	small_df = pd.DataFrame({"close": range(10)})
	indicator = RSIIndicator("rsi14", length=14)
	result = indicator.calculate(small_df)

	assert result.value is None


def test_macd_basic(sample_ohlcv):
	indicator = MACDIndicator()
	result = indicator.calculate(sample_ohlcv)

	assert isinstance(result, IndicatorResult)
	assert result.name == "macd"
	assert isinstance(result.value, dict)
	assert "macd" in result.value
	assert "signal" in result.value
	assert "histogram" in result.value
	assert result.metadata["type"] == "macd"


def test_macd_on_small_dataframe():
	small_df = pd.DataFrame({"close": range(20)})
	indicator = MACDIndicator()
	result = indicator.calculate(small_df)

	assert result.value is None


def test_stochastic_basic(sample_ohlcv):
	indicator = StochasticIndicator()
	result = indicator.calculate(sample_ohlcv)

	assert isinstance(result, IndicatorResult)
	assert result.name == "stoch"
	assert isinstance(result.value, dict)
	assert "k" in result.value
	assert "d" in result.value
	assert result.metadata["type"] == "stochastic"


def test_stochastic_missing_columns():
	df = pd.DataFrame({"close": range(50)})  # нет high/low
	indicator = StochasticIndicator()
	result = indicator.calculate(df)

	assert result.value is None


def test_cci_basic(sample_ohlcv):
	indicator = CCIIndicator("cci20", length=20)
	result = indicator.calculate(sample_ohlcv)

	assert isinstance(result, IndicatorResult)
	assert result.name == "cci20"
	assert isinstance(result.value, (float, type(None)))
	assert result.metadata["length"] == 20


def test_cci_different_lengths(sample_ohlcv):
	indicator = CCIIndicator("cci14", length=14)
	result = indicator.calculate(sample_ohlcv)

	assert result.name == "cci14"


def test_momentum_indicators_are_registered():
	"""Проверяем, что все momentum индикаторы зарегистрированы"""
	registered = registry.list_all()

	expected = ["rsi", "rsi7", "rsi14", "macd", "stoch", "cci", "cci14"]

	for name in expected:
		assert name in registered, f"Индикатор {name} не зарегистрирован"


def test_rsi_in_registry():
	rsi = registry.get("rsi14")
	assert rsi is not None
	assert rsi.category == "momentum"


def test_macd_in_registry():
	macd = registry.get("macd")
	assert macd is not None
	assert macd.category == "momentum"


def test_all_momentum_indicators_on_empty_dataframe():
	empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])

	indicators = [
		RSIIndicator(),
		MACDIndicator(),
		StochasticIndicator(),
		CCIIndicator(),
	]

	for ind in indicators:
		result = ind.calculate(empty_df)
		assert result.value is None or isinstance(result.value, dict)


def test_rsi_with_custom_length_via_kwargs(sample_ohlcv):
	indicator = RSIIndicator("rsi_custom", length=14)
	result = indicator.calculate(sample_ohlcv, length=21)

	assert result.metadata["length"] == 21
