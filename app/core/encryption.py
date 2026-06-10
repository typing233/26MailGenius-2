from cryptography.fernet import Fernet

from app.config import settings

_fernet = None


def _get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        if not settings.encryption_key:
            settings.encryption_key = Fernet.generate_key().decode()
        _fernet = Fernet(settings.encryption_key.encode() if isinstance(settings.encryption_key, str) else settings.encryption_key)
    return _fernet


def encrypt_value(plaintext: str) -> bytes:
    return _get_fernet().encrypt(plaintext.encode())


def decrypt_value(ciphertext: bytes) -> str:
    return _get_fernet().decrypt(ciphertext).decode()
