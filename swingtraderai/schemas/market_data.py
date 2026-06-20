from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Optional, Set, TypeAlias
from uuid import UUID

import numpy as np
import numpy.typing as npt
import pandas as pd
import pandas_ta as pdt
from pydantic import BaseModel, ConfigDict

ArrayLike: TypeAlias = npt.ArrayLike
NDArrayInt: TypeAlias = npt.NDArray[np.int_]

_ = pdt


class MarketDataBase(BaseModel):
	timeframe: Optional[str] = None
	open: Optional[Decimal] = None
	high: Optional[Decimal] = None
	low: Optional[Decimal] = None
	close: Optional[Decimal] = None
	volume: Optional[Decimal] = None


class MarketQuoteSchema(BaseModel):
	symbol: str
	price: Decimal
	change_percent: float
	volume: Optional[float] = None
	market_type: str
	updated_at: datetime

	model_config = ConfigDict(from_attributes=True)


class MarketDataOut(MarketDataBase):
	id: UUID
	ticker_id: UUID
	timestamp: datetime
	created_at: datetime

	model_config = ConfigDict(from_attributes=True)


@dataclass(frozen=True)
class MarketDataSchema:
	"""Единый источник истины для схемы рыночных данных"""

	BASE_COLUMNS: List[str] = field(
		default_factory=lambda: [
			"time",
			"open",
			"high",
			"low",
			"close",
			"volume",
			"timeframe",
		]
	)
	HIGH_COLUMN: str = "high"
	LOW_COLUMN: str = "low"
	CLOSE_COLUMN: str = "close"
	SQL_COLUMN_TYPES: Dict[str, str] = field(
		default_factory=lambda: {
			"open": "DECIMAL",
			"high": "DECIMAL",
			"low": "DECIMAL",
			"close": "DECIMAL",
			"volume": "DECIMAL",
			"time": "TIMESTAMP",
			"timestamp": "TIMESTAMP",
		}
	)

	# Колонки, которые требуют конвертации в Decimal
	DECIMAL_COLUMNS: Set[str] = field(
		default_factory=lambda: {"open", "high", "low", "close", "volume"}
	)

	# Колонки-идентификаторы в БД
	ID_COLUMNS: Set[str] = field(default_factory=lambda: {"ticker_id", "id"})

	# Обязательные колонки для вставки
	REQUIRED_INSERT_COLUMNS: Set[str] = field(
		default_factory=lambda: {"ticker_id", "time"}
	)

	# Обязательные индикаторы
	REQUIRED_INDICATORS: Set[str] = field(
		default_factory=lambda: {"sma_10", "rsi_14", "atr_14"}
	)

	# Колонки для индекса уникальности
	UNIQUE_CONSTRAINT_COLUMNS: List[str] = field(
		default_factory=lambda: ["ticker_id", "timeframe", "time"]
	)

	# Колонки для обучения модели
	MODEL_FEATURE_COLUMNS: List[str] = field(
		default_factory=lambda: ["open", "high", "low", "close", "volume"]
	)

	# Целевая колонка для обучения
	TARGET_COLUMN: str = "target"

	# Временная колонка
	TIME_COLUMN: str = "time"

	# Колонки для дропа при подготовке X
	DROP_COLUMNS_FOR_TRAINING: Set[str] = field(
		default_factory=lambda: {"target", "time", "future_return", "close"}
	)

	@property
	def all_columns(self) -> List[str]:
		"""Все возможные колонки"""
		return self.BASE_COLUMNS + list(self.ID_COLUMNS) + ["timestamp"]

	def get_sql_type(self, column: str) -> str:
		"""Получить SQL тип для колонки"""
		return self.SQL_COLUMN_TYPES.get(column, "TEXT")

	def is_decimal_column(self, column: str) -> bool:
		"""Проверка, нужно ли конвертировать в Decimal"""
		return column in self.DECIMAL_COLUMNS

	def normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
		df = df.copy()
		df.columns = [col.lower() for col in df.columns]
		rename_map = {
			"datetime": "time",
			"timestamp": "time",
		}

		df = df.rename(columns=rename_map)

		return df

	def validate_base_columns(self, df: pd.DataFrame) -> None:
		missing = set(self.BASE_COLUMNS) - set(df.columns)
		if missing:
			raise ValueError(f"Отсутствуют колонки: {missing}")


MARKET_DATA_SCHEMA = MarketDataSchema()
