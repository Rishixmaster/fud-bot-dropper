import asyncio
import logging
import sys
from telegram.ext import Application
from config import Config
from database import Database
from handlers import get_handlers
from worker import Worker
from utils import ensure_dirs
import os

ensure_dirs()

log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=log_level,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(Config.LOG_PATH, "bot.log"))
    ]
)
logger = logging.getLogger(__name__)

async def main():
    db = Database()
    await db.init()

    application = Application.builder().token(Config.BOT_TOKEN).build()

    for handler in get_handlers():
        application.add_handler(handler)

    worker = Worker(application.bot)
    worker_task = asyncio.create_task(worker.run())
    application.bot_data["worker"] = worker

    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling()

        while True:
            await asyncio.sleep(1)
            if application.bot_data.get("restart", False):
                logger.info("Restart requested. Shutting down...")
                break

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
    finally:
        await worker.stop()
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass
        await application.updater.stop()
        await application.stop()
        await application.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
