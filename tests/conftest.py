import os
import warnings

import pytest_asyncio
from dotenv import load_dotenv
from httpx import AsyncClient

from swingtraderai.db.session import get_session
from swingtraderai.main import app
from tests.fixtures import *

load_dotenv()

warnings.filterwarnings(
	"ignore", message=".*rite' option is deprecated.*", category=FutureWarning
)

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")


# Подмена зависимости FastAPI
@pytest_asyncio.fixture
async def client(session):
	async def override_get_session():
		yield session

	app.dependency_overrides[get_session] = override_get_session

	async with AsyncClient(app=app, base_url="http://test") as ac:
		yield ac

	app.dependency_overrides.clear()
