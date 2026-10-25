import asyncio
import signal
import sys
from src.app.bootstrap.app import Application
from src.app.config.settings import settings
from src.app.observability.logging import get_logger
from src.app.workers.task_worker import run_task_worker

logger = get_logger("main")


async def main() -> None:
    app = Application()
    await app.startup()

    tasks = []

    # 1. Background worker task
    if settings.TASK_WORKER_ENABLED:
        worker_coro = run_task_worker(poll_interval=settings.TASK_WORKER_POLL_INTERVAL)
        tasks.append(asyncio.create_task(worker_coro, name="task_worker"))

    # 2. Telegram Bot Polling task
    async def run_bot() -> None:
        try:
            logger.info(f"Starting bot polling for @{settings.BOT_USERNAME}...")
            await app.bot.delete_webhook(drop_pending_updates=True)
            await app.dp.start_polling(app.bot)
        except Exception as e:
            logger.error(f"Bot polling terminated with error: {e}")

    tasks.append(asyncio.create_task(run_bot(), name="telegram_bot"))

    # Graceful shutdown handler
    stop_event = asyncio.Event()

    def signal_handler() -> None:
        logger.info("Termination signal received.")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            pass

    try:
        # Wait until stop event or until one of the main tasks fails
        done, pending = await asyncio.wait(
            [asyncio.create_task(stop_event.wait()), *tasks],
            return_when=asyncio.FIRST_COMPLETED,
        )
    finally:
        logger.info("Stopping all running tasks...")
        for t in tasks:
            if not t.done():
                t.cancel()
        await app.shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Application exited.")
