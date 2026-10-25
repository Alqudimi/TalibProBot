import time
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """Simple in-memory rate-limiting middleware to prevent rapid duplicate clicks."""

    def __init__(self, rate_limit_seconds: float = 0.5) -> None:
        self.rate_limit = rate_limit_seconds
        self.last_actions: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.time()
            last_time = self.last_actions.get(user_id, 0.0)
            if now - last_time < self.rate_limit:
                if isinstance(event, CallbackQuery):
                    await event.answer("⚠️ يرجى التمهل قليلًا بين الضغطات.", show_alert=False)
                return None
            self.last_actions[user_id] = now

        return await handler(event, data)
