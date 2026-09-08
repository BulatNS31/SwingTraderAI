import os

import joblib
import pandas as pd


def check_saved_model(model_path, csv_path):
	print(f"🧐 Проверка модели: {model_path}")

	model = joblib.load(model_path)

	df = pd.read_csv(csv_path)
	if "Unnamed: 0" in df.columns:
		df = df.drop(columns=["Unnamed: 0"])

	df.columns = [col.capitalize() for col in df.columns]
	df["Date"] = pd.to_datetime(df["Date"], utc=True)
	df = df.set_index("Date")
	df = df.sort_index()
	# Имя индекса не влияет на колонки X, но для порядка:
	df.index.name = "Time"

	from swingtraderai.indicators.matrix import add_all_indicators

	print("🛠 Расчет индикаторов...")
	df_features = add_all_indicators(df)

	cols_to_drop = ["Close"]
	for extra in ["Open", "High", "Low", "Adj_close", "Volume"]:
		if extra in df_features.columns:
			cols_to_drop.append(extra)

	# Выделяем признаки (X)
	X_last_5 = df_features.drop(columns=cols_to_drop)

	print(f"🧬 Количество признаков в X: {X_last_5.shape[1]}")

	# Предсказание вероятностей
	# ВАЖНО: твой тренер не использовал StandardScaler, поэтому подаем данные как есть
	probs = model.predict_proba(X_last_5)[:, 1]
	preds = (probs > 0.5).astype(int)

	print("\n🔮 Результаты предсказания для последних 5 дней:")
	results = pd.DataFrame(
		{"Probability": probs, "Signal (Buy)": preds}, index=X_last_5.index
	)

	pd.set_option("display.max_rows", None)

	# Фильтруем и выводим
	only_signals = results[results["Signal (Buy)"] == 1]

	print(f"\n🚀 Найдено сигналов к покупке: {len(only_signals)}")
	# print(only_signals.)

	pd.reset_option("display.max_rows")


if __name__ == "__main__":
	# Убедись, что этот путь соответствует созданному файлу в models/xgboost/
	PATH = "models/xgboost/019ce726-70bc-7d7f-a9b1-94203634b4ac_1d.joblib"

	import kagglehub

	print("📦 Загрузка данных...")
	csv_dir = kagglehub.dataset_download("abdulmoiz12/amazon-stock-data-2025")
	csv_path = os.path.join(csv_dir, os.listdir(csv_dir)[0])

	if os.path.exists(PATH):
		check_saved_model(PATH, csv_path)
	else:
		print(f"❌ Файл модели не найден по пути: {PATH}")
		print(
			"Сначала запусти check_trainer.py и "
			"скопируй актуальный путь к .joblib файлу."
		)
