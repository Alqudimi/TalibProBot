"""HTTP bridge for Telegym -> the real aiogram Dispatcher.

Telegym injects Telegram Updates into /telegym/update. Outbound Bot API
requests are redirected to the Telegym mock through TELEGRAM_API_URL.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from aiohttp import web

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.app.bootstrap.app import Application


async def main() -> None:
    app = Application()
    print(f"telegym bot api={app.bot.session.api.base}", flush=True)
    app.register_middlewares()
    app.register_error_handlers()
    app.register_routers()
    background_tasks: set[asyncio.Task[object]] = set()

    def report_task(task: asyncio.Task[object]) -> None:
        background_tasks.discard(task)
        if task.cancelled():
            return
        if task.exception():
            print(f"background update failed: {task.exception()!r}", flush=True)

    async def receive_update(request: web.Request) -> web.Response:
        update = await request.json()
        # Telegram considers a webhook delivered once it receives 2xx. Do not
        # hold the HTTP connection open while DB-backed handlers run; this is
        # essential for a realistic burst/load test.
        task = asyncio.create_task(app.dp.feed_raw_update(app.bot, update))
        background_tasks.add(task)
        task.add_done_callback(report_task)
        return web.json_response({"ok": True})

    web_app = web.Application()
    web_app.router.add_post("/telegym/update", receive_update)
    runner = web.AppRunner(web_app)
    await runner.setup()
    site = web.TCPSite(
        runner,
        os.getenv("TELEGYM_BRIDGE_HOST", "127.0.0.1"),
        int(os.getenv("TELEGYM_BRIDGE_PORT", "8089")),
        backlog=int(os.getenv("TELEGYM_BRIDGE_BACKLOG", "8192")),
    )
    await site.start()
    print("telegym bridge ready", flush=True)
    try:
        await asyncio.Event().wait()
    finally:
        await app.bot.session.close()
        await runner.cleanup()


if __name__ == "__main__":
    # Keep the harness on the same asyncio implementation used by Telegym's
    # reference run; production polling may opt into uvloop independently.
    asyncio.run(main())
