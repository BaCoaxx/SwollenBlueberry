"""Read and write the encrypted account vault."""

from __future__ import annotations

import json
import os
from pathlib import Path

from gwmultilaunch.crypto import decrypt_bytes, encrypt_bytes
from gwmultilaunch.models import Account, new_account_id
from gwmultilaunch.settings import Settings, load_settings, save_settings

_PAYLOAD_VERSION = 1


def save_accounts(
    path: Path,
    accounts: list[Account],
    password: str,
    *,
    iterations: int | None = None,
) -> None:
    payload = {
        "version": _PAYLOAD_VERSION,
        "accounts": [account.to_dict() for account in accounts],
    }
    plaintext = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    kwargs = {} if iterations is None else {"iterations": iterations}
    blob = encrypt_bytes(plaintext, password, **kwargs)
    _write_secret(path, blob)


def load_accounts(path: Path, password: str) -> list[Account]:
    blob = path.read_bytes()
    plaintext = decrypt_bytes(blob, password)
    try:
        data = json.loads(plaintext.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Decrypted vault is not valid account data") from exc
    if not isinstance(data, dict) or data.get("version") != _PAYLOAD_VERSION:
        raise ValueError("Decrypted vault is not valid account data")
    raw_accounts = data.get("accounts")
    if not isinstance(raw_accounts, list):
        raise ValueError("Decrypted vault is not valid account data")
    accounts: list[Account] = []
    seen: set[str] = set()
    for item in raw_accounts:
        account = Account.from_dict(item)
        if account.id in seen:
            account.id = new_account_id()
        seen.add(account.id)
        accounts.append(account)
    return accounts


class Vault:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.accounts_path = directory / "accounts.enc"
        self.settings_path = directory / "settings.json"

    def exists(self) -> bool:
        return self.accounts_path.is_file()

    def load_accounts(self, password: str) -> list[Account]:
        return load_accounts(self.accounts_path, password)

    def save_accounts(
        self,
        accounts: list[Account],
        password: str,
        *,
        iterations: int | None = None,
    ) -> None:
        save_accounts(self.accounts_path, accounts, password, iterations=iterations)

    def load_settings(self) -> Settings:
        return load_settings(self.settings_path)

    def save_settings(self, settings: Settings) -> None:
        save_settings(self.settings_path, settings)


def _write_secret(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path.parent, 0o700)
    except OSError:
        pass
    tmp = path.with_name(path.name + ".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, data)
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(tmp, 0o600)
    os.replace(tmp, path)
    os.chmod(path, 0o600)
