import logging
from pathlib import Path

import pytest

from gwmultilaunch.launch import LaunchArgError, build_launch_argv, launch_cwd, launch_env
from gwmultilaunch.models import Account
from gwmultilaunch.monitor import LaunchError, ProcessTracker
from gwmultilaunch.redact import format_command_for_log


def _exe_account(**overrides) -> Account:
    data = dict(
        id="acc",
        email="user name@example.com",
        password="s3cret 'quote'",
        character="A B",
        gwpath="/opt/gw/Gw.exe",
        extraargs="",
        wine_prefix="",
        wine_bin="",
    )
    data.update(overrides)
    return Account(**data)


def test_argv_includes_password_and_log_helper_does_not():
    password = "s3cret 'quote'"
    account = _exe_account(extraargs='-windowed -title "My Client"')
    argv = build_launch_argv(account, default_wine="wine")
    assert argv[:6] == [
        "wine",
        "/opt/gw/Gw.exe",
        "-email",
        "user name@example.com",
        "-password",
        password,
    ]
    assert argv[6:8] == ["-character", "A B"]
    assert argv[8:] == ["-windowed", "-title", "My Client"]
    logged = format_command_for_log(argv, password)
    assert password not in logged
    assert "********" in logged
    assert "-password" in logged


def test_character_omitted_when_blank():
    argv = build_launch_argv(_exe_account(character="   "))
    assert "-character" not in argv


def test_custom_wine_bin_and_unmatched_extraargs():
    argv = build_launch_argv(_exe_account(wine_bin="/opt/wine/bin/wine"))
    assert argv[0] == "/opt/wine/bin/wine"
    account = _exe_account(extraargs='"', password="super-secret")
    with pytest.raises(LaunchArgError):
        build_launch_argv(account)


def test_native_client_is_not_prefixed_with_wine(tmp_path: Path):
    script = tmp_path / "gw-standin"
    script.write_text("#!/usr/bin/env python3\nprint('no')\n", encoding="utf-8")
    account = _exe_account(gwpath=str(script), character="")
    argv = build_launch_argv(account)
    assert argv[0] != "wine"
    assert argv[1] == str(script)
    assert "-email" in argv
    assert "-character" not in argv


def test_wine_prefix_env():
    account = _exe_account(wine_prefix="/opt/prefix")
    env = launch_env(account, {"PATH": "/usr/bin", "WINEPREFIX": "/inherited"})
    assert env["WINEPREFIX"] == "/opt/prefix"
    env = launch_env(_exe_account(), {"PATH": "/usr/bin", "WINEPREFIX": "/inherited"})
    assert "WINEPREFIX" not in env
    native = _exe_account(gwpath="/tmp/standin")
    env = launch_env(native, {"WINEPREFIX": "/inherited"})
    assert env["WINEPREFIX"] == "/inherited"


def test_cwd_is_client_directory():
    account = _exe_account(gwpath="/opt/client/Gw.exe")
    assert launch_cwd(account) == "/opt/client"


def test_popen_uses_argument_list_and_does_not_log_password(monkeypatch, caplog, tmp_path: Path):
    password = "super-secret"
    gwpath = tmp_path / "Gw.exe"
    account = _exe_account(
        password=password,
        gwpath=str(gwpath),
        wine_prefix=str(tmp_path / "prefix"),
        extraargs="-windowed",
        character="",
    )
    captured: dict = {}

    class FakeProc:
        pid = 4242

    def fake_popen(argv, **kwargs):
        captured["argv"] = argv
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr("gwmultilaunch.monitor.subprocess.Popen", fake_popen)
    with caplog.at_level(logging.DEBUG, logger="gwmultilaunch.monitor"):
        pid = ProcessTracker().launch(account, default_wine="wine")
    assert pid == 4242
    assert captured["kwargs"].get("shell", False) is False
    assert captured["kwargs"]["cwd"] == str(tmp_path)
    assert captured["kwargs"]["env"]["WINEPREFIX"] == str(tmp_path / "prefix")
    assert captured["argv"] == ["wine", str(gwpath), "-email", account.email, "-password", password, "-windowed"]
    assert password in captured["argv"]
    assert password not in caplog.text


def test_invalid_extraargs_error_has_no_password(tmp_path: Path):
    account = _exe_account(password="super-secret", gwpath=str(tmp_path / "Gw.exe"), extraargs='"')
    with pytest.raises(LaunchError) as caught:
        ProcessTracker().launch(account)
    assert str(caught.value) == "invalid extraargs"
    assert "super-secret" not in str(caught.value)


def test_package_never_opts_into_shell():
    root = Path(__file__).resolve().parents[1] / "gwmultilaunch"
    for path in root.rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert "shell=True" not in text
        assert "shell = True" not in text
