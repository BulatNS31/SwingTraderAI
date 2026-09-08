"""
Локальная проверка TTM Squeeze (John Carter).

Поток:
OHLCV → calculate_ttm_squeeze → статистика squeeze/fire + сигналы индикатора
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from dotenv import load_dotenv

from swingtraderai.indicators.volatility.ttm_squeeze import (
	TTMSqueezeIndicator,
	calculate_ttm_squeeze,
)
from swingtraderai.schemas.market_data import MARKET_DATA_SCHEMA

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
	sys.path.insert(0, str(ROOT))


load_dotenv()


def load_ohlcv_csv(path: str, timeframe: str = "1D") -> pd.DataFrame:
	"""Универсальная загрузка CSV (date/time + OHLCV)."""
	df = pd.read_csv(path)
	df.columns = [c.lower().strip() for c in df.columns]
	df = df.drop(
		columns=[c for c in df.columns if c.startswith("unnamed")], errors="ignore"
	)

	time_src = "date" if "date" in df.columns else "time"
	if time_src not in df.columns:
		raise ValueError(f"Нет date/time в {path}. Колонки: {list(df.columns)}")

	df["time"] = pd.to_datetime(df[time_src], utc=True).dt.tz_localize(None)
	df = df.sort_values("time").reset_index(drop=True)

	required = ["open", "high", "low", "close", "volume"]
	missing = [c for c in required if c not in df.columns]
	if missing:
		raise ValueError(f"Нет колонок {missing}")

	df = df[["time", "open", "high", "low", "close", "volume"]].copy()
	df["timeframe"] = timeframe
	df = MARKET_DATA_SCHEMA.normalize_columns(df)
	return df


def load_amzn_kaggle(timeframe: str = "1D") -> pd.DataFrame:
	"""Опционально: тот же Kaggle AMZN, что в check_setup_ml."""
	print("[1] Импортирую kagglehub...", flush=True)
	import kagglehub

	print("[2] Проверяю Kaggle credentials...", flush=True)

	if not os.environ.get("KAGGLE_USERNAME") or not os.environ.get("KAGGLE_KEY"):
		raise RuntimeError("Нужны KAGGLE_USERNAME / KAGGLE_KEY в .env")

	print("[3] Скачиваю Kaggle dataset...", flush=True)

	path = kagglehub.dataset_download("abdulmoiz12/amazon-stock-data-2025")

	print(f"[4] Dataset downloaded: {path}", flush=True)

	files = os.listdir(path)
	print(f"[5] Files: {files}", flush=True)

	csv_files = [f for f in files if f.endswith(".csv")]

	if not csv_files:
		raise RuntimeError(f"CSV не найден. Файлы: {files}")

	csv_file = csv_files[0]

	print(f"[6] Loading CSV: {csv_file}", flush=True)

	return load_ohlcv_csv(
		os.path.join(path, csv_file),
		timeframe=timeframe,
	)


def squeeze_fire_events(squeeze_on: pd.Series) -> pd.DataFrame:
	"""Моменты выхода из squeeze: prev ON, curr OFF."""
	prev = squeeze_on.shift(1).fillna(False).astype(bool)
	curr = squeeze_on.astype(bool)
	fired = prev & ~curr
	return fired


def run_check(
	df: pd.DataFrame,
	bb_length: int = 20,
	bb_mult: float = 2.0,
	kc_length: int = 20,
	kc_mult: float = 1.5,
	mom_length: int = 20,
	forward_horizon: int = 10,
) -> None:
	print("=" * 64)
	print("TTM SQUEEZE CHECK")
	print("=" * 64)
	print(f"bars: {len(df):,} | timeframe: {df['timeframe'].iloc[0]}")

	sq = calculate_ttm_squeeze(
		df,
		bb_length=bb_length,
		bb_mult=bb_mult,
		kc_length=kc_length,
		kc_mult=kc_mult,
		mom_length=mom_length,
	)

	# --- sanity ---
	assert len(sq) == len(df), "длина результата != len(df)"
	for col in (
		"squeeze_on",
		"momentum",
		"bb_upper",
		"bb_lower",
		"kc_upper",
		"kc_lower",
	):
		assert col in sq.columns, f"нет колонки {col}"

	valid_mom = sq["momentum"].notna().sum()
	print(f"\nmomentum non-NaN: {valid_mom:,} / {len(sq):,}")

	# --- squeeze stats ---
	on_ratio = float(sq["squeeze_on"].mean())
	print(f"squeeze ON ratio: {on_ratio:.1%}")

	fired = squeeze_fire_events(sq["squeeze_on"])
	n_fire = int(fired.sum())
	print(f"squeeze FIRE events: {n_fire}")

	# направление в момент fire
	fire_idx = np.where(fired.to_numpy())[0]
	bull_fire = 0
	bear_fire = 0
	for i in fire_idx:
		m = sq["momentum"].iloc[i]
		if pd.isna(m):
			continue
		if m > 0:
			bull_fire += 1
		elif m < 0:
			bear_fire += 1

	print(f"  fire + mom>0 (bullish bias): {bull_fire}")
	print(f"  fire + mom<0 (bearish bias): {bear_fire}")

	# --- простой forward return после fire (не edge proof, только sanity) ---
	close = df[MARKET_DATA_SCHEMA.CLOSE_COLUMN]
	fwd = close.shift(-forward_horizon) / close - 1.0

	rows = []
	for i in fire_idx:
		if i >= len(df) - forward_horizon:
			continue
		m = sq["momentum"].iloc[i]
		if pd.isna(m) or pd.isna(fwd.iloc[i]):
			continue
		side = 1 if m > 0 else -1
		ret = float(fwd.iloc[i]) * side  # signed: плюс = в сторону mom
		rows.append(ret)

	if rows:
		arr = np.array(rows)
		print(
			f"\nAfter FIRE → {forward_horizon}-bar signed return (по знаку momentum):"
		)
		print(f"  n={len(arr)}  mean={arr.mean():.2%}  median={np.median(arr):.2%}")
		print(f"  winrate={(arr > 0).mean():.1%}  std={arr.std():.2%}")
	else:
		print("\nНедостаточно fire-событий для forward return")

	# --- IndicatorResult на последнем баре ---
	ind = TTMSqueezeIndicator()
	result = ind.calculate(
		df,
		bb_length=bb_length,
		bb_mult=bb_mult,
		kc_length=kc_length,
		kc_mult=kc_mult,
		mom_length=mom_length,
	)
	print("\nLast-bar IndicatorResult:")
	print(f"  signal : {result.signal}")
	print(f"  regime : {result.regime}")
	print(f"  value  : {result.value}")
	print(f"  meta   : {result.metadata}")

	# --- последние 15 строк для глаз ---
	view = pd.concat(
		[
			df[
				[MARKET_DATA_SCHEMA.TIME_COLUMN, MARKET_DATA_SCHEMA.CLOSE_COLUMN]
			].reset_index(drop=True),
			sq[["squeeze_on", "momentum"]].reset_index(drop=True),
			fired.rename("squeeze_fired").reset_index(drop=True),
		],
		axis=1,
	)
	print("\nTail (15 bars):")
	print(view.tail(15).to_string(index=False))

	print("\n✅ check_ttm_squeeze завершён")


if __name__ == "__main__":
	import argparse

	parser = argparse.ArgumentParser(description="Check TTM Squeeze indicator")
	parser.add_argument("--csv", type=str, default=None, help="Путь к OHLCV CSV")
	parser.add_argument(
		"--kaggle-amzn", action="store_true", help="Взять AMZN с Kaggle"
	)
	parser.add_argument("--timeframe", type=str, default="1D")
	parser.add_argument(
		"--horizon", type=int, default=10, help="Forward bars after fire"
	)
	args = parser.parse_args()

	if args.csv:
		ohlcv = load_ohlcv_csv(args.csv, timeframe=args.timeframe)
	elif args.kaggle_amzn:
		ohlcv = load_amzn_kaggle(timeframe=args.timeframe)
	else:
		print("Укажи --csv path/to/ohlcv.csv  или  --kaggle-amzn")
		sys.exit(1)

	run_check(ohlcv, forward_horizon=args.horizon)
