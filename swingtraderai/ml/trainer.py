from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Generator, List, Optional, Tuple, Union
from uuid import UUID

import joblib
import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler
from sqlalchemy import text
from xgboost import XGBClassifier

from swingtraderai.db.session import get_db
from swingtraderai.indicators.matrix import add_all_indicators
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

try:
	from swingtraderai.core.config import settings

	_MODELS_ROOT = Path(getattr(settings, "MODELS_DIR", "models"))
except Exception:
	_MODELS_ROOT = Path("models")


class PurgedTimeSeriesSplit(TimeSeriesSplit):
	"""TimeSeriesSplit с purge: хвост train отрезается,
	чтобы не пересекаться с target horizon."""

	def __init__(self, n_splits: int = 6, purge_size: int = 12) -> None:
		super().__init__(n_splits=n_splits)
		self.purge_size = purge_size

	def split(
		self,
		X: Any,
		y: Any = None,
		groups: Any = None,
	) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
		for train_idx, test_idx in super().split(X, y, groups):
			if self.purge_size > 0 and len(train_idx) > self.purge_size:
				train_idx = np.array(train_idx[: -self.purge_size])
			yield np.array(train_idx), np.array(test_idx)


def calculate_trading_metrics(
	y_true: Union[NDArray[np.floating], List[float]],
	y_pred_proba: Union[NDArray[np.floating], List[float]],
	threshold: float = 0.5,
) -> Dict[str, float]:
	"""Эвристические WR / PF по сигналам pred > threshold (не реальный PnL)."""
	y_true_arr = np.asarray(y_true)
	y_prob = np.asarray(y_pred_proba)
	y_pred = (y_prob > threshold).astype(int)

	total_trades = int(np.sum(y_pred))
	if total_trades == 0:
		return {"win_rate": 0.0, "total_trades": 0.0, "profit_factor": 0.0}

	winning_trades = int(np.sum((y_pred == 1) & (y_true_arr == 1)))
	win_rate = winning_trades / total_trades

	avg_win_conf = (
		float(np.mean(y_prob[y_true_arr == 1])) if np.any(y_true_arr == 1) else 0.0
	)
	avg_loss_conf = (
		float(np.mean(y_prob[y_true_arr == 0])) if np.any(y_true_arr == 0) else 1.0
	)
	profit_factor = (win_rate * avg_win_conf) / (
		(1.0 - win_rate) * avg_loss_conf + 1e-6
	)

	return {
		"win_rate": float(win_rate),
		"total_trades": float(total_trades),
		"profit_factor": float(profit_factor),
	}


def get_atr_column(df: pd.DataFrame) -> str:
	"""Найти колонку ATR; fallback — простой TR = high - low (не полноценный ATR)."""
	candidates = (
		"atr14",
		"atr_14",
		"atrr_14",
		"ATRr_14",
		"atr",
		"ATR14",
		"ATR_14",
	)
	for col in candidates:
		if col in df.columns:
			return col

	high = MARKET_DATA_SCHEMA.HIGH_COLUMN
	low = MARKET_DATA_SCHEMA.LOW_COLUMN
	if high in df.columns and low in df.columns:
		df["atr_calc"] = (df[high] - df[low]).abs()
		return "atr_calc"

	raise KeyError("ATR column not found and could not be calculated")


def _find_feature(df: pd.DataFrame, patterns: List[str]) -> Optional[str] | None:
	"""Первая колонка, чьё имя содержит один из patterns (без регистра/_)."""
	norm: Dict[str, str] = {c: c.lower().replace("_", "") for c in df.columns}
	for pattern in patterns:
		p = pattern.lower().replace("_", "")
		for col, n in norm.items():
			if p in n:
				return col
	return None


