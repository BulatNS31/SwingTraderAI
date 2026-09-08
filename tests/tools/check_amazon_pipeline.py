import asyncio
import os
from typing import Iterator

import kagglehub
import numpy.typing as npt
import pandas as pd
from sklearn.metrics import (
	roc_auc_score,
)
from sklearn.model_selection import TimeSeriesSplit
from uuid6 import uuid7
from xgboost import XGBClassifier

from swingtraderai.indicators.matrix import add_all_indicators
from swingtraderai.ml.trainer import NDArrayInt


class PurgedTimeSeriesSplit(TimeSeriesSplit):
	"""TimeSeriesSplit с удалением перекрывающихся данных (purging)"""

	def __init__(self, n_splits: int = 5, purge_size: int = 5) -> None:
		super().__init__(n_splits=n_splits)
		self.purge_size = purge_size

	def split(
		self,
		X: npt.ArrayLike,
		y: npt.ArrayLike | None = None,
		groups: npt.ArrayLike | None = None,
	) -> Iterator[tuple[NDArrayInt, NDArrayInt]]:
		for train_idx, test_idx in super().split(X, y, groups):
			if self.purge_size < len(train_idx):
				train_idx = train_idx[: -self.purge_size]
			yield train_idx, test_idx


async def run_amazon_simple_test():
	print("🚀 Тестовое обучение простой XGBoost на Amazon (Kaggle) 1d\n")

	# 1. Скачивание датасета
	print("📥 Загрузка датасета Amazon Stock Data 2010-2024...")
	try:
		dataset_path = kagglehub.dataset_download(
			"mhassansaboor/amazon-stock-data-2010-2024"
		)
		print(f"   Путь: {dataset_path}")
	except Exception as e:
		print(f"❌ Ошибка скачивания датасета: {e}")
		return

	# 2. Поиск CSV-файла
	csv_files = [f for f in os.listdir(dataset_path) if f.lower().endswith(".csv")]
	if not csv_files:
		print("❌ CSV-файл не найден в папке датасета")
		return

	csv_path = os.path.join(dataset_path, csv_files[0])
	print(f"   Найден файл: {csv_files[0]}")

	# 3. Чтение и базовая очистка
	try:
		df = pd.read_csv(csv_path)
		if "Unnamed: 0" in df.columns:
			df = df.drop(columns=["Unnamed: 0"])

		# Капитализация названий колонок — как в твоём примере
		df.columns = [col.capitalize() for col in df.columns]

		# Приводим дату к datetime и ставим в индекс
		if "Date" in df.columns:
			df["Date"] = pd.to_datetime(df["Date"])
			df = df.set_index("Date")
			df.index.name = "Time"
		else:
			print("❌ Колонка 'Date' не найдена")
			print("Доступные колонки:", df.columns.tolist())
			return

		df = df.sort_index()
		print(f"   Загружено строк: {len(df):,}")
	except Exception as e:
		print(f"❌ Ошибка при чтении/подготовке данных: {e}")
		return

	# Проверка обязательных колонок
	required = {"Open", "High", "Low", "Close", "Volume"}
	missing = required - set(df.columns)
	if missing:
		print(f"❌ Отсутствуют обязательные колонки: {missing}")
		return

	# 4. Тестовый ID
	test_ticker_id = uuid7()
	print(f"🆔 Тестовый ticker_id: {test_ticker_id}")
	print("   Таймфрейм: 1d\n")

	# 5. Добавление индикаторов
	print("🛠 Вычисление технических индикаторов...")
	try:
		df_features = add_all_indicators(df)
		print(f"   Получено признаков: {len(df_features.columns)}")
	except Exception as e:
		print(f"❌ Ошибка в add_all_indicators: {e}")
		return

	# 6. Подготовка таргета и признаков
	print("📊 Подготовка X и y...")
	HORIZON = 5
	THRESHOLD = 0.01

	df_features["future_return"] = (
		df_features["Close"].shift(-HORIZON) / df_features["Close"] - 1
	)
	y = (df_features["future_return"] > THRESHOLD).astype(int)

	# Колонки, которые почти всегда убираем из признаков
	cols_to_drop = ["future_return", "Close"]
	for col in ["Open", "High", "Low", "Volume", "Adj_close"]:
		if col in df_features.columns:
			cols_to_drop.append(col)

	X = df_features.drop(columns=cols_to_drop, errors="ignore")

	# Убираем хвост, где таргет NaN
	valid_mask = y.notna()
	X = X[valid_mask].copy()
	y = y[valid_mask].copy()

	print(f"   Финальный размер выборки: {len(X):,} строк\n")

	# 7. Обучение
	print("→ Purged TimeSeries CV ...")

	tscv_purged = PurgedTimeSeriesSplit(n_splits=5, purge_size=HORIZON)

	auc_scores_p = []
	# fold_metrics = []

	for fold, (train_idx, val_idx) in enumerate(tscv_purged.split(X), 1):
		X_tr = X.iloc[train_idx]
		X_val = X.iloc[val_idx]
		y_tr = y.iloc[train_idx]
		y_val = y.iloc[val_idx]

		if len(y_val) < 50:
			continue

		# Можно добавить scaler, если хочешь быть ближе к оригинальному пайплайну
		# from sklearn.preprocessing import StandardScaler
		# scaler = StandardScaler()
		# X_tr = scaler.fit_transform(X_tr)
		# X_val = scaler.transform(X_val)

		model = XGBClassifier(
			n_estimators=600,
			learning_rate=0.025,
			max_depth=5,
			scale_pos_weight=(len(y_tr) - sum(y_tr)) / (sum(y_tr) + 1e-6),
			random_state=42,
			eval_metric="auc",
			early_stopping_rounds=60,
			verbosity=0,
		)

		model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], verbose=False)

		proba = model.predict_proba(X_val)[:, 1]
		auc = roc_auc_score(y_val, proba)
		auc_scores_p.append(auc)

		pos = sum(y_val)
		print(
			f"Fold {fold} | AUC: {auc:.4f} | "
			f"pos%: {pos / len(y_val):.1%} | val rows: {len(y_val)}"
		)


if __name__ == "__main__":
	print("=" * 80)
	print("   Простой тестовый запуск XGBoost на Amazon 1d")
	print("=" * 80)
	asyncio.run(run_amazon_simple_test())
