import asyncio
import logging
import os
import shutil
from datetime import datetime
from config import Config
from database import Database
from utils import move_file, delete_file, ensure_dirs
from telegram import Bot

logger = logging.getLogger(__name__)
db = Database()

class Worker:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.running = True
        self.semaphore = asyncio.Semaphore(Config.MAX_CONCURRENT_JOBS)

    async def stop(self):
        self.running = False

    async def run(self):
        logger.info("Worker started.")
        while self.running:
            try:
                await self._process_pending()
                await asyncio.sleep(Config.WORKER_INTERVAL)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                await asyncio.sleep(5)

    async def _process_pending(self):
        pending = await db.get_pending_tasks()
        if not pending:
            return
        # Process only up to concurrent limit
        for task in pending[:Config.MAX_CONCURRENT_JOBS]:
            current = await db.get_task(task["task_id"])
            if current["status"] != "pending":
                continue
            # We use semaphore to limit concurrency, but since we are iterating, we can just process sequentially.
            # For true concurrency, we'd use asyncio.gather with semaphore.
            # But we'll process one by one to keep it simple.
            await self._process_task(task)

    async def _process_task(self, task: dict):
        task_id = task["task_id"]
        user_id = task["user_id"]
        file_path = task["file_path"]

        await db.update_task_status(task_id, "processing", started_at=datetime.utcnow().isoformat())

        try:
            # Simulate processing – replace with actual logic
            await asyncio.sleep(5)
            base, ext = os.path.splitext(task["original_filename"])
            output_name = f"processed_{base}{ext}"
            output_path = os.path.join(Config.DOWNLOAD_PATH, output_name)
            shutil.copy2(file_path, output_path)

            await db.update_task_status(
                task_id,
                "completed",
                finished_at=datetime.utcnow().isoformat(),
                result_path=output_path
            )

            try:
                with open(output_path, "rb") as f:
                    await self.bot.send_document(
                        chat_id=user_id,
                        document=f,
                        caption=f"✅ APK Processing Complete!\nTask ID: #{task_id}\n\nOriginal: {task['original_filename']}"
                    )
            except Exception as send_err:
                logger.error(f"Failed to send file to user {user_id}: {send_err}")
                await db.update_task_status(
                    task_id,
                    "failed",
                    finished_at=datetime.utcnow().isoformat(),
                    error_message=f"Delivery error: {str(send_err)}"
                )
                await self.bot.send_message(user_id, "⚠️ Processing finished but failed to send file. Please contact admin.")

            delete_file(file_path)
            logger.info(f"Task {task_id} completed for user {user_id}")

        except Exception as e:
            logger.error(f"Task {task_id} failed: {e}")
            await db.update_task_status(
                task_id,
                "failed",
                finished_at=datetime.utcnow().isoformat(),
                error_message=str(e)
            )
            try:
                await self.bot.send_message(
                    user_id,
                    f"❌ Processing failed.\nTask ID: #{task_id}\nPlease try again later."
                )
            except Exception as send_err:
                logger.error(f"Could not notify user {user_id} about failure: {send_err}")
            delete_file(file_path)
