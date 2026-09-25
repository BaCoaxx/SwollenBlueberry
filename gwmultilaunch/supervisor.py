"""Connect the relaunch machine to real processes."""

from __future__ import annotations

import time
from collections.abc import Callable

from gwmultilaunch.models import Account
from gwmultilaunch.monitor import LaunchError, ProcessTracker
from gwmultilaunch.relaunch import PAUSED_MESSAGE, RelaunchMachine

Clock = Callable[[], float]


class Supervisor:
    def __init__(
        self,
        tracker: ProcessTracker | None = None,
        *,
        clock: Clock = time.monotonic,
        default_wine: str = "wine",
    ) -> None:
        self.tracker = tracker or ProcessTracker()
        self.clock = clock
        self.default_wine = default_wine
        self.machines: dict[str, RelaunchMachine] = {}
        self.spawn_errors: dict[str, str] = {}

    def machine_for(self, account_id: str) -> RelaunchMachine:
        machine = self.machines.get(account_id)
        if machine is None:
            machine = RelaunchMachine()
            self.machines[account_id] = machine
        return machine

    def launch(self, account: Account) -> None:
        now = self.clock()
        machine = self.machine_for(account.id)
        machine.user_launch(now)
        if self.tracker.is_online(account):
            machine.observe(True, now, auto_relaunch=account.auto_relaunch)
            self.spawn_errors.pop(account.id, None)
            return
        self._spawn(account)

    def stop(self, account: Account) -> None:
        self.machine_for(account.id).user_stop(self.clock())
        self.spawn_errors.pop(account.id, None)
        self.tracker.stop(account)

    def forget(self, account_id: str) -> None:
        self.machines.pop(account_id, None)
        self.spawn_errors.pop(account_id, None)

    def tick(self, accounts: list[Account], *, window_pids: set[int] | None) -> None:
        now = self.clock()
        presence = self.tracker.poll_all(accounts, window_pids=window_pids)
        for account in accounts:
            state = presence.get(account.id, "offline")
            machine = self.machine_for(account.id)
            decision = machine.observe(
                state == "online",
                now,
                auto_relaunch=account.auto_relaunch,
                confirmed_exit=state == "exited",
            )
            if decision.launch:
                self._spawn(account)

    def row_status(self, account: Account, *, online: bool) -> str:
        machine = self.machine_for(account.id)
        if online:
            return "Online"
        if machine.paused or machine.error == PAUSED_MESSAGE:
            return PAUSED_MESSAGE
        spawn_error = self.spawn_errors.get(account.id)
        if spawn_error:
            return spawn_error
        return "Offline"

    def next_relaunch_delay(self, accounts: list[Account], *, now: float) -> float | None:
        delays = [
            self.machine_for(account.id).relaunch_due_in(now, auto_relaunch=account.auto_relaunch)
            for account in accounts
        ]
        pending = [delay for delay in delays if delay is not None]
        if not pending:
            return None
        return min(pending)

    def _spawn(self, account: Account) -> None:
        machine = self.machine_for(account.id)
        try:
            self.tracker.launch(account, default_wine=self.default_wine)
        except LaunchError as exc:
            self.spawn_errors[account.id] = str(exc)
            machine.observe(
                False,
                self.clock(),
                auto_relaunch=account.auto_relaunch,
                confirmed_exit=True,
            )
            return
        self.spawn_errors.pop(account.id, None)
