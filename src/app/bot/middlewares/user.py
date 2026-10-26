from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TgUser
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.accounts.service import AccountService
from src.app.observability.logging import correlation_id_ctx

_PUBLIC_COMMANDS = {
    "/help", "/terms", "/privacy", "/language", "/cancel", "/edu",
    "/daily", "/opportunities", "/groups", "/support", "/search",
}
_PUBLIC_CALLBACKS = {
    "terms:read", "home:privacy", "priv:home", "priv:retention",
    "home:opp", "opp:hub", "opp:calendar", "home:groups", "edu:groups",
    "grp:join", "grp:request", "home:support", "sup:faq", "home:edu",
    "edu:hub", "edu:daily", "edu:quizzes",
}


def _needs_account(event: TelegramObject) -> bool:
    """Avoid DB/account work for strictly informational first-hop routes."""
    text = getattr(event, "text", None)
    if isinstance(text, str):
        command = text.split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
        if command in _PUBLIC_COMMANDS:
            return False
    callback_data = getattr(event, "data", None)
    return callback_data not in _PUBLIC_CALLBACKS


class UserRegistrationMiddleware(BaseMiddleware):
    """Middleware that retrieves or registers the telegram user and binds correlation ID."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user: TgUser | None = data.get("event_from_user")
        session: AsyncSession = data.get("session")

        if tg_user and session:
            # Set correlation context
            correlation_id_ctx.set(f"tg:{tg_user.id}")

            if not _needs_account(event):
                return await handler(event, data)

            user = await AccountService.get_or_create_telegram_user(
                session=session,
                telegram_id=tg_user.id,
                username=tg_user.username,
                display_name=tg_user.full_name,
                language_code=tg_user.language_code,
            )
            data["current_user"] = user
            # The account lookup/heartbeat is a separate unit of work. End
            # it before handlers call Telegram, so an idle network request
            # does not keep a PostgreSQL connection checked out from the pool.
            await session.commit()

        return await handler(event, data)
