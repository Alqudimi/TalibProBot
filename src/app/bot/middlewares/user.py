from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.modules.accounts.service import AccountService
from src.app.observability.logging import correlation_id_ctx


class UserRegistrationMiddleware(BaseMiddleware):
    """Middleware that retrieves or registers the telegram user and binds correlation ID."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession = data.get("session")

        if tg_user and session:
            # Set correlation context
            correlation_id_ctx.set(f"tg:{tg_user.id}")

            user = await AccountService.get_or_create_telegram_user(
                session=session,
                telegram_id=tg_user.id,
                username=tg_user.username,
                display_name=tg_user.full_name,
                language_code=tg_user.language_code,
            )
            data["current_user"] = user

        return await handler(event, data)
