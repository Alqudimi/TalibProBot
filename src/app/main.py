import asyncio
import signal

from src.app.bootstrap.app import Application
from src.app.config.settings import settings
from src.app.observability.logging import get_logger
from src.app.workers.task_worker import run_task_worker

logger = get_logger("main")


async def main() -> None:
    settings.validate_for_production()
    app = Application()
    await app.startup()

    tasks = []

    # 1. Background worker task
    if settings.TASK_WORKER_ENABLED:
        worker_coro = run_task_worker(poll_interval=settings.TASK_WORKER_POLL_INTERVAL)
        tasks.append(asyncio.create_task(worker_coro, name="task_worker"))

    # Graceful shutdown handler
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Termination signal received.")
        stop_event.set()

    # 2. Telegram Bot Polling task with automatic network reconnect
    async def run_bot() -> None:
        while not stop_event.is_set():
            try:
                logger.info(f"Starting bot polling for @{settings.BOT_USERNAME}...")
                await app.bot.delete_webhook(drop_pending_updates=True)
                used_updates = app.dp.resolve_used_update_types()
                await app.dp.start_polling(
                    app.bot,
                    allowed_updates=used_updates,
                    handle_signals=False,
                )
                break
            except asyncio.CancelledError:
                break
            except Exception as e:  # noqa: BLE001 - polling must reconnect on any transport failure
                logger.error(
                    f"Bot polling encountered error: {e}. Reconnecting in 5s..."
                )
                if stop_event.is_set():
                    break
                await asyncio.sleep(5)

    if settings.BOT_POLLING_ENABLED:
        tasks.append(asyncio.create_task(run_bot(), name="telegram_bot"))
    else:
        logger.info("BOT_POLLING_ENABLED=false; running worker-only process.")

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    try:
        # Wait until stop event or until one of the main tasks fails
        waiters = [asyncio.create_task(stop_event.wait()), *tasks]
        if waiters:
            await asyncio.wait(waiters, return_when=asyncio.FIRST_COMPLETED)
        else:
            await stop_event.wait()
    finally:
        logger.info("Stopping all running tasks...")
        for t in tasks:
            if not t.done():
                t.cancel()
        await app.shutdown()


if __name__ == "__main__":
    try:
        try:
            import uvloop
        except ImportError:
            asyncio.run(main())
        else:
            uvloop.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application exited.")
