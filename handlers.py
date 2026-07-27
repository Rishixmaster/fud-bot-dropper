import logging
from telegram import Update, Document
from telegram.ext import ContextTypes, CommandHandler, MessageHandler, filters
from config import Config
from database import Database
from utils import is_apk, get_file_size_mb, save_upload_file, ensure_dirs
import os
from datetime import datetime

logger = logging.getLogger(__name__)
db = Database()

# -------------------- Start Command --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.add_user(user.id, user.username, user.first_name, user.last_name)
    welcome_text = (
        f"👋 Welcome, {user.first_name}!\n\n"
        "Send me an APK file and I will process it.\n"
        "Use /status to check your tasks.\n"
        "Admins: use /stats, /users, /queue, /tasks, /restart, /logs"
    )
    await update.message.reply_text(welcome_text)

# -------------------- APK Upload Handler --------------------
async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    document: Document = update.message.document

    if not document:
        await update.message.reply_text("Please send a file.")
        return

    if not is_apk(document.file_name):
        await update.message.reply_text("❌ Only APK files are allowed.")
        return

    file_size_mb = document.file_size / (1024 * 1024)
    if file_size_mb > Config.MAX_FILE_SIZE:
        await update.message.reply_text(
            f"❌ File too large. Max size: {Config.MAX_FILE_SIZE} MB"
        )
        return

    ensure_dirs()

    file = await document.get_file()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    save_path = os.path.join(Config.UPLOAD_PATH, f"{user.id}_{timestamp}_{document.file_name}")
    await save_upload_file(file, save_path)

    task_id = await db.add_task(user.id, document.file_name, save_path)

    await update.message.reply_text(
        f"✅ APK Received.\nTask ID: #{task_id}\n\n⏳ Processing..."
    )

    logger.info(f"User {user.id} uploaded {document.file_name}, task {task_id}")

# -------------------- Status Command --------------------
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tasks = await db.get_tasks_by_user(user.id, limit=10)
    if not tasks:
        await update.message.reply_text("📭 No tasks found.")
        return

    lines = ["📋 Your recent tasks:"]
    for t in tasks:
        status_emoji = {
            "pending": "⏳",
            "processing": "🔄",
            "completed": "✅",
            "failed": "❌"
        }.get(t["status"], "❓")
        lines.append(f"{status_emoji} #{t['task_id']} – {t['original_filename']} – {t['status']}")
    await update.message.reply_text("\n".join(lines))

# -------------------- Admin Commands --------------------
async def admin_only(func):
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id != Config.ADMIN_ID:
            await update.message.reply_text("⛔ You are not authorized.")
            return
        await func(update, context)
    return wrapper

@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    counts = await db.count_tasks_by_status()
    total_users = len(await db.get_all_users())
    text = (
        f"📊 Statistics\n"
        f"Users: {total_users}\n"
        f"Pending: {counts['pending']}\n"
        f"Processing: {counts['processing']}\n"
        f"Completed: {counts['completed']}\n"
        f"Failed: {counts['failed']}"
    )
    await update.message.reply_text(text)

@admin_only
async def users_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    users = await db.get_all_users()
    if not users:
        await update.message.reply_text("No users.")
        return
    lines = ["👥 Users:"]
    for u in users[:20]:
        lines.append(f"{u['user_id']} – @{u['username'] or 'N/A'} ({u['first_name']})")
    await update.message.reply_text("\n".join(lines))

@admin_only
async def queue_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    pending = await db.get_pending_tasks()
    if not pending:
        await update.message.reply_text("📭 Queue is empty.")
        return
    lines = ["⏳ Pending tasks:"]
    for t in pending[:20]:
        lines.append(f"#{t['task_id']} – {t['original_filename']} (user {t['user_id']})")
    await update.message.reply_text("\n".join(lines))

@admin_only
async def tasks_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tasks = await db.get_all_tasks(limit=20)
    if not tasks:
        await update.message.reply_text("No tasks.")
        return
    lines = ["📋 Recent tasks:"]
    for t in tasks:
        lines.append(f"#{t['task_id']} – {t['original_filename']} – {t['status']}")
    await update.message.reply_text("\n".join(lines))

@admin_only
async def restart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🔄 Restarting bot...")
    context.bot_data["restart"] = True

@admin_only
async def logs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logs = await db.get_recent_logs(limit=20)
    if not logs:
        await update.message.reply_text("No logs.")
        return
    lines = ["📜 Recent logs:"]
    for log in logs:
        lines.append(f"[{log['level']}] {log['message']}")
    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "..."
    await update.message.reply_text(text)

# -------------------- Handlers Registration --------------------
def get_handlers():
    return [
        CommandHandler("start", start),
        CommandHandler("status", status),
        CommandHandler("stats", stats),
        CommandHandler("users", users_cmd),
        CommandHandler("queue", queue_cmd),
        CommandHandler("tasks", tasks_cmd),
        CommandHandler("restart", restart_cmd),
        CommandHandler("logs", logs_cmd),
        MessageHandler(filters.Document.ALL, handle_document),
    ]
