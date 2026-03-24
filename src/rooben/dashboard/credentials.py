"""Fernet encryption helper for integration credentials."""

from __future__ import annotations

from pathlib import Path

from cryptography.fernet import Fernet


_fernet: Fernet | None = None


def get_fernet() -> Fernet:
    """Get or create a Fernet instance for credential encryption.

    Key resolution order:
    1. ROOBEN_CREDENTIAL_KEY env var
    2. .rooben/.credential_key file
    3. Auto-generate and write to .rooben/.credential_key
    """
    global _fernet
    if _fernet is not None:
        return _fernet

    from rooben.config import get_settings
    key = get_settings().rooben_credential_key or None
    key_path = Path(".rooben/.credential_key")

    if not key and key_path.exists():
        key = key_path.read_text().strip()

    if not key:
        key = Fernet.generate_key().decode()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(key)

    _fernet = Fernet(key.encode() if isinstance(key, str) else key)
    return _fernet


def encrypt_value(plaintext: str) -> str:
    """Encrypt a plaintext value and return the ciphertext as a string."""
    f = get_fernet()
    return f.encrypt(plaintext.encode()).decode()


def decrypt_value(ciphertext: str) -> str:
    """Decrypt a ciphertext string and return the plaintext."""
    f = get_fernet()
    return f.decrypt(ciphertext.encode()).decode()


def reset_fernet() -> None:
    """Reset cached Fernet instance (for testing)."""
    global _fernet
    _fernet = None
