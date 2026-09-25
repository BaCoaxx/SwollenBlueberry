import json
from pathlib import Path

import pytest

from gwmultilaunch.crypto import (
    DEFAULT_ITERATIONS,
    MAX_ITERATIONS,
    CryptoError,
    VaultCorruptError,
    decrypt_bytes,
    encrypt_bytes,
)


def test_default_iterations_are_high():
    assert DEFAULT_ITERATIONS >= 600_000


def test_round_trip_and_wrong_password():
    secret = "correct horse battery"
    payload = '{"accounts":[{"password":"päss wörd"}]}'.encode()
    blob = encrypt_bytes(payload, secret, iterations=1000)
    assert secret.encode() not in blob
    assert "päss".encode() not in blob
    assert decrypt_bytes(blob, secret) == payload
    with pytest.raises(CryptoError):
        decrypt_bytes(blob, "definitely-wrong")


def test_empty_master_password_rejected():
    with pytest.raises(CryptoError):
        encrypt_bytes(b"{}", "", iterations=1000)


def test_tamper_fails():
    blob = encrypt_bytes(b"hello", "master-password", iterations=1000)
    flipped = bytearray(blob)
    flipped[-4] ^= 0x20
    with pytest.raises(CryptoError):
        decrypt_bytes(bytes(flipped), "master-password")


def test_iterations_are_read_from_the_file():
    blob = encrypt_bytes(b"payload", "master-password", iterations=1000)
    envelope = json.loads(blob)
    assert envelope["iterations"] == 1000
    assert decrypt_bytes(blob, "master-password") == b"payload"


def test_excessive_iterations_rejected():
    envelope = {
        "version": 1,
        "kdf": "pbkdf2-hmac-sha256",
        "iterations": MAX_ITERATIONS + 1,
        "salt": "AAAAAAAAAAAAAAAAAAAAAA==",
        "ciphertext": "not-used",
    }
    with pytest.raises(VaultCorruptError):
        decrypt_bytes(json.dumps(envelope).encode(), "master-password")


def test_corrupt_envelope():
    with pytest.raises(VaultCorruptError):
        decrypt_bytes(b"not-json", "master-password")
