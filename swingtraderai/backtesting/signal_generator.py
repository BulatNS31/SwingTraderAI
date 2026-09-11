"""Моментальная генерация сигнала для обратного тестирования.

Повторно использует логику составных сигналов проекта без предварительного просмотра.
Индикаторы рассчитываются только на основе истории, доступной до
текущего бара. Задержка подтверждения фрактала моделируется явно.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from swingtraderai.backtesting.models import Side, Signal
from swingtraderai.indicators.registry import IndicatorRegistry

from .config import BacktestConfig, StopLossMode, TakeProfitMode


def _extract_signal_value(result: Any) -> float:
	"""Зеркало IndicatorService._extract_signal_value.

	Сохраняется локальным, чтобы уровень тестирования
	на основе данных не зависел от класса live service
	(который использует зависимости от базы данных / асинхронности).
	"""
	if hasattr(result, "signal_value"):
		return float(result.signal_value)
	if hasattr(result, "signal"):
		signal_map = {
			"STRONG_BUY": 2.0,
			"BUY": 1.0,
			"NEUTRAL": 0.0,
			"SELL": -1.0,
			"STRONG_SELL": -2.0,
			"bullish": 1.0,
			"bearish": -1.0,
		}
		return signal_map.get(str(result.signal), 0.0)
	if isinstance(result, dict):
		if "signal_value" in result:
			return float(result["signal_value"])
		if "signal" in result:
			signal_map = {
				"STRONG_BUY": 2.0,
				"BUY": 1.0,
				"NEUTRAL": 0.0,
				"SELL": -1.0,
				"STRONG_SELL": -2.0,
				"bullish": 1.0,
				"bearish": -1.0,
			}
			return signal_map.get(str(result["signal"]), 0.0)
	if isinstance(result, (int, float)):
		return float(result)
	return 0.0


def _calculate_composite_signal(
	indicator_results: Dict[str, Any],
) -> Tuple[str, int, str]:
	"""Mirror of IndicatorService._calculate_composite_signal."""
	if not indicator_results:
		return "NEUTRAL", 1, "Нет данных от индикаторов"

	buy_score = 0.0
	sell_score = 0.0

	for _, result in indicator_results.items():
		value = _extract_signal_value(result)
		if value > 0:
			buy_score += value
		elif value < 0:
			sell_score += abs(value)

	total = buy_score + sell_score
	if total == 0:
		return "NEUTRAL", 1, "Сигналы отсутствуют"

	if buy_score > sell_score:
		strength = int(min(10, 1 + (buy_score / total) * 9))
		if strength >= 8:
			return "STRONG_BUY", strength, f"Сильный бычий сигнал (сила: {strength}/10)"
		return "BUY", strength, f"Бычий сигнал (сила: {strength}/10)"
	if sell_score > buy_score:
		strength = int(min(10, 1 + (sell_score / total) * 9))
		if strength >= 8:
			return (
				"STRONG_SELL",
				strength,
				f"Сильный медвежий сигнал (сила: {strength}/10)",
			)
		return "SELL", strength, f"Медвежий сигнал (сила: {strength}/10)"
	return "NEUTRAL", 5, "Рынок в нейтральном состоянии"


def _side_from_signal_type(signal_type: str) -> Side:
	if signal_type in ("BUY", "STRONG_BUY"):
		return Side.LONG
	if signal_type in ("SELL", "STRONG_SELL"):
		return Side.SHORT
	return Side.NEUTRAL


def _default_sl_tp(
	entry_ref: float,
	side: Side,
	config: BacktestConfig,
	atr: Optional[float] = None,
) -> Tuple[Optional[float], Optional[float]]:
	"""Compute default stop-loss and take-profit from config."""

	sl: Optional[float] = None
	tp: Optional[float] = None

	if side == Side.NEUTRAL:
		return None, None

	# Stop-loss
	if config.stop_loss_mode == StopLossMode.FIXED_PCT:
		if side == Side.LONG:
			sl = entry_ref * (1.0 - config.stop_loss_pct)
		else:
			sl = entry_ref * (1.0 + config.stop_loss_pct)
	elif config.stop_loss_mode == StopLossMode.ATR_MULTIPLE and atr and atr > 0:
		if side == Side.LONG:
			sl = entry_ref - atr * config.stop_loss_atr_mult
		else:
			sl = entry_ref + atr * config.stop_loss_atr_mult

	# Take-profit
	if config.take_profit_mode == TakeProfitMode.FIXED_PCT:
		if side == Side.LONG:
			tp = entry_ref * (1.0 + config.take_profit_pct)
		else:
			tp = entry_ref * (1.0 - config.take_profit_pct)
	elif config.take_profit_mode == TakeProfitMode.ATR_MULTIPLE and atr and atr > 0:
		if side == Side.LONG:
			tp = entry_ref + atr * config.take_profit_atr_mult
		else:
			tp = entry_ref - atr * config.take_profit_atr_mult
	elif config.take_profit_mode == TakeProfitMode.RR_RATIO and sl is not None:
		risk = abs(entry_ref - sl)
		if side == Side.LONG:
			tp = entry_ref + risk * config.risk_reward_ratio
		else:
			tp = entry_ref - risk * config.risk_reward_ratio

	return sl, tp


def _simple_atr(df: pd.DataFrame, window: int = 14) -> Optional[float]:
	"""Lightweight ATR for SL/TP sizing when full indicator suite is unavailable."""
	if len(df) < window + 1:
		return None

	high = df["high"].astype(float)
	low = df["low"].astype(float)
	close = df["close"].astype(float)
	tr = pd.concat(
		[
			high - low,
			(high - close.shift(1)).abs(),
			(low - close.shift(1)).abs(),
		],
		axis=1,
	).max(axis=1)
	atr = tr.rolling(window).mean().iloc[-1]
	return float(atr) if pd.notna(atr) else None


class SignalGenerator:
	"""Генерирует сигналы на определенный момент времени из истории OHLCV.

	Два режима:
	A) Только составной (по умолчанию) — использует зарегистрированные индикаторы,
	когда они доступны, в противном случае возвращается
	к минимальной детерминированной эвристике RSI/EMA,
	чтобы механизм можно было протестировать без полного проекта.
	Б) Составной + дополнительный замороженный XGBoost (фаза 4).
	"""

	def __init__(self, config: BacktestConfig) -> None:
		self.config = config
		self._registry: Optional[IndicatorRegistry] = None
		self._try_load_registry()

	def _try_load_registry(self) -> None:
		try:
			# Import side-effects register indicators
			import swingtraderai.indicators  # noqa: F401
			from swingtraderai.indicators.registry import registry

			self._registry = registry
		except Exception:
			self._registry = None

	def generate(
		self,
		history: pd.DataFrame,
		ticker: str,
		timeframe: str,
		bar_timestamp: datetime,
	) -> Signal:
		"""Produce a Signal using only data present in `history`.

		`history` must be the slice available at the decision bar
		(i.e. df.iloc[:i+1]). No future rows may be present.
		"""
		if history.empty:
			return self._neutral(ticker, timeframe, bar_timestamp, 0.0)

		# Ensure lower-case columns
		hist = history.copy()
		hist.columns = [c.lower() for c in hist.columns]

		close = float(hist["close"].iloc[-1])
		indicator_results: Dict[str, Any] = {}
		indicators_used: List[str] = []

		if self._registry is not None:
			for name, indicator in list(self._registry._indicators.items()):
				try:
					result = indicator.calculate(hist)
					indicator_results[name] = result
					indicators_used.append(name)
				except Exception:
					continue
		else:
			# Fallback heuristic for standalone / unit tests
			indicator_results, indicators_used = self._fallback_indicators(hist)

		signal_type, strength, _message = _calculate_composite_signal(indicator_results)
		side = _side_from_signal_type(signal_type)

		atr = _simple_atr(hist)
		sl, tp = _default_sl_tp(close, side, self.config, atr=atr)

		# Optional ML (Phase 4 stub)
		ml_prob: Optional[float] = None
		if self.config.use_ml:
			ml_prob = self._optional_ml_predict(hist, ticker, timeframe)

		regime = self._infer_regime(hist)

		return Signal(
			timestamp=bar_timestamp,
			ticker=ticker,
			timeframe=timeframe,
			side=side,
			signal_type=signal_type,
			signal_score=float(strength),
			confidence=None,
			market_regime=regime,
			entry_reference_price=close,
			stop_loss=sl,
			take_profit=tp,
			ml_probability=ml_prob,
			indicators_used=indicators_used,
		)

	def _fallback_indicators(
		self, hist: pd.DataFrame
	) -> Tuple[Dict[str, Any], List[str]]:
		"""Deterministic RSI + EMA crossover when full registry is absent."""
		results: Dict[str, Any] = {}
		used: List[str] = []
		close = hist["close"].astype(float)

		if len(close) >= 15:
			delta = close.diff()
			gain = delta.clip(lower=0).rolling(14).mean()
			loss = (-delta.clip(upper=0)).rolling(14).mean()
			last_gain = float(gain.iloc[-1])
			last_loss = float(loss.iloc[-1])

			if last_gain == 0.0 and last_loss == 0.0:
				# Плоские цены — RSI не определён, трактуем как нейтральный
				results["rsi"] = {"signal": "NEUTRAL", "signal_value": 0.0}
			elif last_loss == 0.0:
				results["rsi"] = {"signal": "SELL", "signal_value": -1.0}  # RSI = 100
			elif last_gain == 0.0:
				results["rsi"] = {"signal": "BUY", "signal_value": 1.0}  # RSI = 0
			else:
				rs = last_gain / last_loss
				last_rsi = 100.0 - (100.0 / (1.0 + rs))
				if last_rsi < 30:
					results["rsi"] = {"signal": "BUY", "signal_value": 1.0}
				elif last_rsi > 70:
					results["rsi"] = {"signal": "SELL", "signal_value": -1.0}
				else:
					results["rsi"] = {"signal": "NEUTRAL", "signal_value": 0.0}
			used.append("rsi")

		if len(close) >= 21:
			ema_fast = close.ewm(span=9, adjust=False).mean()
			ema_slow = close.ewm(span=21, adjust=False).mean()
			if (
				ema_fast.iloc[-1] > ema_slow.iloc[-1]
				and ema_fast.iloc[-2] <= ema_slow.iloc[-2]
			):
				results["ema_cross"] = {"signal": "BUY", "signal_value": 1.5}
			elif (
				ema_fast.iloc[-1] < ema_slow.iloc[-1]
				and ema_fast.iloc[-2] >= ema_slow.iloc[-2]
			):
				results["ema_cross"] = {"signal": "SELL", "signal_value": -1.5}
			else:
				results["ema_cross"] = {"signal": "NEUTRAL", "signal_value": 0.0}
			used.append("ema_cross")

		return results, used

	def _infer_regime(self, hist: pd.DataFrame) -> Optional[str]:
		if len(hist) < 30:
			return None
		close = hist["close"].astype(float)
		ret = close.pct_change().dropna()
		vol = float(ret.tail(20).std())
		if vol > 0.02:
			return "high_vol"
		sma = close.rolling(20).mean()
		if close.iloc[-1] > sma.iloc[-1] * 1.01:
			return "uptrend"
		if close.iloc[-1] < sma.iloc[-1] * 0.99:
			return "downtrend"
		return "range"

	def _optional_ml_predict(
		self, hist: pd.DataFrame, ticker: str, timeframe: str
	) -> Optional[float]:
		"""Stub for Phase 4. Returns None when ML is unavailable."""
		return None

	def _neutral(
		self, ticker: str, timeframe: str, ts: datetime, price: float
	) -> Signal:
		return Signal(
			timestamp=ts,
			ticker=ticker,
			timeframe=timeframe,
			side=Side.NEUTRAL,
			signal_type="NEUTRAL",
			signal_score=1.0,
			entry_reference_price=price,
		)
