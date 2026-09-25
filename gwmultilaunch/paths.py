"""XDG config location."""

from __future__ import annotations

import os
from pathlib import Path


def default_config_dir() -> Path:
    raw = os.environ.get("XDG_CONFIG_HOME", "").strip()
    base = Path(raw) if raw else Path.home() / ".config"
    return base / "gwmultilaunch"
