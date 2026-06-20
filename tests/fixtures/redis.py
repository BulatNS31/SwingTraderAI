from typing import Dict, Optional
from unittest.mock import AsyncMock

import pytest_asyncio
import redis
from fastapi import Request
from starlette.requests import Request as StarletteRequest
from starlette.types import Scope


@pytest_asyncio.fixture
def mock_redis(mocker):
	redis_mock = mocker.Mock(spec=redis.Redis)
	redis_mock.ping.return_value = True
	redis_mock.llen.return_value = 42
	redis_mock.get.return_value = None
	redis_mock.keys = AsyncMock(return_value=[])
	redis_mock.pipeline.return_value = mocker.Mock()
	return redis_mock


@pytest_asyncio.fixture
def mock_async_redis(mocker):
	redis_mock = mocker.Mock(spec=redis.asyncio.Redis)
	redis_mock.llen = AsyncMock(return_value=7)
	return redis_mock


@pytest_asyncio.fixture
def mock_celery(mocker):
	celery_app = mocker.Mock()
	inspector = mocker.Mock()
	inspector.ping.return_value = {"worker1": "pong"}
	celery_app.control.inspect.return_value = inspector
	return celery_app


@pytest_asyncio.fixture
def mock_request():
	"""Создает mock Request объект для тестов"""

	def _create_request(
		headers: Optional[Dict[str, str]] = None,
		method: str = "GET",
		path: str = "/",
		client_ip: str = "127.0.0.1",
	) -> Request:
		"""Создает Request с заданными параметрами"""
		scope: Scope = {
			"type": "http",
			"method": method,
			"headers": [
				[b"host", b"testserver"],
				(
					[b"x-forwarded-for", client_ip.encode()]
					if client_ip
					else [b"user-agent", b"pytest"]
				),
			],
			"path": path,
			"query_string": b"",
			"client": (client_ip, 8000),
			"server": ("testserver", 80),
			"scheme": "http",
			"asgi": {"version": "3.0", "spec_version": "2.1"},
			"http_version": "1.1",
		}

		# Добавляем дополнительные headers если есть
		if headers:
			for key, value in headers.items():
				scope["headers"].append([key.encode(), value.encode()])

		# Создаем ASGI receive/send заглушки
		async def receive():
			return {"type": "http.request", "body": b"", "more_body": False}

		async def send(message):
			pass

		# Создаем request
		request = StarletteRequest(scope, receive=receive, send=send)
		return request

	return _create_request


@pytest_asyncio.fixture
def mock_request_with_user(mock_request, user):
	"""Создает request с уже авторизованным пользователем"""

	def _create_request_with_user(
		custom_user=None, headers: Optional[Dict[str, str]] = None
	) -> Request:
		request = mock_request(headers=headers)
		target_user = custom_user or user
		request.state.user = target_user
		return request

	return _create_request_with_user
