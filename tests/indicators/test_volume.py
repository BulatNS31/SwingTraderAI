import numpy as np
import pandas as pd

from swingtraderai.indicators.base import IndicatorResult
from swingtraderai.indicators.registry import registry
from swingtraderai.indicators.volume import (
	ADIndicator,
	ATRIndicator,
	BollingerBandsIndicator,
	DonchianChannelsIndicator,
	OBVIndicator,
	VolumeSMAIndicator,
)


def test_bollinger_bands_basic(sample_ohlcv):
	indicator = BollingerBandsIndicator()
	result = indicator.calculate(sample_ohlcv)

	assert isinstance(result, IndicatorResult)
	assert result.name == "bbands"
	assert isinstance(result.value, dict)
	assert "upper" in result.value
	assert "middle" in result.value
	assert "lower" in result.value
	assert "bandwidth" in result.value
	assert result.metadata["length"] == 20
	assert result.metadata["std"] == 2


def test_atr_basic(sample_ohlcv):
	indicator = ATRIndicator("atr14", length=14)
	result = indicator.calculate(sample_ohlcv)

	assert result.name == "atr14"
	assert isinstance(result.value, (float, type(None)))
	assert result.metadata["length"] == 14


def test_atr_different_lengths(sample_ohlcv):
	for length in [10, 14, 20]:
		indicator = ATRIndicator(f"atr{length}", length=length)
		result = indicator.calculate(sample_ohlcv)
		assert result.metadata["length"] == length


def test_donchian_channels_basic(sample_ohlcv):
	indicator = DonchianChannelsIndicator()
	result = indicator.calculate(sample_ohlcv, length=20)

	assert result.name == "donchian"
	assert isinstance(result.value, dict)
	assert "upper" in result.value
	assert "lower" in result.value
	assert "middle" in result.value
	assert result.metadata["length"] == 20


def test_volume_sma_basic(sample_ohlcv):
	indicator = VolumeSMAIndicator("volume_sma20", length=20)
	result = indicator.calculate(sample_ohlcv)

	assert result.name == "volume_sma20"
	assert isinstance(result.value, (float, type(None)))
	assert result.metadata["length"] == 20


def test_obv_basic(sample_ohlcv):
	indicator = OBVIndicator()
	result = indicator.calculate(sample_ohlcv)

	assert result.name == "obv"
	assert isinstance(result.value, (float, type(None)))


def test_ad_indicator_basic(sample_ohlcv):
	indicator = ADIndicator()
	result = indicator.calculate(sample_ohlcv)

	assert result.name == "ad"
	assert isinstance(result.value, (float, type(None)))


def test_bbands_in_registry():
	ind = registry.get("bbands")
	assert ind is not None
	assert ind.category == "volatility"


def test_atr_in_registry():
	ind = registry.get("atr")
	assert ind is not None
	assert ind.category == "volatility"


def test_obv_in_registry():
	ind = registry.get("obv")
	assert ind is not None
	assert ind.category == "volume"


def test_indicators_on_empty_dataframe():
	empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])

	indicators = [
		BollingerBandsIndicator(),
		ATRIndicator(),
		DonchianChannelsIndicator(),
		VolumeSMAIndicator(),
		OBVIndicator(),
		ADIndicator(),
	]

	for ind in indicators:
		result = ind.calculate(empty_df)
		assert result.value is None or isinstance(result.value, dict)


def test_atr_with_custom_length_via_kwargs(sample_ohlcv):
	indicator = ATRIndicator("atr_custom", length=14)
	result = indicator.calculate(sample_ohlcv, length=21)

	assert result.metadata["length"] == 21


def test_bollinger_on_small_dataframe():
	small_df = pd.DataFrame({"close": np.random.rand(15) * 100 + 5000})
	indicator = BollingerBandsIndicator()
	result = indicator.calculate(small_df)

	assert result is not None


def test_volume_indicators_missing_volume_column():
	df_no_volume = pd.DataFrame(
		{
			"open": [100] * 10,
			"high": [105] * 10,
			"low": [95] * 10,
			"close": [101] * 10,
		}
	)

	indicators = [VolumeSMAIndicator(), OBVIndicator(), ADIndicator()]

	for ind in indicators:
		result = ind.calculate(df_no_volume)
		assert result.value is None
