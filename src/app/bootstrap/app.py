import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.types import BotCommand, ErrorEvent
from src.app.bot.handlers import (
    admin,
    bookings,
    catalog,
    groups,
    opportunities,
    orders,
    payments,
    privacy,
    profile,
    provider,
    services,
    start,
    study,
    subscriptions,
    support,
)
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
        session = AiohttpSession(timeout=60.0)
        self.bot = Bot(
            token=settings.BOT_TOKEN,
            session=session,
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

    def register_error_handlers(self) -> None:
        @self.dp.error()
        async def handle_errors(event: ErrorEvent) -> bool:
            logger.error(f"Telegram handler error: {event.exception}", exc_info=event.exception)
            try:
                if event.update and event.update.callback_query:
                    await event.update.callback_query.answer(
                        "⚠️ حدث بطء مؤقت في الشبكة، يرجى المحاولة مرة أخرى.",
                        show_alert=True,
                    )
                elif event.update and event.update.message:
                    await event.update.message.answer(
                        "⚠️ حدث بطء مؤقت في الاتصال مع خوادم تيليجرام، يرجى إعادة إرسال الأمر."
                    )
            except Exception as e:
                logger.warning(f"Could not send error response to user: {e}")
            return True

    def register_routers(self) -> None:
        self.dp.include_routers(
            start.router,
            catalog.router,
            services.router,
            orders.router,
            payments.router,
            subscriptions.router,
            bookings.router,
            support.router,
            profile.router,
            privacy.router,
            opportunities.router,
            groups.router,
            study.router,
            provider.router,
            admin.router,
        )

    async def setup_bot_commands(self) -> None:
        """Configures official user commands list according to UI-UX.md §3.2."""
        commands = [
            BotCommand(command="start", description="بدء الاستخدام والترحيب"),
            BotCommand(command="menu", description="فتح القائمة الرئيسية"),
            BotCommand(command="help", description="شرح مختصر ودليل الاستخدام"),
            BotCommand(command="services", description="تصفح كتالوج الخدمات (153 خدمة)"),
            BotCommand(command="search", description="البحث بالكلمات في الكتالوج"),
            BotCommand(command="orders", description="متابعة طلباتي وتنفيذاتي"),
            BotCommand(command="subscriptions", description="اشتراكاتي وحقوقي المفعلة"),
            BotCommand(command="bookings", description="مواعيدي وجلساتي الدراسية"),
            BotCommand(command="downloads", description="مكتبة ملفاتي المشتراة"),
            BotCommand(command="edu", description="مركز المذاكرة والتعلم الذاتي"),
            BotCommand(command="plan", description="خطتي الدراسية وجدول المراجعة"),
            BotCommand(command="timer", description="مؤقت التركيز والمذاكرة (Pomodoro)"),
            BotCommand(command="daily", description="السؤال الأكاديمي اليومي"),
            BotCommand(command="opportunities", description="دليل الفرص والمنح الدراسية"),
            BotCommand(command="groups", description="مجموعات الدراسة الأكاديمية"),
            BotCommand(command="profile", description="ملفي الأكاديمي والإعدادات"),
            BotCommand(command="notifications", description="إعدادات الإشعارات والتنبيهات"),
            BotCommand(command="language", description="لغة واجهة البوت"),
            BotCommand(command="support", description="طلب الدعم الفني والأكاديمي"),
            BotCommand(command="terms", description="الشروط والنزاهة وسياسة الاسترداد"),
            BotCommand(command="privacy", description="الخصوصية وتصدير وحذف البيانات"),
            BotCommand(command="cancel", description="إلغاء العملية الحالية والعودة بأمان"),
            BotCommand(command="id", description="معرف حسابك المرجعي لدى الدعم"),
        ]
        try:
            await self.bot.set_my_commands(commands)
            logger.info("Bot commands successfully registered with Telegram.")
        except Exception as e:
            logger.warning(f"Failed to set bot commands with Telegram: {e}")

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
        self.register_error_handlers()
        self.register_routers()

        # 4. Register commands with Telegram API
        if settings.BOT_TOKEN and not settings.BOT_TOKEN.startswith("test_"):
            await self.setup_bot_commands()

        logger.info("Application startup completed successfully.")

    async def shutdown(self) -> None:
        logger.info("Initiating graceful shutdown...")
        await self.bot.session.close()
        await self.cache.close()
        await close_db_engine()
        logger.info("Shutdown completed.")
