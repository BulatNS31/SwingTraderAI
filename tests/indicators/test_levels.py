import numpy as np
import pandas as pd
import pytest

from swingtraderai.indicators.levels import (
	add_key_levels_indicators,
	calculate_classic_pivot_points,
	detect_fractal_highs_lows,
	rolling_support_resistance_zones,
)


def test_detect_fractal_highs_lows(sample_ohlcv):
	highs, lows = detect_fractal_highs_lows(sample_ohlcv, window=2)

	assert isinstance(highs, pd.Series)
	assert isinstance(lows, pd.Series)
	assert len(highs) == len(sample_ohlcv)
	assert len(lows) == len(sample_ohlcv)

	# Должны быть найдены хотя бы некоторые фракталы
	assert highs.notna().sum() > 0
	assert lows.notna().sum() > 0

	# Проверка корректности фрактала high
	fractal_high_idx = highs.first_valid_index()
	if fractal_high_idx is not None:
		start = max(0, fractal_high_idx - 2)
		end = fractal_high_idx + 3
		window_slice = sample_ohlcv["high"].iloc[start:end]
		assert sample_ohlcv.loc[fractal_high_idx, "high"] == window_slice.max()


def test_detect_fractal_small_window(sample_ohlcv):
	highs, lows = detect_fractal_highs_lows(sample_ohlcv, window=1)
	assert highs.notna().sum() > 5
	assert lows.notna().sum() > 5


def test_detect_fractal_on_empty_dataframe():
	empty_df = pd.DataFrame(columns=["open", "high", "low", "close", "volume", "time"])
	highs, lows = detect_fractal_highs_lows(empty_df, window=2)

	assert isinstance(highs, pd.Series)
	assert isinstance(lows, pd.Series)
	assert len(highs) == 0
	assert len(lows) == 0


def test_rolling_support_resistance_zones(sample_ohlcv):
	result = rolling_support_resistance_zones(
		sample_ohlcv, window=40, min_touches=2, price_tolerance=0.005
	)

	assert isinstance(result, pd.DataFrame)
	assert list(result.columns) == [
		"support_level",
		"resistance_level",
		"touches_support",
		"touches_resistance",
	]
	assert len(result) == len(sample_ohlcv)
	assert result.index.equals(sample_ohlcv.index)

	# После прогрева окна должны быть значения
	assert result["support_level"].iloc[40:].notna().sum() > 0
	assert result["resistance_level"].iloc[40:].notna().sum() > 0


def test_rolling_support_resistance_small_data():
	small_df = pd.DataFrame(
		{
			"high": np.random.uniform(4900, 5100, 25),
			"low": np.random.uniform(4850, 5050, 25),
			"close": np.random.uniform(4880, 5080, 25),
		}
	)

	result = rolling_support_resistance_zones(small_df, window=15, min_touches=3)

	assert result["support_level"].iloc[:20].isna().sum() > 10  # начало окна
	assert result["resistance_level"].iloc[:20].isna().sum() > 10


def test_calculate_classic_pivot_points(sample_ohlcv):
	pivots = calculate_classic_pivot_points(sample_ohlcv, timeframe="D")

	assert isinstance(pivots, pd.DataFrame)
	assert {"pp", "r1", "s1", "r2", "s2"}.issubset(pivots.columns)
	assert pivots["pp"].notna().sum() > 0


def test_pivot_points_single_day():
	df = pd.DataFrame(
		{
			"open": [5000],
			"high": [5050],
			"low": [4980],
			"close": [5020],
			"volume": [10000],
			"time": [pd.Timestamp("2025-05-01")],
		}
	)

	pivots = calculate_classic_pivot_points(df, timeframe="D")

	assert not pivots.empty
	assert "pp" in pivots.columns
	assert pivots["pp"].iloc[0] == pytest.approx(5016.67, rel=1e-2)


def test_add_key_levels_indicators(sample_ohlcv):
	result = add_key_levels_indicators(
		sample_ohlcv, fractal_window=2, sr_window=50, pivot_tf="D"
	)

	expected_cols = {
		"open",
		"high",
		"low",
		"close",
		"volume",
		"fractal_high",
		"fractal_low",
		"support_level",
		"resistance_level",
		"pp",
		"r1",
		"s1",
		"r2",
		"s2",
	}

	assert isinstance(result, pd.DataFrame)
	assert expected_cols.issubset(result.columns)

	# Проверяем, что данные не потерялись
	assert result["close"].notna().sum() == sample_ohlcv["close"].notna().sum()

	# Должны быть найдены уровни
	assert result["fractal_high"].notna().sum() > 0
	assert result["fractal_low"].notna().sum() > 0
	assert result["pp"].notna().sum() > 10


def test_add_key_levels_preserves_data(sample_ohlcv):
	original_close = sample_ohlcv["close"].copy()

	result = add_key_levels_indicators(sample_ohlcv, fractal_window=2, sr_window=30)

	# Исходные данные не должны измениться
	pd.testing.assert_series_equal(
		result["close"].iloc[: len(original_close)], original_close, check_names=False
	)


def test_add_key_levels_on_small_dataframe():
	small_df = pd.DataFrame(
		{
			"open": np.random.rand(30) * 100 + 5000,
			"high": np.random.rand(30) * 100 + 5050,
			"low": np.random.rand(30) * 100 + 4950,
			"close": np.random.rand(30) * 100 + 5020,
			"volume": np.random.randint(1000, 10000, 30),
			"time": pd.date_range("2025-01-01", periods=30, freq="h"),
		}
	)

	result = add_key_levels_indicators(small_df, fractal_window=2, sr_window=20)

	assert isinstance(result, pd.DataFrame)
	assert len(result) == 30
	assert "pp" in result.columns
	assert "fractal_high" in result.columns
