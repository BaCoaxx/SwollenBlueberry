"""Format commands for logs without echoing account passwords."""

from __future__ import annotations

import shlex


def redact_secrets(text: str, secrets: list[str]) -> str:
    redacted = text
    for secret in sorted((item for item in secrets if item), key=len, reverse=True):
        redacted = redacted.replace(secret, "********")
    return redacted


def format_command_for_log(argv: list[str], password: str) -> str:
    """Shell-quoted argv with the ``-password`` value and any copy of it masked."""
    redacted: list[str] = []
    mask_next = False
    secrets = [password] if password else []
    for arg in argv:
        if mask_next:
            redacted.append("********")
            mask_next = False
            continue
        if arg == "-password":
            redacted.append(arg)
            mask_next = True
            continue
        redacted.append(redact_secrets(arg, secrets))
    return " ".join(shlex.quote(part) for part in redacted)
