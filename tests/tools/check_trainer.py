import asyncio
import os

import kagglehub
import pandas as pd
from dotenv import load_dotenv
from kagglehub import KaggleDatasetAdapter
from sklearn.metrics import precision_score, roc_auc_score
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from swingtraderai.indicators.matrix import add_all_indicators
from swingtraderai.ml.trainer import (
	calculate_trading_metrics,
	detect_false_breakout,
	detect_strong_levels,
)

load_dotenv()

if not os.environ.get("KAGGLE_USERNAME") or not os.environ.get("KAGGLE_KEY"):
	print("⚠️  Внимание! Не найдены KAGGLE_USERNAME или KAGGLE_KEY в .env")
	print("Создайте .env файл с:")
	print("KAGGLE_USERNAME=ваш_username")
	print("KAGGLE_KEY=ваш_api_key")
	exit(1)


async def run_gerchik_test(timeframe: str = "1D", min_samples: int = 800):
	print("🚀 Загрузка данных AMZN 201	0-2024...")

	path = kagglehub.load_dataset(
		KaggleDatasetAdapter.PANDAS,
		"abdulmoiz12/amazon-stock-data-2025",
		"amazon_stock_data.csv",
	)
	csv_file = [f for f in os.listdir(path) if f.endswith(".csv")][0]
	df = pd.read_csv(os.path.join(path, csv_file))

	df.columns = [c.lower() for c in df.columns]
	df = df.drop(columns=["unnamed: 0"], errors="ignore")
	df["time"] = pd.to_datetime(df["date"])
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

	# ===================== INDICATORS =====================
	print("🛠 Добавляем индикаторы...")
	df = add_all_indicators(df, timeframe=timeframe)

	# ===================== GERCHIK FEATURES =====================
	print("📍 Определяем сильные уровни...")
	df = detect_strong_levels(df, min_tests=2, window=100)  # ослабили min_tests

	print("🔍 Ищем ложные пробои...")
	df = detect_false_breakout(df, atr_mult=1.2)  # ослабили

	# Дополнительные фичи
	df["returns_5"] = df["close"].pct_change(5)
	df["returns_10"] = df["close"].pct_change(10)
	df["volume_ratio"] = df["volume"] / df["volume"].rolling(30).mean()
	df["price_to_level_ratio"] = df["close"] / (
		df["nearest_level"].fillna(df["close"]) + 1e-8
	)
	df["level_strength_rank"] = df["level_strength"].rolling(200).rank(pct=True)

	# ===================== ЦЕЛЕВОЕ УДАЛЕНИЕ NaN =====================
	print(f"Размер до dropna: {len(df)}")
	df = df.dropna(
		subset=["atr14", "nearest_level", "level_strength", "false_breakout"]
	).reset_index(drop=True)
	print(f"Размер после dropna: {len(df)} строк")

	if len(df) < 300:
		raise ValueError(
			f"Слишком мало данных после обработки: "
			f"{len(df)} строк. Попробуйте таймфрейм 1h."
		)

	# ===================== TARGET =====================
	print("🎯 Создаём таргет по стратегии Герчика...")
	horizon = 15 if timeframe == "1D" else 12
	df["target"] = 0

	fb_count = 0
	for i in range(len(df) - horizon):
		if df["false_breakout"].iloc[i] == 1:
			fb_count += 1
			fb_type = df["fb_type"].iloc[i]
			entry = df["close"].iloc[i]

			future_high = df["high"].iloc[i + 1 : i + horizon + 1].max()
			future_low = df["low"].iloc[i + 1 : i + horizon + 1].min()

			if fb_type == "bear_trap" and future_high > entry * 1.008:  # ослабили порог
				df.loc[i, "target"] = 1
			elif fb_type == "bull_trap" and future_low < entry * 0.992:
				df.loc[i, "target"] = 1

	print(f"Найдено ложных пробоев: {fb_count}")
	print(f"Положительных таргетов: {df['target'].sum()} ({df['target'].mean():.2%})")

	# ===================== FEATURES =====================
	feature_list = [
		"false_breakout",
		"fb_depth",
		"fb_return_bars",
		"level_strength",
		"dist_to_level",
		"price_to_level_ratio",
		"level_strength_rank",
		"volume_ratio",
		"volume_zscore",
		"volume_spike",
		"rsi14",
		"rsi_delta_3",
		"macd_hist",
		"atr_pct",
		"bb_width",
		"returns_5",
		"returns_10",
		"price_above_ema200",
		"ema9_gt_ema21",
		"hour",
		"dayofweek",
	]

	features = [col for col in feature_list if col in df.columns]
	print(f"Используется {len(features)} признаков")

	X = df[features].copy()
	y = df["target"].copy()

	# Отрезаем хвост
	X = X.iloc[:-horizon].reset_index(drop=True)
	y = y.iloc[:-horizon].reset_index(drop=True)

	print(f"Финальный размер датасета: {len(X)}")

	if len(X) < min_samples:
		print(f"⚠️ Мало данных ({len(X)}). Используем весь датасет для теста.")
		# fallback — используем хотя бы 70/30
		split_idx = int(len(X) * 0.7)
	else:
		split_idx = int(len(X) * 0.78)

	X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
	y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

	print(f"Train: {len(X_train):,} | Test: {len(X_test):,}")

	if len(X_train) == 0:
		raise ValueError("Train set пустой! Попробуйте запустить на 1h таймфрейме.")

	# ===================== SCALING =====================
	scaler = StandardScaler()
	X_train_scaled = scaler.fit_transform(X_train)
	X_test_scaled = scaler.transform(X_test)

	# ===================== MODEL =====================
	pos_ratio = float(y_train.mean()) if len(y_train) > 0 else 0.5
	scale_pos_weight = max((1 - pos_ratio) / pos_ratio, 1.0) if pos_ratio > 0 else 1.0

	print(f"scale_pos_weight = {scale_pos_weight:.2f}")

	model = XGBClassifier(
		n_estimators=600,
		learning_rate=0.05,
		max_depth=5,
		min_child_weight=4,
		gamma=0.4,
		subsample=0.8,
		colsample_bytree=0.8,
		reg_alpha=0.5,
		reg_lambda=1.5,
		scale_pos_weight=scale_pos_weight,
		eval_metric=["auc", "logloss"],
		tree_method="hist",
		random_state=42,
	)

	print("🔄 Обучение модели...")
	model.fit(X_train_scaled, y_train)

	# ===================== EVALUATION =====================
	probs = model.predict_proba(X_test_scaled)[:, 1]
	auc = roc_auc_score(y_test, probs)
	pred = (probs > 0.5).astype(int)

	metrics = calculate_trading_metrics(y_test, probs, threshold=0.5)

	print("\n" + "=" * 65)
	print("📊 РЕЗУЛЬТАТЫ ТЕСТА — СТРАТЕГИЯ ГЕРЧИКА")
	print("=" * 65)
	print(f"AUC                  : {auc:.4f}")
	print(f"Win Rate             : {metrics['win_rate']:.1%}")
	print(f"Profit Factor        : {metrics['profit_factor']:.2f}")
	print(f"Total Signals        : {metrics['total_trades']}")
	print(
		f"Precision            : {precision_score(y_test, pred, zero_division=0):.1%}"
	)

	importance = pd.Series(model.feature_importances_, index=features).sort_values(
		ascending=False
	)
	print("\n🔝 ТОП-10 признаков:")
	print(importance.head(10))

	# Примеры сигналов
	df_test = df.iloc[-len(y_test) :].copy().reset_index(drop=True)
	df_test["prob"] = probs
	df_test["signal"] = (probs > 0.6).astype(int)  # более строгий порог

	print(f"\n📈 Сигналов с prob > 0.6: {(df_test['signal'] == 1).sum()}")
	if (df_test["signal"] == 1).sum() > 0:
		print("\nПримеры сильных сигналов:")
		print(
			df_test[df_test["signal"] == 1][
				["time", "close", "fb_type", "fb_depth", "prob"]
			].head(6)
		)

	print("\n✅ Тест завершён!")


if __name__ == "__main__":
	asyncio.run(run_gerchik_test(timeframe="1D"))
