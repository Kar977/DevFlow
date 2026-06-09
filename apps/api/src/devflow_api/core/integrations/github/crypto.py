"""Symmetric encryption for GitHub access tokens at rest (Fernet/AES-128)."""

from cryptography.fernet import Fernet


class TokenCipher:
    """Encrypts and decrypts secrets using a Fernet key from configuration."""

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError(
                "github_token_encryption_key is not configured; "
                "cannot encrypt GitHub tokens."
            )
        self._fernet = Fernet(key.encode())

    def encrypt(self, plaintext: str) -> str:
        return self._fernet.encrypt(plaintext.encode()).decode()

    def decrypt(self, ciphertext: str) -> str:
        return self._fernet.decrypt(ciphertext.encode()).decode()
