from typing import Any, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.db.base import TenantBase

ModelType = TypeVar("ModelType")
TenantModelType = TypeVar("TenantModelType", bound=TenantBase)


class BaseRepository(Generic[ModelType]):
	"""
	Базовый репозиторий с автоматической изоляцией по tenant_id.
	"""

	def __init__(self, session: AsyncSession, model: Type[ModelType]):
		self.session = session
		self.model = model

	async def get_by_id(self, id: UUID) -> ModelType | None:
		result = await self.session.get(self.model, id)
		return result

	async def get_all(
		self, skip: int = 0, limit: int = 100, **filters: Any
	) -> list[ModelType]:
		query = select(self.model)
		for field, value in filters.items():
			if hasattr(self.model, field):
				query = query.where(getattr(self.model, field) == value)
		query = query.offset(skip).limit(limit)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def create(self, obj_in: dict[str, Any] | Any) -> ModelType:
		if isinstance(obj_in, dict):
			db_obj = self.model(**obj_in)
		else:
			db_obj = obj_in

		self.session.add(db_obj)
		await self.session.commit()
		await self.session.refresh(db_obj)
		return db_obj

	async def update(
		self, id: UUID, obj_in: dict[str, Any] | Any
	) -> Optional[ModelType]:
		"""Обновить запись"""
		db_obj = await self.get_by_id(id)
		if not db_obj:
			return None

		if isinstance(obj_in, dict):
			for key, value in obj_in.items():
				if hasattr(db_obj, key) and value is not None:
					setattr(db_obj, key, value)
		else:
			for key, value in obj_in.__dict__.items():
				if (
					hasattr(db_obj, key)
					and value is not None
					and not key.startswith("_")
				):
					setattr(db_obj, key, value)

		await self.session.commit()
		await self.session.refresh(db_obj)
		return db_obj

	async def delete(self, id: UUID) -> bool:
		obj = await self.get_by_id(id)
		if obj:
			await self.session.delete(obj)
			await self.session.commit()
			return True
		return False


class TenantAwareRepository(Generic[TenantModelType]):
	"""Репозиторий для моделей с tenant_id"""

	def __init__(self, session: AsyncSession, model: Type[TenantModelType]):
		self.session = session
		self.model = model

	def _get_tenant_query(self, tenant_id: UUID) -> Select[tuple[TenantModelType]]:
		"""Базовый запрос с фильтром по tenant_id"""
		return select(self.model).where(self.model.tenant_id == tenant_id)

	async def get_by_id(self, tenant_id: UUID, id: UUID) -> Optional[TenantModelType]:
		id_column = getattr(self.model, "ticker_id", None)
		if id_column is None:
			raise AttributeError(
				f"Model {self.model.__name__} must have an 'id' column"
			)
		query = self._get_tenant_query(tenant_id).where(id_column == id)
		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def get_all(
		self, tenant_id: UUID, skip: int = 0, limit: int = 100, **filters: Any
	) -> List[TenantModelType]:
		query = self._get_tenant_query(tenant_id)
		for field, value in filters.items():
			if hasattr(self.model, field):
				query = query.where(getattr(self.model, field) == value)
		query = query.offset(skip).limit(limit)
		result = await self.session.execute(query)
		return list(result.scalars().all())

	async def create(
		self, tenant_id: UUID, obj_in: dict[str, Any] | Any
	) -> TenantModelType:
		"""Создать запись с принудительной установкой tenant_id"""
		# ✅ Проверяем тип obj_in
		if isinstance(obj_in, dict):
			db_obj = self.model(**obj_in)
		elif isinstance(obj_in, self.model):
			db_obj = obj_in
		else:
			raise TypeError(
				f"obj_in must be dict or {self.model.__name__} instance, "
				f"got {type(obj_in).__name__}"
			)

		if hasattr(db_obj, "tenant_id"):
			db_obj.tenant_id = tenant_id

		self.session.add(db_obj)
		await self.session.commit()
		await self.session.refresh(db_obj)
		return db_obj

	async def delete(self, tenant_id: UUID, id: UUID) -> bool:
		"""Удалить запись с проверкой tenant_id"""
		obj = await self.get_by_id(tenant_id, id)
		if obj:
			await self.session.delete(obj)
			await self.session.commit()
			return True
		return False
