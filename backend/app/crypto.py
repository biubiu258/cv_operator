"""api_key 的对称加密存储（Fernet）。"""
from cryptography.fernet import Fernet

from .config import SECRET_KEY_FILE


def _get_key() -> bytes:
    if SECRET_KEY_FILE.exists():
        return SECRET_KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    SECRET_KEY_FILE.write_bytes(key)
    return key


def encrypt(text: str) -> str:
    if not text:
        return ""
    return Fernet(_get_key()).encrypt(text.encode()).decode()


def decrypt(token: str) -> str:
    if not token:
        return ""
    return Fernet(_get_key()).decrypt(token.encode()).decode()