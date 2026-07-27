import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    DATABASE_PATH = os.getenv("DATABASE_PATH", "database/bot.db")
    UPLOAD_PATH = os.getenv("UPLOAD_PATH", "uploads")
    DOWNLOAD_PATH = os.getenv("DOWNLOAD_PATH", "downloads")
    LOG_PATH = os.getenv("LOG_PATH", "logs")
    MAX_FILE_SIZE = int(os.getenv("MAX_FILE_SIZE", "50"))
    MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
    WORKER_INTERVAL = int(os.getenv("WORKER_INTERVAL", "5"))
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
