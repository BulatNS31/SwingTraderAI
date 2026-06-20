from typing import Any, Dict, Sequence
from uuid import UUID

from sqlalchemy import and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from swingtraderai.db.models.user import Position

from .base import TenantAwareRepository


class PositionRepository(TenantAwareRepository[Position]):
	"""Репозиторий для управления позициями пользователей."""

	def __init__(self, session: AsyncSession):
		super().__init__(session, Position)

	async def create(self, tenant_id: UUID, obj_in: Dict[str, Any]) -> Position:
		"""Создать новую позицию"""
		# Добавляем tenant_id в данные
		obj_in["tenant_id"] = tenant_id
		position = Position(**obj_in)
		self.session.add(position)
		await self.session.commit()
		await self.session.refresh(position)
		return position

	async def get_all_by_user(
		self, tenant_id: UUID, user_id: UUID, closed: bool | None = None
	) -> Sequence[Position]:
		"""Получить все позиции пользователя"""
		query = self._get_tenant_query(tenant_id).where(Position.user_id == user_id)

		if closed is not None:
			if closed:
				query = query.where(Position.closed_at.isnot(None))
			else:
				query = query.where(Position.closed_at.is_(None))

		query = query.options(joinedload(Position.ticker))

		result = await self.session.execute(query)
		return result.scalars().all()

	async def get_active_by_ticker(
		self, tenant_id: UUID, user_id: UUID, ticker_id: UUID, position_type: str
	) -> Position | None:
		"""Проверка наличия активной позиции"""
		query = (
			self._get_tenant_query(tenant_id)
			.where(
				and_(
					Position.user_id == user_id,
					Position.ticker_id == ticker_id,
					Position.position_type == position_type,
					Position.closed_at.is_(None),
				)
			)
			.options(joinedload(Position.ticker))
		)

		result = await self.session.execute(query)
		return result.scalar_one_or_none()

	async def close_position(self, tenant_id: UUID, position_id: UUID) -> bool:
		"""Закрытие позиции (можно расширить логикой)"""
		position = await self.get_by_id(tenant_id, position_id)
		if position and not position.closed_at:
			# Здесь можно добавить логику закрытия (расчёт P&L и т.д.)
			await self.session.delete(position)
			await self.session.commit()
			return True
		return False
