import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    """Simple in-memory rate-limiting middleware to prevent rapid duplicate clicks."""

    def __init__(self, rate_limit_seconds: float = 0.5) -> None:
        self.rate_limit = rate_limit_seconds
        self.last_actions: OrderedDict[int, float] = OrderedDict()
        self.max_entries = 100_000

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None
        if isinstance(event, Message) and event.from_user or isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            now = time.monotonic()
            last_time = self.last_actions.get(user_id, 0.0)
            if now - last_time < self.rate_limit:
                if isinstance(event, CallbackQuery):
                    await event.answer("⚠️ يرجى التمهل قليلًا بين الضغطات.", show_alert=False)
                return None
            self.last_actions[user_id] = now
            self.last_actions.move_to_end(user_id)
            if len(self.last_actions) > self.max_entries:
                self.last_actions.popitem(last=False)

        return await handler(event, data)
