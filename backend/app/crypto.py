"""API Key 本地加密存储（Fernet 对称加密，密钥文件自动生成）"""
from cryptography.fernet import Fernet

from app.database import DATA_DIR

_KEY_FILE = DATA_DIR / ".secret_key"


def _load_key() -> bytes:
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    return key


def encrypt(plain: str) -> str:
    if not plain:
        return ""
    return Fernet(_load_key()).encrypt(plain.encode()).decode()


def decrypt(enc: str) -> str:
    if not enc:
        return ""
    try:
        return Fernet(_load_key()).decrypt(enc.encode()).decode()
    except Exception:
        return ""
