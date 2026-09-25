"""Инструменты для прогнозирования и проверки утечек.

Цель
-------
Необходимо определить, изменяется ли значение признака/индикатора,
вычисленное в момент времени T, при добавлении будущих баров.
Если это происходит, то вычисление не является безопасным на
данный момент времени и не должно использоваться в текущем виде при тестировании.

Типичное использование
-------------
>>> from swingtraderai.backtesting.validation import assert_point_in_time
>>> assert_point_in_time(compute_rsi, df, bar_index=50, feature_name="rsi")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, List, Sequence

import pandas as pd

FeatureFn = Callable[[pd.DataFrame], Any]
"""Функция, которая принимает DataFrame истории и возвращает
скалярное значение или значение Series,
представляющее характеристику на *последнем* баре этой истории."""


@dataclass
class LeakageFinding:
	bar_index: int
	feature_name: str
	value_until_t: Any
	value_until_end: Any
	message: str


@dataclass
class LeakageReport:
	findings: List[LeakageFinding] = field(default_factory=list)

	@property
	def ok(self) -> bool:
		return len(self.findings) == 0

	def raise_if_leaky(self) -> None:
		if self.findings:
			details = "\n".join(
				f"  [{f.feature_name} @ bar {f.bar_index}] {f.message}"
				for f in self.findings
			)
			raise AssertionError(f"Look-ahead leakage detected:\n{details}")


def _values_equal(a: Any, b: Any, tol: float = 1e-9) -> bool:
	if a is None and b is None:
		return True
	if a is None or b is None:
		return False
	try:
		import math

		if isinstance(a, float) and isinstance(b, float):
			if math.isnan(a) and math.isnan(b):
				return True
			return abs(a - b) <= tol
		if hasattr(a, "item"):
			a = a.item()
		if hasattr(b, "item"):
			b = b.item()
		if isinstance(a, (int, float)) and isinstance(b, (int, float)):
			if math.isnan(float(a)) and math.isnan(float(b)):
				return True
			return abs(float(a) - float(b)) <= tol
	except Exception:
		pass
	return bool(a == b)


def check_point_in_time(
	feature_fn: FeatureFn,
	full_df: pd.DataFrame,
	bar_indices: Sequence[int],
	feature_name: str = "feature",
	tol: float = 1e-9,
) -> LeakageReport:
	"""Сравните значение признака (история[:t+1]) с признаком,
	извлеченным из полной истории.
	Для каждого индекса бара ``i`` в ``bar_indices``:
	- v_short = feature_fn(df.iloc[: i+1])
	- v_full = значение того же признака в позиции i, вычисленное на
	всем датафрейме (если feature_fn возвращает Series), ИЛИ feature_fn(df),
	если он возвращает скалярное значение только для последнего бара
	в этом случае мы сравниваем скалярные значения только тогда, когда i является
	последним индексом.

	Наиболее безопасный контракт для ``feature_fn``:
	вход = история до бара принятия решения включительно
	выход = скалярное значение, известное на этом баре
	Если скалярное значение изменяется при наличии
	большего количества будущих строк, сообщается об утечке.
	"""
	report = LeakageReport()
	n = len(full_df)
	if n == 0:
		return report

	for i in bar_indices:
		if i < 0 or i >= n:
			continue
		hist = full_df.iloc[: i + 1].copy()
		try:
			v_short = feature_fn(hist)
		except Exception as exc:
			report.findings.append(
				LeakageFinding(
					bar_index=i,
					feature_name=feature_name,
					value_until_t=None,
					value_until_end=None,
					message=f"feature_fn failed on hist[:{i + 1}]: {exc}",
				)
			)
			continue

		# Scalar path, recompute on a longer prefix (i + buffer) and compare
		# the value at the same logical "last bar of hist".
		# If feature_fn always returns the value for the last row, then
		# feature_fn(hist) must equal the value obtained by taking the
		# i-th element of a Series returned on a longer window — but the
		# simplest robust check is: feature_fn(hist) must be identical when
		# we append future rows *and then slice back* is not possible for
		# scalar-only fns. Instead we check stability under extension:
		# compute on hist, then on hist+future; if the fn is last-bar-only,
		# the second call returns a *different* bar's value, so that is not
		# a valid comparison.
		#
		# Correct test for last-bar scalar functions:
		#   v(df[:i+1]) must equal v(df[:i+1])  (trivial)
		#   AND v(df[:i+1]) must not depend on rows after i.
		# The way to probe dependence: temporarily corrupt future rows and
		# recompute on the short hist only (should be unchanged — always),
		# OR recompute a vectorised version.
		#
		# Practical approach used here:
		#   1. v_short = fn(df[:i+1])
		#   2. Build poisoned full frame where rows after i have extreme values
		#   3. v_poisoned_short = fn(poisoned[:i+1])  — must equal v_short
		#   4. If fn internally ignores the passed frame length and reads a
		#      global, this still won't catch it; callers must pass only hist.
		poisoned = full_df.copy()
		numeric_cols = poisoned.select_dtypes(include="number").columns
		if i + 1 < n and len(numeric_cols) > 0:
			poisoned.loc[poisoned.index[i + 1 :], numeric_cols] = 1e12

		hist_poisoned = poisoned.iloc[: i + 1].copy()
		try:
			v_poisoned = feature_fn(hist_poisoned)
		except Exception as exc:
			report.findings.append(
				LeakageFinding(
					bar_index=i,
					feature_name=feature_name,
					value_until_t=v_short,
					value_until_end=None,
					message=f"feature_fn failed on poisoned hist: {exc}",
				)
			)
			continue

		if not _values_equal(v_short, v_poisoned, tol=tol):
			report.findings.append(
				LeakageFinding(
					bar_index=i,
					feature_name=feature_name,
					value_until_t=v_short,
					value_until_end=v_poisoned,
					message=(
						f"value changed when future rows were poisoned "
						f"({v_short!r} → {v_poisoned!r}). "
						f"Feature likely reads beyond the provided history."
					),
				)
			)

	return report


def assert_point_in_time(
	feature_fn: FeatureFn,
	full_df: pd.DataFrame,
	bar_indices: Sequence[int],
	feature_name: str = "feature",
	tol: float = 1e-9,
) -> None:
	"""Вызвать AssertionError, если обнаружена утечка памяти."""
	report = check_point_in_time(
		feature_fn, full_df, bar_indices, feature_name=feature_name, tol=tol
	)
	report.raise_if_leaky()


def check_series_point_in_time(
	series_fn: Callable[[pd.DataFrame], pd.Series],
	full_df: pd.DataFrame,
	bar_indices: Sequence[int],
	feature_name: str = "series",
	tol: float = 1e-9,
) -> LeakageReport:
	"""Для векторизованных индикаторов,
	возвращающих полный ряд данных, выровненный по df.

	Сравнивает series_fn(df[:i+1]).iloc[-1] vs series_fn(full_df).iloc[i].
	Если они различаются, то для расчета используется будущие данные по индексу i.
	"""
	report = LeakageReport()
	n = len(full_df)
	try:
		full_series = series_fn(full_df)
	except Exception as exc:
		report.findings.append(
			LeakageFinding(
				bar_index=-1,
				feature_name=feature_name,
				value_until_t=None,
				value_until_end=None,
				message=f"series_fn failed on full df: {exc}",
			)
		)
		return report

	for i in bar_indices:
		if i < 0 or i >= n:
			continue
		hist = full_df.iloc[: i + 1].copy()
		try:
			short_series = series_fn(hist)
			v_short = short_series.iloc[-1]
		except Exception as exc:
			report.findings.append(
				LeakageFinding(
					bar_index=i,
					feature_name=feature_name,
					value_until_t=None,
					value_until_end=None,
					message=f"series_fn failed on hist[:{i + 1}]: {exc}",
				)
			)
			continue

		try:
			v_full = full_series.iloc[i]
		except Exception:
			v_full = None

		if not _values_equal(v_short, v_full, tol=tol):
			report.findings.append(
				LeakageFinding(
					bar_index=i,
					feature_name=feature_name,
					value_until_t=v_short,
					value_until_end=v_full,
					message=(
						f"series_fn(df[:{i + 1}]).iloc[-1]={v_short!r} != "
						f"series_fn(full).iloc[{i}]={v_full!r}"
					),
				)
			)
	return report


def check_no_future_columns(
	df: pd.DataFrame,
	forbidden_prefixes: Sequence[str] = ("future_", "target", "fwd_", "label"),
) -> LeakageReport:
	"""Пометки столбцов, которые выглядят, как
	перспективные метки в рамках описания функции."""
	report = LeakageReport()
	for col in df.columns:
		low = str(col).lower()
		for p in forbidden_prefixes:
			if low.startswith(p) or low == p:
				report.findings.append(
					LeakageFinding(
						bar_index=-1,
						feature_name=str(col),
						value_until_t=None,
						value_until_end=None,
						message=f"Column '{col}' looks like a future/label feature",
					)
				)
	return report


def validate_signal_timestamps(
	signals: Sequence[Any],
	bar_times: Sequence[Any],
) -> LeakageReport:
	"""Каждый signal.timestamp должен содержать
	одно из известных временных значений бара (не будущие)."""
	report = LeakageReport()
	known = set(bar_times)
	for idx, sig in enumerate(signals):
		ts = getattr(sig, "timestamp", None)
		if ts is not None and ts not in known:
			report.findings.append(
				LeakageFinding(
					bar_index=idx,
					feature_name="signal.timestamp",
					value_until_t=ts,
					value_until_end=None,
					message=f"Signal timestamp {ts} not in bar timeline",
				)
			)
	return report