def detect_strong_levels(
	df: pd.DataFrame,
	min_tests: int = 3,
	window: int = 120,
	max_distance_pct: float = 0.08,
) -> pd.DataFrame:
	"""Сильные уровни только на прошлых данных (без center=True и без будущих касаний).

	На каждом баре i:
	- swing high/low в окне [i-window, i) (правый край исключён)
	- число тестов уровня считается только на [0, i]
	"""
	df = df.copy()
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
	n = len(df)

	nearest_level = np.full(n, np.nan)
	level_type = np.array([""] * n, dtype=object)
	level_strength = np.zeros(n, dtype=float)
	dist_to_level = np.zeros(n, dtype=float)

	# Предрасчёт rolling max/min только по прошлому (shift(1) + rolling)
	roll_high = high.shift(1).rolling(window, min_periods=max(5, window // 4)).max()
	roll_low = low.shift(1).rolling(window, min_periods=max(5, window // 4)).min()

	for i in range(window, n):
		c = float(close.iloc[i])
		if c <= 0 or np.isnan(c):
			continue

		candidates: List[Dict[str, Any]] = []

		sh = roll_high.iloc[i]
		sl = roll_low.iloc[i]

		# Тесты уровня только в прошлом [i-window, i)
		hist_high = high.iloc[i - window : i]
		hist_low = low.iloc[i - window : i]

		if pd.notna(sh) and sh > 0:
			tests = int(((hist_high >= sh * 0.995) & (hist_low <= sh * 1.005)).sum())
			if tests >= min_tests and abs(sh - c) / c < max_distance_pct:
				candidates.append(
					{"price": float(sh), "type": "resistance", "tests": tests}
				)

		if pd.notna(sl) and sl > 0:
			tests = int(((hist_high >= sl * 0.995) & (hist_low <= sl * 1.005)).sum())
			if tests >= min_tests and abs(sl - c) / c < max_distance_pct:
				candidates.append(
					{"price": float(sl), "type": "support", "tests": tests}
				)

		if not candidates:
			continue

		best = max(candidates, key=lambda x: int(x["tests"]))
		nearest_level[i] = best["price"]
		level_type[i] = best["type"]
		level_strength[i] = float(best["tests"])
		dist_to_level[i] = (c - best["price"]) / best["price"]

	df["nearest_level"] = nearest_level
	df["level_type"] = level_type
	df["level_strength"] = level_strength
	df["dist_to_level"] = dist_to_level
	return df


def detect_false_breakout(df: pd.DataFrame, min_depth_atr: float = 0.4) -> pd.DataFrame:
	"""Ложные пробои относительно nearest_level (только текущий бар, без look-ahead).

	Признаки:
	- false_breakout, fb_type, fb_depth
	fb_return_bars НЕ считается здесь (это будущее → leakage).
	"""
	df = df.copy()
	atr_col = get_atr_column(df)
	atr = df[atr_col]

	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]

	n = len(df)
	false_breakout = np.zeros(n, dtype=int)
	fb_type = np.array([""] * n, dtype=object)
	fb_depth = np.zeros(n, dtype=float)

	for i in range(len(df)):
		lvl = df["nearest_level"].iloc[i]
		lt = df["level_type"].iloc[i]
		if pd.isna(lvl) or not lt:
			continue

		curr_atr = float(atr.iloc[i]) if pd.notna(atr.iloc[i]) else 0.0
		if curr_atr <= 0:
			continue

		level = float(lvl)

		# Bear trap: прокол support вниз, close обратно выше уровня
		if lt == "support":
			if low.iloc[i] < level * 0.995 and close.iloc[i] > level:
				depth = (level - float(low.iloc[i])) / curr_atr
				if depth > min_depth_atr:
					false_breakout[i] = 1
					fb_type[i] = "bear_trap"
					fb_depth[i] = float(depth)

		# Bull trap: прокол resistance вверх, close обратно ниже уровня
		elif lt == "resistance":
			if high.iloc[i] > level * 1.005 and close.iloc[i] < level:
				depth = (float(high.iloc[i]) - level) / curr_atr
				if depth > min_depth_atr:
					false_breakout[i] = 1
					fb_type[i] = "bull_trap"
					fb_depth[i] = float(depth)

	df["false_breakout"] = false_breakout
	df["fb_type"] = fb_type
	df["fb_depth"] = fb_depth
	return df


def _build_target_on_false_breakouts(
	df: pd.DataFrame,
	horizon: int = 15,
	pt_pct: float = 0.012,
) -> pd.Series:
	"""Target только логика разметки (будущее ок):
	1 если после FB цена ушла в нужную сторону."""
	target = np.full(len(df), np.nan)
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
	high = df[MARKET_DATA_SCHEMA.HIGH_COLUMN]
	low = df[MARKET_DATA_SCHEMA.LOW_COLUMN]

	for i in range(len(df) - horizon):
		if int(df["false_breakout"].iloc[i]) != 1:
			continue

		fb_type = df["fb_type"].iloc[i]
		entry = float(close.iloc[i])
		future_high = float(high.iloc[i + 1 : i + horizon + 1].max())
		future_low = float(low.iloc[i + 1 : i + horizon + 1].min())

		if fb_type == "bear_trap" and future_high > entry * (1.0 + pt_pct):
			target[i] = 1.0
		elif fb_type == "bull_trap" and future_low < entry * (1.0 - pt_pct):
			target[i] = 1.0
		else:
			target[i] = 0.0

	return pd.Series(target, index=df.index, name="target")


def _resolve_feature_frame(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
	"""Собрать матрицу фичей с устойчивыми именами колонок."""
	# alias: каноническое имя → паттерны поиска в df
	wanted: Dict[str, List[str]] = {
		"false_breakout": ["false_breakout"],
		"fb_depth": ["fb_depth"],
		"level_strength": ["level_strength"],
		"dist_to_level": ["dist_to_level"],
		"price_to_level_ratio": ["price_to_level_ratio"],
		"level_strength_rank": ["level_strength_rank"],
		"volume_ratio": ["volume_ratio"],
		"volume_zscore": ["volume_zscore"],
		"volume_spike": ["volume_spike"],
		"rsi14": ["rsi14", "rsi_14", "rsi"],
		"rsi_delta_3": ["rsi_delta_3", "rsidelta3"],
		"macd_hist": ["macd_hist", "macdh"],
		"atr_pct": ["atr_pct", "atrpct"],
		"bb_width": ["bb_width", "bbwidth", "bbb"],
		"returns_5": ["returns_5"],
		"returns_10": ["returns_10"],
		"price_above_ema200": ["price_above_ema200"],
		"ema9_gt_ema21": ["ema9_gt_ema21"],
		"hour": ["hour"],
		"dayofweek": ["dayofweek"],
		"is_session_open": ["is_session_open"],
	}

	cols: Dict[str, pd.Series] = {}
	for canonical, patterns in wanted.items():
		if canonical in df.columns:
			cols[canonical] = df[canonical]
			continue
		found = _find_feature(df, patterns)
		if found is not None:
			cols[canonical] = df[found]

	feature_names = list(cols.keys())
	X = pd.DataFrame(cols, index=df.index)
	return X, feature_names


async def train_model(
	ticker_id: UUID,
	timeframe: str = "1h",
	n_splits: int = 6,
	early_stopping_rounds: int = 80,
	verbose: bool = True,
	horizon: int = 15,
	min_rows: int = 200,
) -> str:
	"""Обучение bar-level XGBoost на Gerchik false-breakout событиях.

	Важно:
	- обучаемся только на строках с false_breakout==1 (размеченный target);
	- fb_return_bars не используется (look-ahead);
	- артефакт сохраняется в models/xgboost/... для совместимости с loader.
	"""
	# ----- load OHLCV -----
	rows = None
	async for session in get_db():
		cols = ", ".join(MARKET_DATA_SCHEMA.BASE_COLUMNS)
		time_col = MARKET_DATA_SCHEMA.TIME_COLUMN
		query = text(
			f"""
			SELECT {cols}
			FROM market_data
			WHERE ticker_id = :ticker_id AND timeframe = :tf
			ORDER BY {time_col}
			"""
		)
		result = await session.execute(
			query, {"ticker_id": str(ticker_id), "tf": timeframe}
		)
		rows = result.fetchall()
		break

	if not rows:
		raise ValueError("Нет данных")

	df = pd.DataFrame(rows, columns=list(MARKET_DATA_SCHEMA.BASE_COLUMNS))
	df[MARKET_DATA_SCHEMA.TIME_COLUMN] = pd.to_datetime(
		df[MARKET_DATA_SCHEMA.TIME_COLUMN]
	)

	# ----- features -----
	df = add_all_indicators(df, timeframe=timeframe)
	df = detect_strong_levels(df, min_tests=3, window=120)
	df = detect_false_breakout(df, min_depth_atr=0.4)

	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
	volume = df[MARKET_DATA_SCHEMA.VOLUME_COLUMN]

	df["returns_5"] = close.pct_change(5)
	df["returns_10"] = close.pct_change(10)
	df["volume_ratio"] = volume / volume.rolling(30).mean()

	nearest = df["nearest_level"] if "nearest_level" in df.columns else close
	df["price_to_level_ratio"] = close / (nearest.replace(0, np.nan) + 1e-8)
	df["level_strength_rank"] = df["level_strength"].rolling(200).rank(pct=True)

	# target (будущее только здесь)
	df["target"] = _build_target_on_false_breakouts(df, horizon=horizon, pt_pct=0.012)

	# только FB-события с меткой
	mask = df["false_breakout"].eq(1) & df["target"].notna()
	df_fb = df.loc[mask].copy()

	if len(df_fb) < min_rows:
		raise ValueError(
			"Мало размеченных false-breakout событий:{len(df_fb)} (нужно ≥ {min_rows})"
		)

	X_all, feature_names = _resolve_feature_frame(df_fb)
	y_all = df_fb["target"].astype(int)

	X_all = X_all.replace([np.inf, -np.inf], np.nan).fillna(0.0)

	if len(X_all) < min_rows:
		raise ValueError(f"Недостаточно данных после фильтрации: {len(X_all)}")

	if verbose:
		print(
			f"FB samples: {len(X_all)} | pos rate: {y_all.mean():.1%} | "
			f"features: {len(feature_names)}"
		)

	# ----- CV -----
	tscv = PurgedTimeSeriesSplit(n_splits=n_splits, purge_size=max(horizon, 5))

	best_model: Optional[XGBClassifier] = None
	best_scaler: Optional[StandardScaler] = None
	best_auc = -1.0
	cv_results: List[Dict[str, float]] = []

	for fold, (train_idx, val_idx) in enumerate(tscv.split(X_all), 1):
		X_train = X_all.iloc[train_idx]
		X_val = X_all.iloc[val_idx]
		y_train = y_all.iloc[train_idx]
		y_val = y_all.iloc[val_idx]

		if y_train.nunique() < 2 or y_val.nunique() < 2:
			if verbose:
				print(f"Fold {fold}: пропуск (один класс в train/val)")
			continue

		scaler = StandardScaler()
		X_train_s = scaler.fit_transform(X_train)
		X_val_s = scaler.transform(X_val)

		pos_ratio = float(y_train.mean())
		spw = max((1.0 - pos_ratio) / pos_ratio, 1.0) if pos_ratio > 0 else 1.0

		model = XGBClassifier(
			n_estimators=1000,
			learning_rate=0.03,
			max_depth=6,
			min_child_weight=5,
			gamma=0.5,
			subsample=0.8,
			colsample_bytree=0.8,
			reg_alpha=0.6,
			reg_lambda=2.0,
			scale_pos_weight=spw,
			eval_metric=["auc", "logloss"],
			tree_method="hist",
			random_state=42,
			max_bin=512,
			early_stopping_rounds=early_stopping_rounds,
		)

		model.fit(
			X_train_s,
			y_train,
			eval_set=[(X_val_s, y_val)],
			verbose=False,
		)

		probs = model.predict_proba(X_val_s)[:, 1]
		auc = float(roc_auc_score(y_val, probs))
		metrics = calculate_trading_metrics(y_val, probs)

		cv_results.append(
			{
				"fold": float(fold),
				"auc": auc,
				"win_rate": metrics["win_rate"],
				"trades": metrics["total_trades"],
				"profit_factor": metrics["profit_factor"],
			}
		)

		if auc > best_auc:
			best_auc = auc
			best_model = model
			best_scaler = scaler

	if best_model is None or best_scaler is None:
		raise RuntimeError("Training failed: no valid fold / model")

	avg_metrics = pd.DataFrame(cv_results).mean(numeric_only=True).to_dict()

	# ----- save (совместимо с loader: models/xgboost/{ticker_id}/) -----
	model_dir = _MODELS_ROOT / "xgboost" / str(ticker_id)
	model_dir.mkdir(parents=True, exist_ok=True)

	timestamp = datetime.now().strftime("%Y%m%d_%H%M")
	path = model_dir / f"{ticker_id}_{timeframe}_{timestamp}.joblib"

	joblib.dump(
		{
			"model": best_model,
			"scaler": best_scaler,
			"features": feature_names,
			"metrics": avg_metrics,
			"ticker_id": str(ticker_id),
			"timeframe": timeframe,
			"strategy": "gerchik_levels_falsebreakout",
			"horizon": horizon,
		},
		path,
		compress=3,
	)

	if verbose:
		print(
			f"✅ Gerchik model | AUC: {avg_metrics.get('auc', 0):.4f} | "
			f"WR: {avg_metrics.get('win_rate', 0):.1%} | "
			f"PF: {avg_metrics.get('profit_factor', 0):.2f} | "
			f"saved: {path}"
		)

	return str(path)
