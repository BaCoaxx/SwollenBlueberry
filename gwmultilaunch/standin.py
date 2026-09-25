"""Native stand-in client for tests and ``--demo``.

This is not Guild Wars. It stays running until it is closed or signaled, so the
launcher can practice online/offline detection without Wine. Arguments that
look like the game's login flags are accepted and discarded. The password is
never stored or printed.
"""

from __future__ import annotations

import os
import signal
import sys
import time
from pathlib import Path


def standin_script_path() -> Path:
    return Path(__file__).resolve().parent / "assets" / "gw-standin"


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    force_headless = "--headless" in args or os.environ.get("GWMULTILAUNCH_STANDIN_HEADLESS") == "1"
    force_gui = "--gui" in args and not force_headless
    character = _character_only(args)
    if force_headless or (not force_gui and not _have_display()):
        return _run_headless()
    return _run_gui(character)


def _character_only(argv: list[str]) -> str:
    character = ""
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "-character" and index + 1 < len(argv):
            character = argv[index + 1]
            index += 2
            continue
        if arg in {"-email", "-password"} and index + 1 < len(argv):
            index += 2
            continue
        index += 1
    return character


def _have_display() -> bool:
    return bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))


def _run_headless() -> int:
    stop = False

    def _handle(signum: int, _frame: object) -> None:
        del signum
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    while not stop:
        time.sleep(0.1)
    return 0


def _run_gui(character: str) -> int:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    app = QApplication.instance() or QApplication(sys.argv)
    window = QWidget()
    window.setWindowTitle("GW stand-in")
    layout = QVBoxLayout(window)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(8)
    title = QLabel("GWMultiLaunch stand-in")
    title.setStyleSheet("font-size: 16px; font-weight: 600;")
    shown = character.strip() or "(none)"
    body = QLabel(
        f"Character: {shown}\n\nClose this window to simulate the client exiting."
    )
    body.setWordWrap(True)
    body.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    layout.addWidget(title)
    layout.addWidget(body)
    window.resize(420, 180)
    window.show()
    return int(app.exec())


if __name__ == "__main__":
    raise SystemExit(main())
