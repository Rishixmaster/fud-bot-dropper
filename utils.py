import os
import shutil
from pathlib import Path
from config import Config

def ensure_dirs():
    for path in [Config.UPLOAD_PATH, Config.DOWNLOAD_PATH, Config.LOG_PATH,
                 os.path.dirname(Config.DATABASE_PATH), "temp"]:
        Path(path).mkdir(parents=True, exist_ok=True)

def is_apk(filename: str) -> bool:
    return filename.lower().endswith(".apk")

def get_file_size_mb(file_path: str) -> float:
    return os.path.getsize(file_path) / (1024 * 1024)

async def save_upload_file(file_obj, dest_path: str) -> str:
    await file_obj.download_to_drive(dest_path)
    return dest_path

def move_file(src: str, dst: str) -> str:
    shutil.move(src, dst)
    return dst

def delete_file(path: str) -> None:
    if os.path.exists(path):
        os.remove(path)
