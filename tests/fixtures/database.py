import os
import warnings

import pytest_asyncio
from dotenv import load_dotenv
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from swingtraderai.db.base import Base

load_dotenv()

warnings.filterwarnings(
	"ignore", message=".*rite' option is deprecated.*", category=FutureWarning
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


# Движок тестовой БД
@pytest_asyncio.fixture
async def engine():
	engine = create_async_engine(TEST_DATABASE_URL, future=True)

	async with engine.begin() as conn:
		await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE;"))
		await conn.execute(text("CREATE SCHEMA public;"))
		await conn.run_sync(Base.metadata.create_all)

	yield engine

	await engine.dispose()


# Фабрика сессий
@pytest_asyncio.fixture
async def session(engine):
	Session = async_sessionmaker(
		engine,
		expire_on_commit=False,
	)

	async with Session() as session:
		yield session
