"""Master-password vault encryption.

The key is PBKDF2-HMAC-SHA256. The payload is Fernet (AES-128-CBC + HMAC-SHA256).
Salt and iteration count are stored next to the ciphertext; they are not secret.
"""

from __future__ import annotations

import base64
import json
import secrets

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

DEFAULT_ITERATIONS = 600_000
MIN_ITERATIONS = 1
MAX_ITERATIONS = 2_000_000
SALT_BYTES = 16
_KDF = "pbkdf2-hmac-sha256"


class CryptoError(Exception):
    """Wrong master password, or ciphertext that failed authentication."""


class VaultCorruptError(CryptoError):
    """The vault envelope is not a GWMultiLaunch file."""


def encrypt_bytes(
    plaintext: bytes,
    password: str,
    *,
    iterations: int = DEFAULT_ITERATIONS,
) -> bytes:
    if not isinstance(password, str) or password == "":
        raise CryptoError("Master password cannot be empty")
    if not MIN_ITERATIONS <= iterations <= MAX_ITERATIONS:
        raise CryptoError("Iteration count is outside the supported range")
    salt = secrets.token_bytes(SALT_BYTES)
    key = _derive_key(password, salt, iterations)
    token = Fernet(key).encrypt(plaintext)
    envelope = {
        "version": 1,
        "kdf": _KDF,
        "iterations": iterations,
        "salt": base64.b64encode(salt).decode("ascii"),
        "ciphertext": token.decode("ascii"),
    }
    return json.dumps(envelope, separators=(",", ":")).encode("utf-8") + b"\n"


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    if not isinstance(password, str) or password == "":
        raise CryptoError("Master password cannot be empty")
    try:
        envelope = json.loads(blob.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VaultCorruptError("Vault file is unreadable") from exc
    if not isinstance(envelope, dict):
        raise VaultCorruptError("Vault file is unreadable")
    if envelope.get("version") != 1 or envelope.get("kdf") != _KDF:
        raise VaultCorruptError("Unsupported vault format")
    iterations = envelope.get("iterations")
    if not isinstance(iterations, int) or not MIN_ITERATIONS <= iterations <= MAX_ITERATIONS:
        raise VaultCorruptError("Vault iteration count is invalid")
    try:
        salt = base64.b64decode(envelope["salt"], validate=True)
        token = envelope["ciphertext"]
    except (KeyError, TypeError, ValueError) as exc:
        raise VaultCorruptError("Vault file is unreadable") from exc
    if not isinstance(token, str) or len(salt) < SALT_BYTES:
        raise VaultCorruptError("Vault file is unreadable")
    key = _derive_key(password, salt, iterations)
    try:
        return Fernet(key).decrypt(token.encode("ascii"))
    except (InvalidToken, ValueError, TypeError) as exc:
        raise CryptoError("Wrong master password or corrupted vault") from exc


def _derive_key(password: str, salt: bytes, iterations: int) -> bytes:
    try:
        password_bytes = password.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise CryptoError("Master password cannot be encoded") from exc
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=iterations,
    )
    return base64.urlsafe_b64encode(kdf.derive(password_bytes))
