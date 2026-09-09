from __future__ import with_statement

from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context
from swingtraderai.core.config import settings
from swingtraderai.db.models import Base

config = context.config

db_url = settings.DATABASE_URL

if db_url:
	if "postgresql://" in db_url and "+asyncpg" not in db_url:
		db_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
	config.set_main_option("sqlalchemy.url", db_url)

if config.config_file_name is not None:
	fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
	"""Run migrations in 'offline' mode."""
	url = config.get_main_option("sqlalchemy.url")
	context.configure(
		url=url,
		target_metadata=target_metadata,
		literal_binds=True,
		dialect_opts={"paramstyle": "named"},
	)
	with context.begin_transaction():
		context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
	"""Run migrations in 'online' mode."""
	context.configure(
		connection=connection, target_metadata=target_metadata, compare_type=True
	)
	with context.begin_transaction():
		context.run_migrations()


async def run_migrations_online() -> None:
	section = config.get_section(config.config_ini_section)

	if section is None:
		raise RuntimeError(
			f"Section {config.config_ini_section} not found in alembic.ini"
		)

	connectable = async_engine_from_config(
		section,
		prefix="sqlalchemy.",
		poolclass=pool.NullPool,
	)
	async with connectable.connect() as connection:
		await connection.run_sync(do_run_migrations)
	await connectable.dispose()


if context.is_offline_mode():
	run_migrations_offline()
else:
	import asyncio

	asyncio.run(run_migrations_online())
