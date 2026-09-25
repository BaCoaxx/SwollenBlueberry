"""Build the Guild Wars launch command.

The official client reads ``-email``, ``-password``, and optional ``-character``
from its own command line. GWMultiLaunch passes those as a subprocess argument
list (``shell=False``). Each value is one argv element, so spaces and quotes are
not interpreted by a shell. The password still appears in the process table,
because that is how the game's login arguments work — the same as gwlauncher.
"""

from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

from gwmultilaunch.models import Account


class LaunchArgError(ValueError):
    """``extraargs`` (or gwpath) cannot be turned into an argument list."""


def is_windows_exe(path: str) -> bool:
    return path.lower().endswith(".exe")


def build_launch_argv(account: Account, *, default_wine: str = "wine") -> list[str]:
    gwpath = account.gwpath.strip()
    if not gwpath:
        raise LaunchArgError("gwpath is empty")
    if is_windows_exe(gwpath):
        wine = account.wine_bin.strip() or (default_wine or "").strip() or "wine"
        argv = [wine, gwpath]
    else:
        argv = native_executable_argv(gwpath)
    argv.extend(["-email", account.email, "-password", account.password])
    character = account.character.strip()
    if character:
        argv.extend(["-character", character])
    extra = account.extraargs.strip()
    if extra:
        try:
            argv.extend(shlex.split(extra, posix=True))
        except ValueError as exc:
            raise LaunchArgError("extraargs has unmatched quotes") from exc
    return argv


def native_executable_argv(gwpath: str) -> list[str]:
    """Run a non-``.exe`` client. Python stand-ins use this interpreter."""
    shebang = _read_shebang(gwpath)
    if shebang is not None and "python" in shebang.lower():
        return [sys.executable, gwpath]
    return [gwpath]


def launch_cwd(account: Account) -> str:
    gwpath = account.gwpath.strip()
    parent = os.path.dirname(os.path.abspath(gwpath))
    return parent or os.sep


def launch_env(
    account: Account,
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    if not is_windows_exe(account.gwpath):
        return env
    prefix = account.wine_prefix.strip()
    if prefix:
        env["WINEPREFIX"] = prefix
    else:
        # Empty prefix means Wine's default (~/.wine), not a prefix inherited
        # from the launcher's environment.
        env.pop("WINEPREFIX", None)
    return env


def _read_shebang(gwpath: str) -> str | None:
    try:
        with Path(gwpath).open("rb") as handle:
            prefix = handle.read(128)
    except OSError:
        return None
    if not prefix.startswith(b"#!"):
        return None
    line = prefix.split(b"\n", 1)[0]
    try:
        return line.decode("utf-8", errors="replace")
    except UnicodeError:
        return None
