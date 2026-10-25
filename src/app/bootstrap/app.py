import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from src.app.bot.handlers import admin, catalog, orders, payments, profile, services, start, study
from src.app.bot.middlewares.db import DatabaseSessionMiddleware
from src.app.bot.middlewares.throttling import ThrottlingMiddleware
from src.app.bot.middlewares.user import UserRegistrationMiddleware
from src.app.config.settings import settings
from src.app.infrastructure.cache.adapter import CacheService
from src.app.infrastructure.database.session import check_db_health, close_db_engine
from src.app.observability.logging import get_logger, setup_logging

logger = get_logger("bootstrap")


class Application:
    """Encapsulates the lifecycle, services, bot instance, and dispatcher."""

    def __init__(self) -> None:
        self.bot = Bot(
            token=settings.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        self.dp = Dispatcher()
        self.cache = CacheService(
            enabled=settings.REDIS_ENABLED,
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
        )

    def register_middlewares(self) -> None:
        # Outer throttling middleware
        self.dp.message.outer_middleware(ThrottlingMiddleware())
        self.dp.callback_query.outer_middleware(ThrottlingMiddleware())

        # Database session middleware
        self.dp.message.middleware(DatabaseSessionMiddleware())
        self.dp.callback_query.middleware(DatabaseSessionMiddleware())

        # User registration middleware
        self.dp.message.middleware(UserRegistrationMiddleware())
        self.dp.callback_query.middleware(UserRegistrationMiddleware())

    def register_routers(self) -> None:
        self.dp.include_routers(
            start.router,
            catalog.router,
            services.router,
            orders.router,
            payments.router,
            study.router,
            profile.router,
            admin.router,
        )

    async def startup(self) -> None:
        setup_logging(log_level=settings.LOG_LEVEL)
        logger.info("Initializing Academic Platform Application...")

        # 1. Verify database connection
        db_healthy = await check_db_health()
        if not db_healthy:
            logger.error("Database connection failed during startup. Check database service and configuration.")
        else:
            logger.info("Database connection verified successfully.")

        # 2. Initialize optional cache
        await self.cache.initialize()

        # 3. Register handlers & middlewares
        self.register_middlewares()
        self.register_routers()
        logger.info("Application startup completed successfully.")

    async def shutdown(self) -> None:
        logger.info("Initiating graceful shutdown...")
        await self.bot.session.close()
        await self.cache.close()
        await close_db_engine()
        logger.info("Shutdown completed.")
