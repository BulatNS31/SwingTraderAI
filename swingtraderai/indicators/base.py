from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

import pandas as pd
from pydantic import BaseModel, Field

from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA


def calculate_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
	"""Расчет Average True Range (ATR)."""
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]

	tr1 = high - low
	tr2 = (high - close.shift(1)).abs()
	tr3 = (low - close.shift(1)).abs()

	tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
	return tr.rolling(window=window).mean()


class IndicatorResult(BaseModel):
	"""Стандартизированный результат расчёта индикатора"""

	name: str
	value: Any
	signal: Optional[str] = None
	regime: Optional[str] = None
	metadata: Dict[str, Any] = Field(default_factory=dict)


class BaseIndicator(ABC):
	name: str
	category: str
	description: str = ""
	default_params: Dict[str, Any] = {}

	@abstractmethod
	def calculate(
		self, df: pd.DataFrame, **kwargs: Any
	) -> Union[IndicatorResult, pd.Series, Dict[str, Any]]:
		"""Основной метод расчёта."""
		pass

	def interpret(self, value: Any, **kwargs: Any) -> Dict[str, Any]:
		return {"signal": "neutral", "regime": None}
