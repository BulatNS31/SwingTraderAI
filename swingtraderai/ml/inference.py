from typing import Any, List, Optional
from uuid import UUID

import numpy as np
import pandas as pd

from swingtraderai.indicators.matrix import add_all_indicators
from swingtraderai.ml.loader import load_latest_model
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA
from swingtraderai.schemas.prediction import (
	ModelDataSchema,
	PredictionRequest,
	PredictionResult,
)


def _resolve_feature_cols(model_data: ModelDataSchema) -> List[str]:
	"""Список фичей модели: из артефакта или дефолт схемы."""
	if model_data.features:
		return list(model_data.features)
	return list(MARKET_DATA_SCHEMA.MODEL_FEATURE_COLUMNS)


def _last_bar_timestamp(df: pd.DataFrame) -> Optional[Any]:
	time_col = MARKET_DATA_SCHEMA.TIME_COLUMN
	if time_col in df.columns and len(df) > 0:
		ts = df[time_col].iloc[-1]
		return ts if pd.notna(ts) else None
	return None


async def predict(
	ticker_id: UUID,
	current_df: pd.DataFrame,
	timeframe: str = "1h",
) -> PredictionResult:
	"""Bar-level прогноз на последний бар.

	Пайплайн: load model → add_all_indicators → scale → predict_proba.
	Это legacy-путь (не setup-ML). Для сетапов см. ml/setup_inference.py.
	"""
	model_data: ModelDataSchema = load_latest_model(ticker_id, timeframe)
	model = model_data.model
	scaler = model_data.scaler
	feature_cols = _resolve_feature_cols(model_data)

	processed_df = add_all_indicators(current_df, timeframe=timeframe)

	if processed_df.empty:
		return PredictionResult(
			ticker_id=ticker_id,
			timeframe=timeframe,
			probability=0.0,
			prediction="flat",
			confidence=0.0,
			error="Недостаточно данных для расчета индикаторов",
			features_used=feature_cols,
			data_points=0,
			timestamp=None,
		)

	missing_features = [c for c in feature_cols if c not in processed_df.columns]
	if missing_features:
		return PredictionResult(
			ticker_id=ticker_id,
			timeframe=timeframe,
			probability=0.0,
			prediction="flat",
			confidence=0.0,
			error=f"Отсутствуют фичи: {missing_features}",
			features_used=feature_cols,
			data_points=len(processed_df),
			timestamp=_last_bar_timestamp(processed_df),
		)

	X_raw = processed_df[feature_cols].iloc[[-1]].replace([np.inf, -np.inf], np.nan)

	if X_raw.isna().any(axis=None):
		return PredictionResult(
			ticker_id=ticker_id,
			timeframe=timeframe,
			probability=0.0,
			prediction="flat",
			confidence=0.0,
			error="NaN в признаках последнего бара (индикаторы не прогрелись)",
			features_used=feature_cols,
			data_points=len(processed_df),
			timestamp=_last_bar_timestamp(processed_df),
		)

	X_scaled = scaler.transform(X_raw)
	proba = model.predict_proba(X_scaled)[0]
	# Бинарная модель: класс 1 = «бычий» исход
	prob = float(proba[1]) if len(proba) > 1 else float(proba[0])

	if prob > MARKET_DATA_SCHEMA.LONG_THRESHOLD:
		prediction = "long"
	elif prob < MARKET_DATA_SCHEMA.SHORT_THRESHOLD:
		# Эвристика: низкая P(long) трактуется как short (не отдельный класс)
		prediction = "short"
	else:
		prediction = "flat"

	confidence = float(prob if prob >= 0.5 else 1.0 - prob)

	return PredictionResult(
		ticker_id=ticker_id,
		timeframe=timeframe,
		probability=prob,
		prediction=prediction,
		confidence=confidence,
		timestamp=_last_bar_timestamp(processed_df),
		features_used=feature_cols,
		data_points=len(processed_df),
	)


async def predict_with_request(
	request: PredictionRequest,
	current_df: pd.DataFrame,
) -> PredictionResult:
	"""Обёртка: валидация BASE_COLUMNS + predict."""
	required_cols = set(MARKET_DATA_SCHEMA.BASE_COLUMNS)
	missing = required_cols - set(current_df.columns)
	if missing:
		raise ValueError(f"Отсутствуют базовые колонки: {sorted(missing)}")

	return await predict(request.ticker_id, current_df, request.timeframe)
