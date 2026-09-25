"""Decide whether a client process counts as online.

Process status comes from psutil. ``window_pids`` comes from ``wmctrl -lp`` when
that tool exists.

A zombie or dead process is offline, including the case where its X11 window is
already gone. A live process stays online even if wmctrl has not seen a window:
Wine often starts Gw.exe before a window exists, and some prefixes never publish
one that wmctrl can list. When ``wmctrl`` is missing, ``has_window`` is ``None``
and only the process status is used.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


_OFFLINE_STATUSES = {"zombie", "dead", "defunct"}


@dataclass(frozen=True)
class ProcInfo:
    pid: int
    cmdline: tuple[str, ...]
    status: str
    cwd: str | None = None
    exe: str | None = None


def process_counts_as_online(status: str, *, has_window: bool | None) -> bool:
    normalized = (status or "").strip().lower()
    if normalized in _OFFLINE_STATUSES:
        # Zombie + missing window (has_window False) and zombie with no window
        # monitor (has_window None) are both offline. A stale wmctrl hit cannot
        # make a zombie count as online.
        return False
    if not normalized:
        return False
    if has_window is False:
        # Live process, window not listed. Still online; see module docstring.
        return True
    return True


def wine_z_to_unix(arg: str) -> str | None:
    """Map Wine's default ``Z:`` drive path back to a Unix path."""
    if len(arg) < 3 or arg[1] != ":" or arg[0].lower() != "z":
        return None
    rest = arg[2:].replace("\\", "/")
    if not rest.startswith("/"):
        rest = "/" + rest
    return rest


def command_matches_client(
    cmdline: tuple[str, ...] | list[str] | None,
    exe: str | None,
    cwd: str | None,
    gwpath: str,
) -> bool:
    target = _abspath(gwpath)
    if not target:
        return False
    base = os.path.basename(target)
    folder = os.path.dirname(target)
    if _abspath(exe) == target:
        return True
    cwd_abs = _abspath(cwd) if cwd else None
    for arg in cmdline or ():
        if not arg or arg.startswith("-"):
            continue
        if arg == gwpath or arg == target or _abspath(arg) == target:
            return True
        translated = wine_z_to_unix(arg)
        if translated and _abspath(translated) == target:
            return True
        if base and cwd_abs == folder and os.path.basename(arg.replace("\\", "/")) == base:
            return True
    return False


def matching_pids(
    *,
    gwpath: str,
    root_pids: set[int],
    processes: list[ProcInfo],
    window_pids: set[int] | None,
    protected_pids: set[int] | None = None,
) -> set[int]:
    """Pids that belong to this account's client and are actually alive."""
    protected = protected_pids or set()
    by_pid = {proc.pid: proc for proc in processes}
    found: set[int] = set()

    def consider(proc: ProcInfo) -> None:
        if proc.pid <= 1 or proc.pid in protected:
            return
        has_window = None if window_pids is None else proc.pid in window_pids
        if process_counts_as_online(proc.status, has_window=has_window):
            found.add(proc.pid)

    for pid in root_pids:
        proc = by_pid.get(pid)
        if proc is None:
            continue
        if not proc.cmdline or command_matches_client(proc.cmdline, proc.exe, proc.cwd, gwpath):
            consider(proc)

    for proc in processes:
        if command_matches_client(proc.cmdline, proc.exe, proc.cwd, gwpath):
            consider(proc)
    return found


def _abspath(path: str | None) -> str | None:
    if not path:
        return None
    try:
        return os.path.abspath(path)
    except (OSError, ValueError):
        return None
