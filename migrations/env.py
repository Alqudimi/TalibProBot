import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from src.app.config.settings import get_settings
from src.app.shared.models import Base

# Import all modules so all models are registered on Base.metadata
import src.app.modules.accounts.models
import src.app.modules.access_control.models
import src.app.modules.catalog.models
import src.app.modules.orders.models
import src.app.modules.payments.models
import src.app.modules.subscriptions.models
import src.app.modules.entitlements.models
import src.app.modules.service_requests.models
import src.app.modules.delivery.models
import src.app.modules.education.models
import src.app.modules.providers.models
import src.app.modules.bookings.models
import src.app.modules.opportunities.models
import src.app.modules.institutions.models
import src.app.modules.notifications.models
import src.app.modules.support.models
import src.app.modules.reviews.models
import src.app.modules.files.models
import src.app.modules.audit.models

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        version_table_schema="student_platform",
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema="student_platform",
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """In this scenario we need to create an Engine and associate a connection with the context."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
