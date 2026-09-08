# Indicator Checks

Локальные проверки индикаторов и ML-компонентов проекта `SwingTraderAI`.

Файлы `check_*.py` предназначены для быстрой проверки того, что индикатор:

* корректно работает на реальных OHLCV-данных;
* возвращает ожидаемые колонки и значения;
* не падает на историческом датасете;
* генерирует разумное количество сигналов;
* при необходимости показывает простую статистику последующего движения цены.

> Эти проверки являются **sanity checks**, а не полноценным доказательством торговой эффективности индикатора.

---

## Структура

```text
checks/
├── check_ttm_squeeze.py
├── check_pattern_recognition.py
├── check_*.py
└── README.md
```

Каждый `check_*.py` проверяет отдельный компонент проекта.

---

## Требования

Перед запуском должны быть установлены зависимости проекта:

```bash
pip install -r requirements.txt
```

Для загрузки датасетов через Kaggle также нужны Kaggle credentials:

```text
KAGGLE_USERNAME=...
KAGGLE_KEY=...
```

Обычно они находятся в `.env`.

---

# Запуск проверки

Все проверки поддерживают запуск с локальным OHLCV CSV:

```bash
python checks/check_pattern_recognition.py --csv path/to/data.csv
```

или с Kaggle, если конкретная проверка это поддерживает:

```bash
python checks/check_pattern_recognition.py --kaggle-amzn
```

---

## `check_pattern_recognition.py`

Проверяет индикатор распознавания свечных паттернов.

Pipeline:

```text
OHLCV
  ↓
extract_candle_features()
  ↓
detect_bulkowski_patterns()
  ↓
статистика паттернов
  ↓
forward returns
  ↓
PatternRecognitionIndicator
```

Пример:

```bash
python checks/check_pattern_recognition.py --kaggle-amzn
```

Локальный CSV:

```bash
python checks/check_pattern_recognition.py \
    --csv data/AMZN.csv \
    --timeframe 1D
```

Дополнительные параметры:

```bash
--lookback 20
--tolerance 0.015
--slope-window 10
--horizon 10
```

Пример:

```bash
python checks/check_pattern_recognition.py \
    --kaggle-amzn \
    --lookback 20 \
    --tolerance 0.015 \
    --slope-window 10 \
    --horizon 10
```

Проверка выводит:

* количество найденных паттернов;
* частоту каждого паттерна;
* bullish / bearish распределение;
* последние обнаруженные паттерны;
* forward return после паттерна;
* winrate;
* результат `IndicatorResult` на последнем баре;
* последние строки рассчитанных признаков.

Поддерживаемые паттерны:

```text
double_bottom
double_top
hammer
shooting_star
bullish_engulfing
bearish_engulfing
```

---

## `check_ttm_squeeze.py`

Проверяет TTM Squeeze.

Pipeline:

```text
OHLCV
  ↓
calculate_ttm_squeeze()
  ↓
squeeze ON/OFF
  ↓
FIRE events
  ↓
momentum direction
  ↓
forward return
  ↓
TTMSqueezeIndicator
```

Пример:

```bash
python checks/check_ttm_squeeze.py --kaggle-amzn
```

Локальный CSV:

```bash
python checks/check_ttm_squeeze.py \
    --csv data/AMZN.csv \
    --timeframe 1D
```

Основные параметры:

```bash
--horizon 10
```

Дополнительно внутри скрипта можно изменить параметры TTM Squeeze:

```text
bb_length
bb_mult
kc_length
kc_mult
mom_length
```

Проверка выводит:

* количество исторических баров;
* долю времени в `squeeze ON`;
* количество `FIRE`;
* bullish / bearish направление momentum;
* forward return после FIRE;
* `IndicatorResult` последнего бара;
* последние значения индикатора.

---

# Формат CSV

Для локальных проверок CSV должен содержать:

```text
date/time
open
high
low
close
volume
```

Например:

```csv
Date,Open,High,Low,Close,Volume
2025-01-02,220.0,225.0,218.0,223.0,45000000
2025-01-03,223.0,227.0,221.0,226.0,41000000
```

Названия колонок могут отличаться регистром.

---

# Как интерпретировать результаты

`check_*.py` предназначены прежде всего для **технической проверки реализации**.

Например:

```text
AUC: 0.61
```

или:

```text
hammer mean return: +2.6%
```

не означает автоматически, что индикатор является прибыльной торговой стратегией.

Для оценки торгового качества необходимо дополнительно учитывать:

* transaction costs;
* slippage;
* position sizing;
* baseline;
* out-of-sample данные;
* walk-forward testing;
* market regime;
* overlapping signals;
* lookahead / data leakage.

---

# Добавление нового check

Для нового индикатора рекомендуется использовать существующие проверки как шаблон.

Название:

```text
check_<indicator_name>.py
```

Минимальная структура:

```text
1. загрузить OHLCV
2. нормализовать данные
3. вызвать индикатор
4. проверить результат
5. вывести основные statistics
6. проверить последний IndicatorResult
7. вывести tail данных
```

Пример:

```text
check_new_indicator.py

OHLCV
  ↓
calculate_new_indicator()
  ↓
sanity checks
  ↓
statistics
  ↓
IndicatorResult
```

Главная цель `check_*.py`:

> Быстро понять, что индикатор работает корректно на реальных исторических данных и не сломался после изменений в коде.
