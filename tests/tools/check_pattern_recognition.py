"""
Локальная проверка Pattern Recognition.

Поток:
OHLCV → extract_candle_features / detect_bulkowski_patterns
	→ статистика паттернов
	→ forward returns
	→ PatternRecognitionIndicator на последнем баре
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from swingtraderai.indicators.pattern_recognition import (
	PatternRecognitionIndicator,
	detect_bulkowski_patterns,
	extract_candle_features,
)
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


load_dotenv()


PATTERN_COLUMNS = [
	"double_bottom",
	"double_top",
	"hammer",
	"shooting_star",
	"bullish_engulfing",
	"bearish_engulfing",
]

BULLISH_PATTERNS = {
	"double_bottom",
	"hammer",
	"bullish_engulfing",
}

BEARISH_PATTERNS = {
	"double_top",
	"shooting_star",
	"bearish_engulfing",
}


def load_ohlcv_csv(path: str, timeframe: str = "1D") -> pd.DataFrame:
	"""Универсальная загрузка CSV (date/time + OHLCV)."""
	df = pd.read_csv(path)

	df.columns = [c.lower().strip() for c in df.columns]

	df = df.drop(
		columns=[c for c in df.columns if c.startswith("unnamed")],
		errors="ignore",
	)

	time_src = "date" if "date" in df.columns else "time"

	if time_src not in df.columns:
		raise ValueError(f"Нет date/time в {path}. Колонки: {list(df.columns)}")

	df["time"] = pd.to_datetime(df[time_src], utc=True).dt.tz_localize(None)

	df = df.sort_values("time").drop_duplicates("time").reset_index(drop=True)

	required = [
		"open",
		"high",
		"low",
		"close",
		"volume",
	]

	missing = [c for c in required if c not in df.columns]

	if missing:
		raise ValueError(f"Нет колонок {missing}")

	df = df[
		[
			"time",
			"open",
			"high",
			"low",
			"close",
			"volume",
		]
	].copy()

	df["timeframe"] = timeframe

	return MARKET_DATA_SCHEMA.normalize_columns(df)


def load_amzn_kaggle(timeframe: str = "1D") -> pd.DataFrame:
	"""Опционально: тот же Kaggle AMZN."""
	print("[1] Импортирую kagglehub...", flush=True)

	import kagglehub

	print("[2] Проверяю Kaggle credentials...", flush=True)

	if not os.environ.get("KAGGLE_USERNAME") or not os.environ.get("KAGGLE_KEY"):
		raise RuntimeError("Нужны KAGGLE_USERNAME / KAGGLE_KEY в .env")

	print("[3] Скачиваю Kaggle dataset...", flush=True)

	path = kagglehub.dataset_download("abdulmoiz12/amazon-stock-data-2025")

	print(
		f"[4] Dataset downloaded: {path}",
		flush=True,
	)

	files = os.listdir(path)

	print(
		f"[5] Files: {files}",
		flush=True,
	)

	csv_files = [f for f in files if f.endswith(".csv")]

	if not csv_files:
		raise RuntimeError(f"CSV не найден. Файлы: {files}")

	csv_file = csv_files[0]

	print(
		f"[6] Loading CSV: {csv_file}",
		flush=True,
	)

	return load_ohlcv_csv(
		os.path.join(path, csv_file),
		timeframe=timeframe,
	)


def classify_pattern(pattern: str) -> str:
	"""Направление паттерна."""
	if pattern in BULLISH_PATTERNS:
		return "bullish"

	if pattern in BEARISH_PATTERNS:
		return "bearish"

	return "neutral"


def pattern_events(
	patterns: pd.DataFrame,
) -> pd.DataFrame:
	"""
	Преобразует wide-format паттерны
	в список событий.

	Один бар может содержать несколько паттернов.
	"""
	rows = []

	for i in patterns.index:
		for pattern in PATTERN_COLUMNS:
			if bool(patterns.at[i, pattern]):
				rows.append(
					{
						"index": i,
						"pattern": pattern,
						"direction": classify_pattern(pattern),
					}
				)

	return pd.DataFrame(rows)


def run_check(
	df: pd.DataFrame,
	lookback: int = 20,
	tolerance: float = 0.015,
	slope_window: int = 10,
	forward_horizon: int = 10,
) -> None:
	print("=" * 64)
	print("PATTERN RECOGNITION CHECK")
	print("=" * 64)

	print(f"bars: {len(df):,} | timeframe: {df['timeframe'].iloc[0]}")

	# ---------------------------------------------------------
	# 1. Candle features
	# ---------------------------------------------------------

	features = extract_candle_features(
		df,
		slope_window=slope_window,
	)

	assert len(features) == len(df)

	required_features = [
		"body_ratio",
		"upper_shadow_ratio",
		"lower_shadow_ratio",
		"trend_slope",
		"relative_body_atr",
	]

	for col in required_features:
		assert col in features.columns, f"Нет feature: {col}"

	print("\nCandle features:")
	print(f"  rows: {len(features):,}")

	print(f"  body_ratio non-NaN: {features['body_ratio'].notna().sum():,}")

	print(f"  trend_slope non-NaN: {features['trend_slope'].notna().sum():,}")

	# ---------------------------------------------------------
	# 2. Detect patterns
	# ---------------------------------------------------------

	patterns = detect_bulkowski_patterns(
		df,
		lookback=lookback,
		tolerance=tolerance,
		features=features,
	)

	assert len(patterns) == len(df)

	for col in PATTERN_COLUMNS:
		assert col in patterns.columns, f"Нет pattern column: {col}"

	# ---------------------------------------------------------
	# 3. Pattern statistics
	# ---------------------------------------------------------

	print("\nPattern statistics:")

	total_events = 0

	for pattern in PATTERN_COLUMNS:
		count = int(patterns[pattern].sum())
		ratio = count / len(patterns)

		total_events += count

		print(f"  {pattern:20s} {count:5d} ({ratio:.2%})")

	print(f"\nTotal pattern events: {total_events:,}")

	# ---------------------------------------------------------
	# 4. Bullish / bearish statistics
	# ---------------------------------------------------------

	bullish_mask = patterns[list(BULLISH_PATTERNS)].any(axis=1)

	bearish_mask = patterns[list(BEARISH_PATTERNS)].any(axis=1)

	both_mask = bullish_mask & bearish_mask

	print("\nDirection:")
	print(f"  bullish bars: {int(bullish_mask.sum()):,}")
	print(f"  bearish bars: {int(bearish_mask.sum()):,}")
	print(f"  mixed bars:   {int(both_mask.sum()):,}")

	# ---------------------------------------------------------
	# 5. Event table
	# ---------------------------------------------------------

	events = pattern_events(patterns)

	if events.empty:
		print("\nПаттернов не найдено.")
	else:
		print("\nLast pattern events:")

		event_view = events.copy()

		event_view["time"] = event_view["index"].map(df["time"])

		event_view["close"] = event_view["index"].map(
			df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
		)

		print(
			event_view[
				[
					"time",
					"pattern",
					"direction",
					"close",
				]
			]
			.tail(20)
			.to_string(index=False)
		)

	# ---------------------------------------------------------
	# 6. Forward returns
	# ---------------------------------------------------------

	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]

	fwd = close.shift(-forward_horizon) / close - 1.0

	print(f"\nForward returns ({forward_horizon} bars):")

	for pattern in PATTERN_COLUMNS:
		indices = np.where(patterns[pattern].to_numpy())[0]

		returns = []

		for i in indices:
			if i >= len(df) - forward_horizon:
				continue

			value = fwd.iloc[i]

			if pd.isna(value):
				continue

			direction = classify_pattern(pattern)

			signed_return = float(value)

			if direction == "bearish":
				signed_return *= -1.0

			returns.append(signed_return)

		if not returns:
			print(f"  {pattern:20s} n=0")
			continue

		arr = np.asarray(returns)

		print(
			f"  {pattern:20s} "
			f"n={len(arr):4d} "
			f"mean={arr.mean():7.2%} "
			f"median={np.median(arr):7.2%} "
			f"winrate={(arr > 0).mean():6.1%} "
			f"std={arr.std():7.2%}"
		)

	# ---------------------------------------------------------
	# 7. IndicatorResult
	# ---------------------------------------------------------

	indicator = PatternRecognitionIndicator()

	result = indicator.calculate(
		df,
		lookback=lookback,
		tolerance=tolerance,
		slope_window=slope_window,
	)

	print("\nLast-bar IndicatorResult:")

	print(f"  signal : {result.signal}")

	print(f"  regime : {result.regime}")

	print(f"  value  : {result.value}")

	print(f"  meta   : {result.metadata}")

	# ---------------------------------------------------------
	# 8. Tail
	# ---------------------------------------------------------

	view = pd.concat(
		[
			df[
				[
					MARKET_DATA_SCHEMA.TIME_COLUMN,
					MARKET_DATA_SCHEMA.CLOSE_COLUMN,
				]
			].reset_index(drop=True),
			features[
				[
					"body_ratio",
					"upper_shadow_ratio",
					"lower_shadow_ratio",
					"trend_slope",
				]
			].reset_index(drop=True),
			patterns.reset_index(drop=True),
		],
		axis=1,
	)

	print("\nTail (15 bars):")
	print(view.tail(15).to_string(index=False))

	print("\n✅ check_pattern_recognition завершён")


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Check Pattern Recognition indicator")

	parser.add_argument(
		"--csv",
		type=str,
		default=None,
		help="Путь к OHLCV CSV",
	)

	parser.add_argument(
		"--kaggle-amzn",
		action="store_true",
		help="Взять AMZN с Kaggle",
	)

	parser.add_argument(
		"--timeframe",
		type=str,
		default="1D",
	)

	parser.add_argument(
		"--lookback",
		type=int,
		default=20,
	)

	parser.add_argument(
		"--tolerance",
		type=float,
		default=0.015,
	)

	parser.add_argument(
		"--slope-window",
		type=int,
		default=10,
	)

	parser.add_argument(
		"--horizon",
		type=int,
		default=10,
		help="Forward bars after pattern",
	)

	args = parser.parse_args()

	if args.csv:
		ohlcv = load_ohlcv_csv(
			args.csv,
			timeframe=args.timeframe,
		)

	elif args.kaggle_amzn:
		ohlcv = load_amzn_kaggle(
			timeframe=args.timeframe,
		)

	else:
		print("Укажи --csv path/to/ohlcv.csv или --kaggle-amzn")
		sys.exit(1)

	run_check(
		ohlcv,
		lookback=args.lookback,
		tolerance=args.tolerance,
		slope_window=args.slope_window,
		forward_horizon=args.horizon,
	)
