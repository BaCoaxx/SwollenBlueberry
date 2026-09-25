"""Start clients and tell whether their process is still alive.

Under Wine the process we spawn may exit while a reparented ``Gw.exe`` keeps
running, so matching uses both the pid we launched and the client path on
another process's command line. Zombies never count as online. ``wmctrl`` is
consulted when it is installed; without it, process status alone is used.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time

import psutil

from gwmultilaunch.launch import LaunchArgError, build_launch_argv, launch_cwd, launch_env
from gwmultilaunch.models import Account
from gwmultilaunch.presence import ProcInfo, matching_pids
from gwmultilaunch.redact import format_command_for_log

logger = logging.getLogger("gwmultilaunch.monitor")

_STOP_WAIT_S = 0.8
_wmctrl_missing = False


class LaunchError(Exception):
    """User-facing start failure. The message must not contain a password."""


class ProcessTracker:
    def __init__(self) -> None:
        self._roots: dict[str, set[int]] = {}
        self._awaiting_exit: dict[str, bool] = {}

    def launch(self, account: Account, *, default_wine: str = "wine") -> int:
        try:
            argv = build_launch_argv(account, default_wine=default_wine)
        except LaunchArgError as exc:
            if "extraargs" in str(exc):
                raise LaunchError("invalid extraargs") from exc
            raise LaunchError("missing client path") from exc
        cwd = launch_cwd(account)
        env = launch_env(account)
        # Log the account id and a redacted command only. Never log raw argv.
        logger.info("launching account %s", account.id)
        logger.debug("command %s", format_command_for_log(argv, account.password))
        try:
            proc = subprocess.Popen(
                argv,
                cwd=cwd,
                env=env,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            raise LaunchError(_safe_os_message(exc)) from None
        self._roots.setdefault(account.id, set()).add(proc.pid)
        self._awaiting_exit[account.id] = True
        return proc.pid

    def is_online(
        self,
        account: Account,
        *,
        window_pids: set[int] | None = None,
    ) -> bool:
        processes = capture_processes()
        return self._state(account, processes, window_pids) == "online"

    def poll_all(
        self,
        accounts: list[Account],
        *,
        window_pids: set[int] | None,
    ) -> dict[str, str]:
        """Return ``online``, ``exited``, or ``offline`` per account id.

        ``exited`` means a launch was outstanding and no live client remains.
        The flag is consumed so a later poll reports ``offline`` instead.
        """
        processes = capture_processes()
        results: dict[str, str] = {}
        for account in accounts:
            state = self._state(account, processes, window_pids)
            if state in {"online", "exited"}:
                self._awaiting_exit[account.id] = False
            if state != "online":
                self._drop_dead_roots(account, processes)
            results[account.id] = state
        return results

    def stop(self, account: Account) -> None:
        self._awaiting_exit[account.id] = False
        processes = capture_processes()
        pids = matching_pids(
            gwpath=account.gwpath,
            root_pids=set(self._roots.get(account.id, set())),
            processes=processes,
            window_pids=None,
            protected_pids=_protected_pids(),
        )
        by_pid = {proc.pid: proc for proc in processes}
        for pid in self._roots.get(account.id, set()):
            # A root that has not published its command line yet still belongs
            # to us. Once a command line exists, only path matches are signaled
            # so a recycled pid is left alone.
            proc = by_pid.get(pid)
            if proc is not None and not proc.cmdline and pid not in pids:
                pids.add(pid)
        for pid in pids:
            _signal_pid(pid, signal.SIGTERM)
        deadline = time.monotonic() + _STOP_WAIT_S
        while time.monotonic() < deadline:
            if not any(_pid_alive(pid) for pid in pids):
                break
            time.sleep(0.05)
        for pid in pids:
            if _pid_alive(pid):
                _signal_pid(pid, signal.SIGKILL)
        self._roots.pop(account.id, None)

    def _state(
        self,
        account: Account,
        processes: list[ProcInfo],
        window_pids: set[int] | None,
    ) -> str:
        live = matching_pids(
            gwpath=account.gwpath,
            root_pids=set(self._roots.get(account.id, set())),
            processes=processes,
            window_pids=window_pids,
            protected_pids=_protected_pids(),
        )
        if live:
            return "online"
        if self._awaiting_exit.get(account.id):
            return "exited"
        return "offline"

    def _drop_dead_roots(self, account: Account, processes: list[ProcInfo]) -> None:
        roots = self._roots.get(account.id)
        if not roots:
            return
        visible = {proc.pid for proc in processes}
        self._roots[account.id] = {pid for pid in roots if pid in visible}


def capture_processes() -> list[ProcInfo]:
    rows: list[ProcInfo] = []
    for proc in psutil.process_iter(["pid", "cmdline", "status", "cwd", "exe"]):
        try:
            info = proc.info
            pid = int(info["pid"])
        except (psutil.Error, TypeError, ValueError, KeyError):
            continue
        cmdline = info.get("cmdline") or []
        rows.append(
            ProcInfo(
                pid=pid,
                cmdline=tuple(str(part) for part in cmdline),
                status=str(info.get("status") or ""),
                cwd=info.get("cwd"),
                exe=info.get("exe"),
            )
        )
    return rows


def query_window_pids() -> set[int] | None:
    """PIDs that own an X11 window, or ``None`` if ``wmctrl`` is unavailable."""
    global _wmctrl_missing
    if _wmctrl_missing:
        return None
    try:
        completed = subprocess.run(
            ["wmctrl", "-lp"],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
            shell=False,
        )
    except FileNotFoundError:
        _wmctrl_missing = True
        return None
    except (subprocess.TimeoutExpired, OSError):
        return None
    if completed.returncode != 0 and not completed.stdout.strip():
        return None
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        parts = line.split()
        # wmctrl -lp: window-id desktop pid host title...
        if len(parts) >= 3:
            try:
                pids.add(int(parts[2]))
            except ValueError:
                continue
    return pids


def _protected_pids() -> set[int]:
    return {os.getpid(), os.getppid()}


def _pid_alive(pid: int) -> bool:
    if pid <= 1 or pid in _protected_pids():
        return False
    try:
        proc = psutil.Process(pid)
        status = proc.status()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False
    return status not in {psutil.STATUS_ZOMBIE, psutil.STATUS_DEAD}


def _signal_pid(pid: int, sig: int) -> None:
    if pid <= 1 or pid in _protected_pids():
        return
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError):
        return


def _safe_os_message(exc: OSError) -> str:
    if isinstance(exc, FileNotFoundError):
        return "executable not found"
    if isinstance(exc, PermissionError):
        return "permission denied"
    if isinstance(exc, NotADirectoryError):
        return "working directory not found"
    return "launch failed"
