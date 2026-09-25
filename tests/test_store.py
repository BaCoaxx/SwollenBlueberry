import os
from pathlib import Path

import pytest

from gwmultilaunch.crypto import CryptoError
from gwmultilaunch.models import Account
from gwmultilaunch.settings import Settings, load_settings
from gwmultilaunch.store import load_accounts, save_accounts


def _account() -> Account:
    return Account(
        id="11111111-1111-4111-8111-111111111111",
        title="Main",
        email="you@example.com",
        password="vault-plaintext-secret",
        character="Hero",
        gwpath="/opt/gw/Gw.exe",
        extraargs="-windowed",
        wine_prefix="/opt/prefix",
        wine_bin="/usr/bin/wine",
        auto_relaunch=False,
    )


def test_account_round_trip_hides_plaintext(tmp_path: Path):
    path = tmp_path / "accounts.enc"
    original = _account()
    save_accounts(path, [original], "master-password-9", iterations=1000)
    raw = path.read_bytes()
    assert b"vault-plaintext-secret" not in raw
    assert b"you@example.com" not in raw
    assert (path.stat().st_mode & 0o777) == 0o600
    loaded = load_accounts(path, "master-password-9")
    assert loaded == [original]


def test_wrong_master_password(tmp_path: Path):
    path = tmp_path / "accounts.enc"
    save_accounts(path, [_account()], "master-password-9", iterations=1000)
    with pytest.raises(CryptoError):
        load_accounts(path, "nope-nope-nope")


def test_change_master_password(tmp_path: Path):
    path = tmp_path / "accounts.enc"
    accounts = [_account()]
    save_accounts(path, accounts, "old-password-xx", iterations=1000)
    save_accounts(path, accounts, "new-password-yy", iterations=1000)
    with pytest.raises(CryptoError):
        load_accounts(path, "old-password-xx")
    assert load_accounts(path, "new-password-yy") == accounts


def test_settings_round_trip(tmp_path: Path):
    path = tmp_path / "settings.json"
    from gwmultilaunch.settings import save_settings

    save_settings(path, Settings(wine_bin=" /usr/bin/wine ", poll_interval_ms=50))
    loaded = load_settings(path)
    assert loaded.wine_bin == "/usr/bin/wine"
    assert loaded.poll_interval_ms == 250
    assert "password" not in path.read_text(encoding="utf-8")


def test_corrupt_settings_fall_back(tmp_path: Path):
    path = tmp_path / "settings.json"
    path.write_text("{", encoding="utf-8")
    assert load_settings(path) == Settings()


def test_directory_mode(tmp_path: Path):
    path = tmp_path / "cfg" / "accounts.enc"
    save_accounts(path, [], "master-password-9", iterations=1000)
    assert (path.parent.stat().st_mode & 0o777) == 0o700
    assert os.path.isfile(path)
