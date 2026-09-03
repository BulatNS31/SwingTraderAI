from typing import Dict, List, Optional

from .base import BaseIndicator


class IndicatorRegistry:
	"""Глобальный реестр технических индикаторов.

	Индикаторы регистрируются при импорте модулей:
	registry.register(SomeIndicator())

	Поиск по имени — case-insensitive.
	"""

	_indicators: Dict[str, BaseIndicator] = {}
	_categories: Dict[str, List[str]] = {}

	@classmethod
	def register(cls, indicator: BaseIndicator) -> None:
		"""Зарегистрировать индикатор (повторная регистрация перезаписывает)."""
		key = indicator.name.lower()

		# Убрать имя из всех категорий при re-register
		for cat_names in cls._categories.values():
			# сравниваем case-insensitive
			to_remove = [n for n in cat_names if n.lower() == key]
			for n in to_remove:
				cat_names.remove(n)

		cls._indicators[key] = indicator

		names = cls._categories.setdefault(indicator.category, [])
		if indicator.name not in names:
			names.append(indicator.name)

	@classmethod
	def get(cls, name: str) -> Optional[BaseIndicator]:
		"""Получить индикатор по имени (без учёта регистра)."""
		return cls._indicators.get(name.lower())

	@classmethod
	def get_by_category(cls, category: str) -> List[BaseIndicator]:
		"""Все индикаторы указанной категории."""
		names = cls._categories.get(category, [])
		result: List[BaseIndicator] = []
		for name in names:
			ind = cls._indicators.get(name.lower())
			if ind is not None:
				result.append(ind)
		return result

	@classmethod
	def list_all(cls) -> List[str]:
		"""Список всех зарегистрированных имён (в lower-case)."""
		return list(cls._indicators.keys())

	@classmethod
	def list_categories(cls) -> List[str]:
		"""Список категорий."""
		return list(cls._categories.keys())

	@classmethod
	def unregister(cls, name: str) -> bool:
		"""Удалить индикатор по имени. True, если был зарегистрирован."""
		key = name.lower()
		ind = cls._indicators.pop(key, None)
		if ind is None:
			return False

		for cat_names in cls._categories.values():
			to_remove = [n for n in cat_names if n.lower() == key]
			for n in to_remove:
				cat_names.remove(n)

		# Убрать пустые категории
		empty = [c for c, names in cls._categories.items() if not names]
		for c in empty:
			del cls._categories[c]

		return True

	@classmethod
	def clear(cls) -> None:
		"""Очистить реестр (удобно в тестах)."""
		cls._indicators.clear()
		cls._categories.clear()


registry = IndicatorRegistry()
