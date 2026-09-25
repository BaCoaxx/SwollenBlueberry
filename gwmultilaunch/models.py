"""Account records. Passwords stay out of ``repr`` so a stray log cannot print them."""

from __future__ import annotations

import uuid
from dataclasses import dataclass


def new_account_id() -> str:
    return str(uuid.uuid4())


@dataclass(eq=True, repr=False)
class Account:
    id: str
    email: str
    password: str
    character: str = ""
    gwpath: str = ""
    extraargs: str = ""
    title: str = ""
    wine_prefix: str = ""
    wine_bin: str = ""
    auto_relaunch: bool = True

    def display_name(self) -> str:
        for value in (self.title, self.character, self.email):
            text = value.strip()
            if text:
                return text
        return "(unnamed)"

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "title": self.title,
            "email": self.email,
            "password": self.password,
            "character": self.character,
            "gwpath": self.gwpath,
            "extraargs": self.extraargs,
            "wine_prefix": self.wine_prefix,
            "wine_bin": self.wine_bin,
            "auto_relaunch": self.auto_relaunch,
        }

    @classmethod
    def from_dict(cls, data: object) -> Account:
        if not isinstance(data, dict):
            raise ValueError("account entry must be an object")
        raw_auto = data.get("auto_relaunch", True)
        if isinstance(raw_auto, str):
            auto = raw_auto.strip().lower() in {"1", "true", "yes", "on"}
        else:
            auto = bool(raw_auto)
        account_id = str(data.get("id") or "").strip() or new_account_id()
        return cls(
            id=account_id,
            title=str(data.get("title") or ""),
            email=str(data.get("email") or ""),
            password=str(data.get("password") or ""),
            character=str(data.get("character") or ""),
            gwpath=str(data.get("gwpath") or ""),
            extraargs=str(data.get("extraargs") or ""),
            wine_prefix=str(data.get("wine_prefix") or ""),
            wine_bin=str(data.get("wine_bin") or ""),
            auto_relaunch=auto,
        )

    def __repr__(self) -> str:
        return (
            f"Account(id={self.id!r}, title={self.title!r}, email={self.email!r}, "
            f"password='********', character={self.character!r}, gwpath={self.gwpath!r}, "
            f"extraargs={self.extraargs!r}, wine_prefix={self.wine_prefix!r}, "
            f"wine_bin={self.wine_bin!r}, auto_relaunch={self.auto_relaunch!r})"
        )
