"""Two copies of the same Gw.exe name, each in its own install folder.

gwlauncher's multi-box model is separate client directories, not one shared
binary. The unit test checks launch paths with no Wine. The integration test
launches the Win32 stand-in through the real Wine path when ``wine`` is on
PATH and skips otherwise.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
import uuid
from pathlib import Path

import psutil
import pytest

from gwmultilaunch.launch import build_launch_argv, launch_cwd
from gwmultilaunch.models import Account
from gwmultilaunch.monitor import ProcessTracker
from gwmultilaunch.presence import command_matches_client
from gwmultilaunch.supervisor import Supervisor

_STANDIN = Path(__file__).resolve().parents[1] / "standin-win" / "gw-standin.exe"
_OFFLINE = {"zombie", "dead", "defunct"}


def test_two_install_folders_have_distinct_launch_paths(tmp_path: Path):
    dir_a, dir_b, account_a, account_b = _two_accounts(tmp_path, prefix="")
    argv_a = build_launch_argv(account_a, default_wine="wine")
    argv_b = build_launch_argv(account_b, default_wine="wine")

    assert os.path.basename(account_a.gwpath) == os.path.basename(account_b.gwpath) == "Gw.exe"
    assert argv_a[0] == argv_b[0] == "wine"
    assert argv_a[1] == str(dir_a / "Gw.exe")
    assert argv_b[1] == str(dir_b / "Gw.exe")
    assert argv_a[1] != argv_b[1]
    assert launch_cwd(account_a) == str(dir_a)
    assert launch_cwd(account_b) == str(dir_b)
    assert launch_cwd(account_a) != launch_cwd(account_b)
    assert argv_a[argv_a.index("-email") + 1] == "alpha@example.com"
    assert argv_b[argv_b.index("-email") + 1] == "beta@example.com"
    assert argv_a[argv_a.index("-character") + 1] == "Alpha"
    assert argv_b[argv_b.index("-character") + 1] == "Beta"


def test_two_wine_install_folders_stay_independent():
    wine = shutil.which("wine")
    if wine is None:
        pytest.skip("wine is not installed")
    if not _STANDIN.is_file():
        pytest.skip(f"Win32 stand-in is missing: {_STANDIN}")

    display, xvfb = _display()
    # Wine refuses a prefix whose parent is not owned by this user (/tmp is not).
    root = Path.home() / ".cache" / "gwmultilaunch-pytest" / uuid.uuid4().hex
    prefix = root / "prefix"
    try:
        dir_a, dir_b, account_a, account_b = _two_accounts(root, prefix=str(prefix))
        shutil.copyfile(_STANDIN, dir_a / "Gw.exe")
        shutil.copyfile(_STANDIN, dir_b / "Gw.exe")
        _init_wine_prefix(wine, prefix, display)

        previous = os.environ.get("DISPLAY")
        os.environ["DISPLAY"] = display
        os.environ["WINEDEBUG"] = "-all"
        tracker = ProcessTracker()
        supervisor = Supervisor(tracker, default_wine=wine)
        try:
            supervisor.launch(account_a)
            supervisor.launch(account_b)
            assert _wait(lambda: tracker.is_online(account_a) and tracker.is_online(account_b), 40), (
                "both install folders should come online"
            )
            cwds_a = _matching_cwds(account_a)
            cwds_b = _matching_cwds(account_b)
            assert launch_cwd(account_a) in cwds_a
            assert launch_cwd(account_b) in cwds_b
            assert launch_cwd(account_b) not in cwds_a
            assert launch_cwd(account_a) not in cwds_b

            supervisor.stop(account_a)
            assert _wait(lambda: not tracker.is_online(account_a), 8)
            assert tracker.is_online(account_b)
            assert launch_cwd(account_b) in _matching_cwds(account_b)
        finally:
            supervisor.stop(account_a)
            supervisor.stop(account_b)
            _wineserver_kill(prefix, display)
            if previous is None:
                os.environ.pop("DISPLAY", None)
            else:
                os.environ["DISPLAY"] = previous
    finally:
        _wineserver_kill(prefix, display)
        if xvfb is not None and xvfb.poll() is None:
            try:
                os.killpg(xvfb.pid, signal.SIGTERM)
            except OSError:
                pass
        shutil.rmtree(root, ignore_errors=True)


def _two_accounts(root: Path, *, prefix: str) -> tuple[Path, Path, Account, Account]:
    dir_a = root / "dir_a"
    dir_b = root / "dir_b"
    dir_a.mkdir(parents=True, exist_ok=True)
    dir_b.mkdir(parents=True, exist_ok=True)
    for folder in (dir_a, dir_b):
        exe = folder / "Gw.exe"
        if not exe.exists():
            exe.write_bytes(b"MZ")
    account_a = Account(
        id="box-a",
        email="alpha@example.com",
        password="box-a-secret",
        character="Alpha",
        gwpath=str(dir_a / "Gw.exe"),
        wine_prefix=prefix,
        auto_relaunch=False,
    )
    account_b = Account(
        id="box-b",
        email="beta@example.com",
        password="box-b-secret",
        character="Beta",
        gwpath=str(dir_b / "Gw.exe"),
        wine_prefix=prefix,
        auto_relaunch=False,
    )
    return dir_a, dir_b, account_a, account_b


def _display() -> tuple[str, subprocess.Popen[bytes] | None]:
    xvfb = shutil.which("Xvfb")
    if xvfb is None:
        display = os.environ.get("DISPLAY", "")
        if not display:
            pytest.skip("wine GUI stand-in needs a display or Xvfb")
        return display, None
    for number in range(80, 100):
        display = f":{number}"
        proc = subprocess.Popen(
            [xvfb, display, "-screen", "0", "640x480x24"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        time.sleep(0.2)
        if proc.poll() is None:
            return display, proc
    pytest.skip("could not start Xvfb for the Wine multi-box test")
    raise AssertionError("unreachable")


def _init_wine_prefix(wine: str, prefix: Path, display: str) -> None:
    prefix.parent.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["DISPLAY"] = display
    env["WINEPREFIX"] = str(prefix)
    env["WINEDEBUG"] = "-all"
    wineboot = shutil.which("wineboot") or wine
    argv = [wineboot, "--init"] if wineboot != wine else [wine, "wineboot", "--init"]
    try:
        completed = subprocess.run(
            argv,
            env=env,
            cwd=str(prefix.parent),
            check=False,
            timeout=90,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError("wine prefix init timed out") from exc
    if completed.returncode != 0:
        tail = (completed.stderr or "").strip().splitlines()[-1:] or ["wineboot failed"]
        raise AssertionError(tail[0])


def _matching_cwds(account: Account) -> set[str]:
    found: set[str] = set()
    for proc in psutil.process_iter(["pid", "cmdline", "cwd", "status", "exe"]):
        try:
            info = proc.info
            status = str(info.get("status") or "").lower()
            if status in _OFFLINE or info["pid"] in {os.getpid(), os.getppid()}:
                continue
            cmdline = tuple(info.get("cmdline") or ())
            cwd = info.get("cwd")
            if not command_matches_client(cmdline, info.get("exe"), cwd, account.gwpath):
                continue
            if cwd:
                found.add(os.path.abspath(cwd))
        except (psutil.Error, OSError):
            continue
    return found


def _wineserver_kill(prefix: Path, display: str) -> None:
    wineserver = shutil.which("wineserver")
    if wineserver is None or not prefix.exists():
        return
    env = os.environ.copy()
    env["WINEPREFIX"] = str(prefix)
    env["DISPLAY"] = display
    env["WINEDEBUG"] = "-all"
    try:
        subprocess.run(
            [wineserver, "-k"],
            env=env,
            check=False,
            timeout=15,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except (subprocess.TimeoutExpired, OSError):
        return


def _wait(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.1)
    return predicate()
