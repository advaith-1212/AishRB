"""
Symmetric encryption for API keys stored in the database.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the cryptography library.
The encryption key is read from the FERNET_KEY environment variable.
In development, a key is auto-generated and saved to .fernet_key (gitignored).
"""

import os

from cryptography.fernet import Fernet

_DIR = os.path.dirname(os.path.abspath(__file__))
_DEV_KEY_FILE = os.path.join(_DIR, '.fernet_key')


def _get_fernet() -> Fernet:
    """Return a Fernet instance using the configured encryption key."""
    key = os.environ.get('FERNET_KEY', '').strip()

    if not key:
        # Dev fallback: auto-generate and persist to .fernet_key
        if os.path.exists(_DEV_KEY_FILE):
            with open(_DEV_KEY_FILE, 'r') as f:
                key = f.read().strip()
        else:
            key = Fernet.generate_key().decode()
            with open(_DEV_KEY_FILE, 'w') as f:
                f.write(key)

    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_api_key(plaintext: str) -> str:
    """Encrypt an API key. Returns a URL-safe base64 string suitable for TEXT columns."""
    if not plaintext:
        return ''
    f = _get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_api_key(ciphertext: str) -> str:
    """Decrypt an API key. Returns the original plaintext string."""
    if not ciphertext:
        return ''
    f = _get_fernet()
    return f.decrypt(ciphertext.encode()).decode()
