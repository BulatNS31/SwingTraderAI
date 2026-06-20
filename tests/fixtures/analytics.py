import numpy as np
import pandas as pd
import pytest_asyncio

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA


@pytest_asyncio.fixture
def registrations() -> pd.Series:
	"""Серия с датами регистрации пользователей"""
	n_users = 1000
	dates = pd.date_range("2025-01-01", periods=90, freq="D")
	reg_dates = np.random.choice(dates, size=n_users, replace=True)
	return pd.Series(
		reg_dates,
		index=range(n_users),
		name="registration_date",
		dtype="datetime64[ns]",
	)


@pytest_asyncio.fixture
def activity_df() -> pd.DataFrame:
	"""Активность пользователей"""
	dates = pd.date_range("2025-02-01", "2025-03-20", freq="D")

	data = {
		"user_id": [i % 800 for i in range(5000)],
		"activity_date": [dates[i % len(dates)] for i in range(5000)],
	}
	df = pd.DataFrame(data)
	df["activity_date"] = pd.to_datetime(df["activity_date"])
	return df


@pytest_asyncio.fixture
def registration_dict(activity_df, registrations) -> dict:
	"""Словарь user_id -> дата регистрации (для cohort retention)"""
	return registrations.to_dict()


@pytest_asyncio.fixture
def sample_ohlcv() -> pd.DataFrame:
	"""Реалистичный OHLCV DataFrame для тестирования индикаторов и уровней"""
	np.random.seed(42)

	dates = pd.date_range("2025-03-01 00:00", periods=100, freq="h")

	base = np.linspace(5000, 5100, 100) + np.random.normal(0, 8, 100)

	df = pd.DataFrame(
		{
			"time": dates,
			"open": base + np.random.normal(0, 5, 100),
			"high": base + np.random.normal(5, 6, 100),
			"low": base + np.random.normal(-5, 6, 100),
			"close": base + np.random.normal(0, 4, 100),
			"volume": np.random.randint(800, 12000, 100),
			"timeframe": "1h",
		}
	)

	df.loc[df.index[10], "high"] = 5080.0
	df.loc[df.index[15], "high"] = 5125.0
	df.loc[df.index[30], "low"] = 4960.0
	df.loc[df.index[50], "high"] = 5150.0
	df.loc[df.index[70], "low"] = 4925.0
	df.loc[df.index[85], "low"] = 4900.0

	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	df["time"] = pd.to_datetime(df["time"])

	return df
