import base64
import os

from cryptography.fernet import Fernet
from flask import current_app


class EncryptionService:
    """Field-level encryption using Fernet symmetric encryption.
    Uses FIELD_ENCRYPTION_KEY_PATH (separate from DB_ENCRYPTION_KEY_PATH
    used by SQLCipher) to avoid key format conflicts."""
    _fernet = None

    @classmethod
    def _get_fernet(cls):
        if cls._fernet is not None:
            return cls._fernet

        key_path = current_app.config.get('FIELD_ENCRYPTION_KEY_PATH')
        if not key_path:
            raise RuntimeError('FIELD_ENCRYPTION_KEY_PATH not configured.')

        if os.path.exists(key_path):
            with open(key_path, 'rb') as f:
                key = f.read().strip()
            # Validate it's a valid Fernet key
            Fernet(key)
        else:
            key = Fernet.generate_key()
            os.makedirs(os.path.dirname(key_path), exist_ok=True)
            with open(key_path, 'wb') as f:
                f.write(key)
            os.chmod(key_path, 0o600)

        cls._fernet = Fernet(key)
        return cls._fernet

    @classmethod
    def reset(cls):
        cls._fernet = None

    @staticmethod
    def encrypt(plaintext):
        if not plaintext:
            return plaintext
        fernet = EncryptionService._get_fernet()
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        return base64.urlsafe_b64encode(fernet.encrypt(plaintext)).decode('ascii')

    @staticmethod
    def decrypt(ciphertext):
        if not ciphertext:
            return ciphertext
        fernet = EncryptionService._get_fernet()
        raw = base64.urlsafe_b64decode(ciphertext.encode('ascii'))
        return fernet.decrypt(raw).decode('utf-8')

    @staticmethod
    def is_encrypted(value):
        if not value or not isinstance(value, str):
            return False
        try:
            raw = base64.urlsafe_b64decode(value.encode('ascii'))
            EncryptionService._get_fernet().decrypt(raw)
            return True
        except Exception:
            return False

    @staticmethod
    def mask(value, visible_chars=4):
        if not value:
            return value
        if len(value) <= visible_chars:
            return '*' * len(value)
        return '*' * (len(value) - visible_chars) + value[-visible_chars:]
