import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from swingtraderai.db.models.user import User


@pytest_asyncio.fixture
async def user(session: AsyncSession):
	"""Создает тестового пользователя и возвращает его"""
	user = User(
		username="testuser",
		email="test@example.com",
		password_hash="fakehash123",
	)

	session.add(user)
	await session.commit()
	await session.refresh(user)

	yield user
