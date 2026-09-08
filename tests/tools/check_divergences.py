"""
Тест ML-фильтра торговых setup'ов (шаг 4).

Поток:
  OHLCV → SetupScanner (вся история) → label (TP до SL) → XGBoost → метрики
"""

from __future__ import annotations

import asyncio
import os

import kagglehub
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sklearn.metrics import precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from swingtraderai.ml.setup_dataset import (
	build_setup_dataset,
	label_setup_outcome,
)
from swingtraderai.ml.setups.scanner import SetupScanner
from swingtraderai.ml.trainer import calculate_trading_metrics

load_dotenv()

if not os.environ.get("KAGGLE_USERNAME") or not os.environ.get("KAGGLE_KEY"):
	print("⚠️  Не найдены KAGGLE_USERNAME или KAGGLE_KEY в .env")
	exit(1)


def load_amzn(timeframe: str = "1D") -> pd.DataFrame:
	print("🚀 Загрузка данных AMZN 2010-2025...")
	path = kagglehub.dataset_download("abdulmoiz12/amazon-stock-data-2025")
	csv_file = next(f for f in os.listdir(path) if f.endswith(".csv"))
	df = pd.read_csv(os.path.join(path, csv_file))

	df.columns = [c.lower() for c in df.columns]
	df = df.drop(columns=["unnamed: 0"], errors="ignore")
	df["time"] = pd.to_datetime(df["date"], utc=True).dt.tz_localize(None)
	df = df.sort_values("time").reset_index(drop=True)

	if timeframe != "1D":
		print(f"🔄 Ресемплинг на {timeframe}...")
		df = (
			df.set_index("time")
			.resample(timeframe)
			.agg(
				{
					"open": "first",
					"high": "max",
					"low": "min",
					"close": "last",
					"volume": "sum",
				}
			)
			.dropna()
			.reset_index()
		)

	df["timeframe"] = timeframe

	print(f"📊 Загружено {len(df):,} баров")
	return df


async def run_setup_ml_test(
	timeframe: str = "1D",
	horizon: int = 15,
	label_mode: str = "rr",  # "rr" | "atr"
	atr_mult: float = 1.5,
	min_samples: int = 50,
) -> None:
	df = load_amzn(timeframe=timeframe)

	# ---------- dataset из SetupScanner ----------
	print("🛠 Сканер setup'ов + разметка (TP до SL)...")
	X, y = build_setup_dataset(
		df,
		symbol="AMZN",
		timeframe=timeframe,
		horizon=horizon,
		label_mode=label_mode,
		atr_mult=atr_mult,
	)

	if len(X) < min_samples:
		raise ValueError(
			f"Мало размеченных setup'ов: {len(X)} (нужно ≥ {min_samples}). "
			"Попробуйте label_mode='atr' или увеличьте историю."
		)

	print(f"Финальный размер: {len(X)}")
	print(f"Positive rate: {y.mean():.1%} ({int(y.sum())}/{len(y)})")
	print(f"Признаков: {len(X.columns)}")

	X = X.replace([np.inf, -np.inf], np.nan).fillna(0.0)

	# хронологический сплит
	split_idx = int(len(X) * 0.75)
	X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
	y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

	print(f"Train: {len(X_train):,} | Test: {len(X_test):,}")
	print(f"Train pos: {y_train.mean():.1%} | Test pos: {y_test.mean():.1%}")

	scaler = StandardScaler()
	X_train_s = scaler.fit_transform(X_train)
	X_test_s = scaler.transform(X_test)

	pos = float(y_train.mean()) if len(y_train) else 0.5
	spw = max((1 - pos) / pos, 1.0) if pos > 0 else 1.0
	print(f"scale_pos_weight = {spw:.2f}")

	model = XGBClassifier(
		n_estimators=400,
		learning_rate=0.05,
		max_depth=4,
		min_child_weight=5,
		gamma=0.3,
		subsample=0.8,
		colsample_bytree=0.8,
		reg_alpha=0.5,
		reg_lambda=1.5,
		scale_pos_weight=spw,
		eval_metric=["auc", "logloss"],
		tree_method="hist",
		random_state=42,
	)

	print("🔄 Обучение...")
	model.fit(X_train_s, y_train)

	probs = model.predict_proba(X_test_s)[:, 1]
	auc = float(roc_auc_score(y_test, probs)) if y_test.nunique() > 1 else 0.0
	pred = (probs > 0.5).astype(int)
	metrics = calculate_trading_metrics(y_test, probs, threshold=0.5)

	print("\n" + "=" * 65)
	print("📊 РЕЗУЛЬТАТЫ — ML-ФИЛЬТР SETUP'ОВ")
	print("=" * 65)
	print(f"label_mode           : {label_mode}")
	print(f"horizon              : {horizon}")
	print(f"AUC                  : {auc:.4f}")
	print(f"Win Rate (pred>0.5)  : {metrics['win_rate']:.1%}")
	print(f"Profit Factor        : {metrics['profit_factor']:.2f}")
	print(f"Total Signals        : {metrics['total_trades']}")
	print(
		f"Precision            : {precision_score(y_test, pred, zero_division=0):.1%}"
	)

	importance = pd.Series(model.feature_importances_, index=X.columns).sort_values(
		ascending=False
	)
	print("\n🔝 ТОП-10 признаков:")
	print(importance.head(10))

	# ---------- baseline: все setup'ы без ML ----------
	print("\n📌 Baseline (сканер без ML, разметка на истории)...")
	scanner = SetupScanner(
		use_divergence=True,
		use_false_breakout=True,
		use_bsu_bpu=True,
		require_trend_align=True,
		only_last_bar=False,
	)
	prepared = scanner.prepare(df, timeframe=timeframe)
	scanned = scanner.scan(prepared, symbol="AMZN", timeframe=timeframe, prepare=False)

	by_type: dict[str, list[int]] = {}
	for s in scanned.setups:
		lab = label_setup_outcome(
			prepared, s, horizon=horizon, mode=label_mode, atr_mult=atr_mult
		)
		if lab is None:
			continue
		by_type.setdefault(s.setup_type.value, []).append(lab)

	print(f"Всего setup'ов (с меткой): {sum(len(v) for v in by_type.values())}")
	for stype, labs in sorted(by_type.items()):
		arr = np.array(labs)
		print(f"  {stype:30s}  n={len(arr):4d}  WR={arr.mean():.1%}")

	# примеры на test с высокой prob
	print(f"\n📈 Test bars with prob > 0.55: {(probs > 0.55).sum()}")
	test_view = X_test.copy()
	test_view["target"] = y_test.values
	test_view["prob"] = probs
	top = (
		test_view[test_view["prob"] > 0.55].sort_values("prob", ascending=False).head(8)
	)
	if len(top):
		cols = [
			c
			for c in (
				"side",
				"signal_strength",
				"reward_risk",
				"near_level",
				"type_bullish_divergence",
				"type_false_breakout_bear_trap",
				"type_bsu_bpu_reaction",
				"target",
				"prob",
			)
			if c in top.columns
		]
		print(top[cols].to_string())

	print("\n✅ Тест завершён!")
	print(
		"Чтобы сохранить модель: swingtraderai.ml.setup_trainer.train_setup_model(...)"
	)


if __name__ == "__main__":
	asyncio.run(
		run_setup_ml_test(
			timeframe="1D",
			horizon=15,
			label_mode="atr",
			atr_mult=1.5,
			min_samples=40,
		)
	)
