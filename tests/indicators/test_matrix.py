import numpy as np
import pandas as pd
import pytest

from swingtraderai.indicators.matrix import (
	add_all_indicators,
	add_target,
	engineer_features,
)
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA


@pytest.fixture
def sample_ohlcv_features() -> pd.DataFrame:
	"""Хороший DataFrame для тестирования"""
	np.random.seed(42)
	dates = pd.date_range("2025-03-01", periods=250, freq="h")

	base = np.linspace(5000, 5200, 250) + np.random.normal(0, 20, 250)

	df = pd.DataFrame(
		{
			"time": dates,
			"open": base + np.random.normal(0, 25, 250),
			"high": base + np.random.normal(15, 30, 250),
			"low": base + np.random.normal(-15, 30, 250),
			"close": base + np.random.normal(5, 22, 250),
			"volume": np.random.randint(800, 25000, 250),
			"timeframe": "1h",
		}
	)

	return MARKET_DATA_SCHEMA.normalize_columns(df)


def test_engineer_features_basic(sample_ohlcv_features):
	result = engineer_features(sample_ohlcv_features)

	assert isinstance(result, pd.DataFrame)
	assert len(result) > 100

	cols_lower = {col.lower() for col in result.columns}

	assert any("sma_10" in c for c in cols_lower)
	assert any("ema_9" in c for c in cols_lower)
	assert any("rsi_14" in c for c in cols_lower)
	assert any("atr" in c for c in cols_lower)
	assert "pp" in result.columns
	assert "fractal_high" in result.columns


def test_add_target(sample_ohlcv_features):
	df = engineer_features(sample_ohlcv_features)
	result = add_target(df, horizon=5, use_triple_barrier=False, threshold=0.008)

	assert "future_return" in result.columns
	assert "target" in result.columns
	assert result["target"].isin([0, 1]).all()


def test_add_all_indicators(sample_ohlcv_features):
	result = add_all_indicators(sample_ohlcv_features)

	assert isinstance(result, pd.DataFrame)
	assert "pp" in result.columns
	assert "target" not in result.columns


def test_add_all_indicators_preserves_time(sample_ohlcv_features):
	result = add_all_indicators(sample_ohlcv_features)
	assert "time" in result.columns
	assert pd.api.types.is_datetime64_any_dtype(result["time"])


def test_small_dataframe_handling():
	"""Тест на маленький датафрейм — должен добавлять timeframe"""
	small_df = pd.DataFrame(
		{
			"open": np.random.rand(30) * 100 + 5000,
			"high": np.random.rand(30) * 100 + 5050,
			"low": np.random.rand(30) * 100 + 4950,
			"close": np.random.rand(30) * 100 + 5020,
			"volume": np.random.randint(1000, 10000, 30),
			"time": pd.date_range("2025-01-01", periods=30, freq="h"),
			"timeframe": "1h",
		}
	)

	result = add_all_indicators(small_df)
	assert len(result) > 0


def test_engineer_features_raises_on_missing_columns():
	bad_df = pd.DataFrame(
		{
			"time": pd.date_range("2025-01-01", periods=10),
			"open": range(10),
			"high": range(10),
			"low": range(10),
			"close": range(10),
			"volume": range(10),
			# timeframe отсутствует — должно падать
		}
	)

	with pytest.raises(ValueError):
		engineer_features(bad_df)
