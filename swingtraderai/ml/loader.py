from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

import joblib

from swingtraderai.schemas.prediction import ModelDataSchema, ModelMetadata

try:
	from swingtraderai.core.config import settings

	_DEFAULT_MODELS_DIR = Path(getattr(settings, "MODELS_DIR", "models"))
except Exception:
	_DEFAULT_MODELS_DIR = Path("models")

REQUIRED_ARTIFACT_KEYS = ("model", "scaler", "features")


def _models_root() -> Path:
	"""Корень каталога моделей (абсолютный путь)."""
	root = _DEFAULT_MODELS_DIR
	if not root.is_absolute():
		root = Path.cwd() / root
	return root


def _ticker_model_dir(ticker_id: UUID) -> Path:
	return _models_root() / "xgboost" / str(ticker_id)


def _validate_artifact(data: Any, path: Path) -> Dict[str, Any]:
	"""Проверить, что joblib-артефакт — dict с нужными ключами."""
	if not isinstance(data, dict):
		raise TypeError(
			f"Артефакт {path} должен быть dict, получен {type(data).__name__}"
		)
	missing = [k for k in REQUIRED_ARTIFACT_KEYS if k not in data]
	if missing:
		raise KeyError(
			f"В артефакте {path} нет обязательных ключей: {missing}. "
			f"Есть: {sorted(data.keys())}"
		)
	return data


def _pick_latest(files: List[Path]) -> Path:
	"""Выбрать самый свежий файл: по mtime, при равенстве — по имени."""
	return max(files, key=lambda p: (p.stat().st_mtime, p.name))


def load_latest_model(
	ticker_id: UUID,
	timeframe: str = "1h",
	*,
	models_dir: Optional[Path] = None,
) -> ModelDataSchema:
	"""Загрузить последнюю bar-level XGBoost-модель для ticker + timeframe.

	Ожидаемый путь:
	{MODELS_DIR}/xgboost/{ticker_id}/{ticker_id}_{timeframe}_*.joblib

	Артефакт joblib:
	{"model": ..., "scaler": ..., "features": list[str], ...}
	"""
	base = models_dir if models_dir is not None else _ticker_model_dir(ticker_id)
	if not base.exists():
		raise FileNotFoundError(
			f"Директория моделей для тикера {ticker_id} не найдена: {base}"
		)

	pattern = f"{ticker_id}_{timeframe}_*.joblib"
	files = list(base.glob(pattern))
	if not files:
		raise FileNotFoundError(
			f"Модель для {ticker_id} / {timeframe} ещё не обучена "
			f"(искали {base / pattern})"
		)

	latest_file = _pick_latest(files)
	raw = joblib.load(latest_file)
	data = _validate_artifact(raw, latest_file)

	features = list(data.get("features") or [])

	metadata = ModelMetadata(
		ticker_id=ticker_id,
		timeframe=timeframe,
		model_path=str(latest_file),
		created_at=datetime.fromtimestamp(latest_file.stat().st_mtime),
		features=features,
	)

	return ModelDataSchema(
		model=data["model"],
		scaler=data["scaler"],
		features=features,
		metadata=metadata,
	)


def load_latest_model_cached(
	ticker_id: UUID,
	timeframe: str = "1h",
) -> ModelDataSchema:
	"""Обёртка с кэшем по (ticker, timeframe, mtime latest-файла)."""
	base = _ticker_model_dir(ticker_id)
	files = (
		list(base.glob(f"{ticker_id}_{timeframe}_*.joblib")) if base.exists() else []
	)
	mtime = max((f.stat().st_mtime for f in files), default=0.0)
	return _cached_load(str(ticker_id), timeframe, mtime)


@lru_cache(maxsize=64)
def _cached_load(ticker_id: str, timeframe: str, mtime: float) -> ModelDataSchema:
	# mtime в ключе → после перезаписи joblib кэш инвалидируется
	return load_latest_model(UUID(ticker_id), timeframe)


def clear_model_cache() -> None:
	"""Сброс LRU-кэша (тесты / после batch-train)."""
	_cached_load.cache_clear()
