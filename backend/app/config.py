"""应用级配置与路径。"""
from pathlib import Path

# backend/ 目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 数据与输出目录（数据库为单文件，非文件夹式存储）
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"
SECRET_KEY_FILE = BASE_DIR / ".secret.key"

DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR / 'resume.db'}"