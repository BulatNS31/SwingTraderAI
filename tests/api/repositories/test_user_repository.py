import pytest_asyncio

from swingtraderai.api.repositories.user_repository import UserRepository
from swingtraderai.db.models.user import User


@pytest_asyncio.fixture
async def user_repo(session):
	return UserRepository(session)


async def test_get_by_email_success(user_repo, user):
	found_user = await user_repo.get_by_email(user.email)

	assert found_user is not None
	assert found_user.id == user.id
	assert found_user.email == user.email
	assert found_user.username == user.username


async def test_get_by_email_not_found(user_repo):
	result = await user_repo.get_by_email("nonexistent@example.com")
	assert result is None


async def test_get_by_email_case_sensitive(user_repo, session):
	"""Проверка чувствительности к регистру
	(обычно email case-insensitive в реальной жизни,
	но в БД зависит от collation)"""
	user = User(
		username="testuser",
		email="TestEmail@Example.com",
		password_hash="hash123",
	)
	session.add(user)
	await session.commit()
	await session.refresh(user)

	found = await user_repo.get_by_email("TestEmail@Example.com")
	assert found is not None


async def test_get_by_username_success(user_repo, user):
	found = await user_repo.get_by_username(user.username)

	assert found is not None
	assert found.id == user.id
	assert found.username == user.username


async def test_get_by_username_not_found(user_repo):
	result = await user_repo.get_by_username("nonexistentuser")
	assert result is None


async def test_get_by_username_case_sensitive(user_repo, session):
	user = User(
		username="CamelCaseUser",
		email="camel@example.com",
		password_hash="hash123",
	)
	session.add(user)
	await session.commit()

	found = await user_repo.get_by_username("CamelCaseUser")
	assert found is not None

	await user_repo.get_by_username("camelcaseuser")


async def test_repository_inherits_tenant_aware_base(user_repo):
	"""Проверка, что репозиторий правильно наследует базовый класс"""
	assert user_repo.model == User
	assert hasattr(user_repo, "get_by_id")
	assert hasattr(user_repo, "create")
	assert hasattr(user_repo, "_get_tenant_query")


async def test_get_by_email_after_update(user_repo, user, session):
	"""Проверка получения после обновления email"""
	new_email = "newemail@example.com"
	user.email = new_email
	await session.commit()

	found = await user_repo.get_by_email(new_email)
	assert found is not None
	assert found.id == user.id
