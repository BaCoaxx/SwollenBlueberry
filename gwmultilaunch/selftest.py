"""Headless checks used by ``gwmultilaunch --self-test`` and DEMO.md."""

from __future__ import annotations

import time

from gwmultilaunch.crypto import CryptoError, decrypt_bytes, encrypt_bytes
from gwmultilaunch.launch import build_launch_argv
from gwmultilaunch.models import Account
from gwmultilaunch.monitor import ProcessTracker
from gwmultilaunch.redact import format_command_for_log
from gwmultilaunch.relaunch import PAUSED_MESSAGE, RelaunchMachine
from gwmultilaunch.standin import standin_script_path


def run_self_test() -> int:
    checks = (
        ("crypto", _check_crypto),
        ("argv", _check_argv),
        ("relaunch", _check_relaunch),
        ("standin", _check_standin),
    )
    for name, check in checks:
        problem = check()
        if problem:
            print(f"self-test failed: {name}: {problem}")
            return 1
        print(f"{name} ok")
    return 0


def _check_crypto() -> str | None:
    secret = "selftest-master"
    token = encrypt_bytes(b'{"ok":true}', secret, iterations=1000)
    if secret.encode() in token or b"ok" not in decrypt_bytes(token, secret):
        return "round trip"
    try:
        decrypt_bytes(token, "other-master")
    except CryptoError:
        return None
    return "wrong password was accepted"


def _check_argv() -> str | None:
    secret = "selftest-secret"
    account = Account(
        id="selftest",
        email="demo@example.com",
        password=secret,
        character="Demo",
        gwpath="/tmp/Gw.exe",
    )
    argv = build_launch_argv(account)
    logged = format_command_for_log(argv, secret)
    if secret not in argv or secret in logged:
        return "password leaked into the log helper"
    if "-character" not in argv:
        return "character argument missing"
    return None


def _check_relaunch() -> str | None:
    machine = RelaunchMachine()
    machine.user_launch(0)
    machine.observe(True, 1, auto_relaunch=True)
    death = machine.observe(False, 10, auto_relaunch=True)
    if death.launch or machine.observe(False, 12.5, auto_relaunch=True).launch:
        return "relaunched before 3 seconds"
    if not machine.observe(False, 13, auto_relaunch=True).launch:
        return "did not relaunch at 3 seconds"
    machine.user_stop(14)
    if machine.observe(False, 30, auto_relaunch=True).launch:
        return "stop did not suppress relaunch"
    machine = RelaunchMachine()
    machine.user_launch(0)
    now = 1.0
    for index in range(5):
        machine.observe(True, now, auto_relaunch=True)
        now += 1
        death = machine.observe(False, now, auto_relaunch=True)
        if index < 4:
            now += 3
            if not machine.observe(False, now, auto_relaunch=True).launch:
                return "expected a relaunch before the fifth failure"
            now += 1
        elif not machine.paused or death.message != PAUSED_MESSAGE or death.launch:
            return "circuit breaker did not pause"
    if machine.observe(False, now + 10, auto_relaunch=True).launch:
        return "paused account relaunched"
    return None


def _check_standin() -> str | None:
    script = standin_script_path()
    if not script.is_file():
        return "stand-in script is missing"
    account = Account(
        id="standin-selftest",
        email="demo@example.com",
        password="selftest-secret",
        character="Demo",
        gwpath=str(script),
        extraargs="--headless",
    )
    tracker = ProcessTracker()
    try:
        tracker.launch(account)
        if not _wait(lambda: tracker.is_online(account), timeout=5):
            return "stand-in did not show as online"
        tracker.stop(account)
        if not _wait(lambda: not tracker.is_online(account), timeout=5):
            return "stand-in did not show as offline"
    except Exception:
        return "stand-in launch failed"
    finally:
        tracker.stop(account)
    return None


def _wait(predicate, timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False
