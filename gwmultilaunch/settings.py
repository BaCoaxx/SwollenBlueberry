"""Non-secret launcher settings."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Settings:
    wine_bin: str = "wine"
    poll_interval_ms: int = 1000

    def normalized(self) -> Settings:
        wine = self.wine_bin.strip() or "wine"
        try:
            poll = int(self.poll_interval_ms)
        except (TypeError, ValueError):
            poll = 1000
        poll = max(250, min(poll, 10_000))
        return Settings(wine_bin=wine, poll_interval_ms=poll)

    def to_dict(self) -> dict[str, object]:
        current = self.normalized()
        return {"wine_bin": current.wine_bin, "poll_interval_ms": current.poll_interval_ms}


def load_settings(path: Path) -> Settings:
    if not path.exists():
        return Settings()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return Settings()
    if not isinstance(data, dict):
        return Settings()
    return Settings(
        wine_bin=str(data.get("wine_bin") or "wine"),
        poll_interval_ms=int(data.get("poll_interval_ms") or 1000),
    ).normalized()


def save_settings(path: Path, settings: Settings) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(settings.normalized().to_dict(), indent=2) + "\n"
    path.write_text(payload, encoding="utf-8")
