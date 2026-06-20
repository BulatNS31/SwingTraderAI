from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sqlalchemy as sa
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from swingtraderai.api.v1 import auth, indicators, markets, tickers, users, watchlist
from swingtraderai.api.v1.admin import router as admin_router
from swingtraderai.api.v1.routers.markets import router as markets_router_v2
from swingtraderai.api.v1.routers.portfolios import router as portfolios_router
from swingtraderai.core.config import settings
from swingtraderai.core.rate_limit import _rate_limit_exceeded_handler, limiter
from swingtraderai.db.base import Base
from swingtraderai.db.session import dispose_engine, engine


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
	try:
		async with engine.connect() as conn:
			await conn.execute(sa.text("SELECT 1"))
		print("Database connection successful")
	except Exception as e:
		print(f"Database connection failed: {e}")
		raise RuntimeError("Cannot connect to database") from e

	async with engine.begin() as conn:
		await conn.run_sync(Base.metadata.create_all)

	yield

	await dispose_engine()


app = FastAPI(
	title="SwingTrader AI API",
	description="API для swing trading с анализом и уведомлениями",
	version="0.1.0",
	docs_url="/docs",
	redoc_url="/redoc",
	lifespan=lifespan,
)


def get_rate_limit_key(request: Request) -> str:
	"""Ключ для rate limiting: сначала пытаемся взять user_id, потом IP"""
	if hasattr(request.state, "user") and request.state.user:
		return f"user:{request.state.user.id}"

	return f"ip:{get_remote_address(request)}"


app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


if settings.CORS_ALLOWED_ORIGINS:
	app.add_middleware(
		CORSMiddleware,
		allow_origins=settings.CORS_ALLOWED_ORIGINS,
		allow_credentials=True,
		allow_methods=["*"],
		allow_headers=["*"],
	)


app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")
app.include_router(tickers.router, prefix="/api/v1")
app.include_router(watchlist.router, prefix="/api/v1")
app.include_router(indicators.router, prefix="/api/v1")
app.include_router(markets.router, prefix="/api/v1")
app.include_router(markets_router_v2, prefix="/api/v1")
app.include_router(portfolios_router, prefix="/api/v1")

app.include_router(admin_router, prefix="/api/v1")
