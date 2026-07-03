import os, json, logging, subprocess, shutil, random, string, uuid, re
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

def obfuscate_apk(input_apk: str, output_apk: str) -> bool:
    ensure_dirs()
    dec_dir = os.path.join(TEMP_DIR, 'dec_' + uuid.uuid4().hex[:6])
    rebuilt = os.path.join(TEMP_DIR, 'rebuilt.apk')
    aligned = os.path.join(TEMP_DIR, 'aligned.apk')
    ks_path = os.path.join(TEMP_DIR, 'rand.keystore')

    if not run_cmd(['apktool', 'd', '-f', '-o', dec_dir, input_apk], timeout=180):
        return False

    try:
        manifest_path = os.path.join(dec_dir, 'AndroidManifest.xml')
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = f.read()

        old_pkg = re.search(r'package="([^"]+)"', manifest).group(1)
        new_pkg = 'com.' + random_string(6) + '.' + random_string(6)

        logger.info(f"Renaming package: {old_pkg} -> {new_pkg}")

        # 1. Replace in manifest
        manifest = manifest.replace(old_pkg, new_pkg)
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(manifest)

        # 2. Replace in all smali files
        smali_dirs = [d for d in os.listdir(dec_dir) if d.startswith('smali')]
        for smali in smali_dirs:
            base = os.path.join(dec_dir, smali)
            for root, dirs, files in os.walk(base):
                for file in files:
                    if file.endswith('.smali'):
                        path = os.path.join(root, file)
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Replace old package name with new one
                        content = content.replace(old_pkg, new_pkg)
                        with open(path, 'w', encoding='utf-8') as f:
                            f.write(content)

        # 3. Rename smali folder structure (optional but good)
        old_path = old_pkg.replace('.', '/')
        new_path = new_pkg.replace('.', '/')
        for smali in smali_dirs:
            base = os.path.join(dec_dir, smali)
            for root, dirs, files in os.walk(base):
                if old_path in root:
                    new_root = root.replace(old_path, new_path)
                    os.makedirs(new_root, exist_ok=True)
                    for file in files:
                        shutil.move(os.path.join(root, file), os.path.join(new_root, file))
            # Remove empty old directories
            for root, dirs, files in os.walk(base, topdown=False):
                if root != base and not os.listdir(root):
                    os.rmdir(root)

        # 4. Randomize some resource file names (just for extra obfuscation)
        res_dir = os.path.join(dec_dir, 'res')
        if os.path.exists(res_dir):
            for root, dirs, files in os.walk(res_dir):
                for file in files:
                    name, ext = os.path.splitext(file)
                    if ext in ('.png', '.jpg', '.xml'):
                        new_name = random_string(10) + ext
                        os.rename(os.path.join(root, file), os.path.join(root, new_name))

        # 5. Rebuild APK
        if not run_cmd(['apktool', 'b', '-o', rebuilt, dec_dir], timeout=180):
            return False

        # 6. Zipalign
        if not run_cmd(['zipalign', '-v', '-p', '4', rebuilt, aligned], timeout=60):
            return False

        # 7. Sign with random keystore
        ks_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        alias = ''.join(random.choices(string.ascii_letters, k=6))
        dname = f"CN={''.join(random.choices(string.ascii_letters, k=5))}, OU=Dev, O=Org, L=Loc, ST=ST, C={random.choice(['US','GB','IN'])}"
        if not run_cmd(['keytool', '-genkey', '-v', '-keystore', ks_path, '-alias', alias, '-keyalg', 'RSA', '-keysize', '2048', '-validity', '365', '-storepass', ks_pass, '-keypass', ks_pass, '-dname', dname], timeout=30):
            return False
        if not run_cmd(['apksigner', 'sign', '--ks', ks_path, '--ks-pass', f'pass:{ks_pass}', '--ks-key-alias', alias, '--out', output_apk, aligned], timeout=30):
            return False

        return True
    except Exception as e:
        logger.exception("Obfuscation failed")
        return False
    finally:
        shutil.rmtree(dec_dir, ignore_errors=True)
        for f in [rebuilt, aligned, ks_path]:
            try: os.remove(f)
            except: pass

# Telegram handlers (unchanged)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("FUD Obfuscation Bot ready. Send APK.")

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("Access denied.")
        return
    doc: Document = update.message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".apk"):
        await update.message.reply_text("Only APK accepted.")
        return
    await update.message.reply_text("Processing... (max 2 min)")
    fin = os.path.join(WORK_DIR, f"{uid}_{doc.file_name}")
    await (await doc.get_file()).download_to_drive(fin)
    base, ext = os.path.splitext(doc.file_name)
    fout = os.path.join(WORK_DIR, f"{base}_fud{ext}")
    success = False
    try:
        success = obfuscate_apk(fin, fout)
    except Exception as e:
        logger.exception("Error")
    try: os.remove(fin)
    except: pass
    if success:
        with open(fout, "rb") as f:
            await update.message.reply_document(document=f, filename=os.path.basename(fout), caption="FUD APK ready.")
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
