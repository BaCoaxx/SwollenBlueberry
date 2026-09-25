"""Relaunch decisions for one account.

The machine is pure: callers pass the clock and the latest online/offline
observation. A death and the follow-up launch never happen in the same call,
so the delay cannot collapse into a tight loop.

Rules:
- Nothing relaunches until the user has pressed Launch this session.
- After the client is seen running and then stops, wait ``delay_s`` (3s) and
  start it again when ``auto_relaunch`` is on.
- Stop clears that intent. Later offline observations do not start the client.
- Five deaths inside ``window_s`` (2 minutes) pause relaunch.
- Staying online longer than ``stable_s`` (30s), or a manual Stop/Launch,
  clears the failure window.
"""

from __future__ import annotations

from dataclasses import dataclass, field


DEFAULT_DELAY_S = 3.0
DEFAULT_WINDOW_S = 120.0
DEFAULT_MAX_FAILURES = 5
DEFAULT_STABLE_S = 30.0
PAUSED_MESSAGE = "relaunch paused"


@dataclass
class RelaunchConfig:
    delay_s: float = DEFAULT_DELAY_S
    window_s: float = DEFAULT_WINDOW_S
    max_failures: int = DEFAULT_MAX_FAILURES
    stable_s: float = DEFAULT_STABLE_S


@dataclass
class Decision:
    launch: bool = False
    stop: bool = False
    message: str = ""


@dataclass
class RelaunchMachine:
    config: RelaunchConfig = field(default_factory=RelaunchConfig)
    user_wants_running: bool = False
    online: bool = False
    expecting: bool = False
    offline_since: float | None = None
    came_online_at: float | None = None
    failures: list[float] = field(default_factory=list)
    paused: bool = False
    error: str = ""

    def user_launch(self, now: float) -> Decision:
        self.user_wants_running = True
        self.paused = False
        self.failures.clear()
        self.error = ""
        self.offline_since = None
        self.expecting = True
        return Decision(launch=True)

    def user_stop(self, now: float) -> Decision:
        del now
        self.user_wants_running = False
        self.paused = False
        self.failures.clear()
        self.error = ""
        self.offline_since = None
        self.expecting = False
        self.online = False
        self.came_online_at = None
        return Decision(stop=True)

    def observe(
        self,
        online: bool,
        now: float,
        *,
        auto_relaunch: bool = True,
        confirmed_exit: bool = False,
    ) -> Decision:
        if online:
            if not self.online:
                self.came_online_at = now
            self.online = True
            self.offline_since = None
            self.expecting = False
            if (
                self.came_online_at is not None
                and (now - self.came_online_at) > self.config.stable_s
            ):
                self.failures.clear()
                self.error = ""
                self.paused = False
            return Decision(message=self.error)

        died_now = self.online or (confirmed_exit and self.expecting)
        if died_now and self.user_wants_running:
            paused = self._record_failure(now)
            if paused is not None:
                return paused
            # Arm ``offline_since`` and wait for a later poll. Launching in
            # this same call would skip the delay.
            return Decision(message=self.error)
        if died_now:
            self.online = False
            self.expecting = False
            self.came_online_at = None
            return Decision(message=self.error)

        if self._ready(now, auto_relaunch):
            self.offline_since = None
            self.expecting = True
            return Decision(launch=True)
        return Decision(message=self.error)

    def relaunch_due_in(self, now: float, *, auto_relaunch: bool) -> float | None:
        if not self._pending(auto_relaunch):
            return None
        assert self.offline_since is not None
        return max(0.0, self.config.delay_s - (now - self.offline_since))

    def _pending(self, auto_relaunch: bool) -> bool:
        return bool(
            auto_relaunch
            and self.user_wants_running
            and not self.paused
            and self.offline_since is not None
        )

    def _ready(self, now: float, auto_relaunch: bool) -> bool:
        if not self._pending(auto_relaunch):
            return False
        assert self.offline_since is not None
        return (now - self.offline_since) >= self.config.delay_s

    def _record_failure(self, now: float) -> Decision | None:
        self.online = False
        self.expecting = False
        self.came_online_at = None
        self.failures.append(now)
        self.failures = [stamp for stamp in self.failures if now - stamp <= self.config.window_s]
        if len(self.failures) >= self.config.max_failures:
            self.paused = True
            self.user_wants_running = False
            self.offline_since = None
            self.error = PAUSED_MESSAGE
            return Decision(message=self.error)
        self.offline_since = now
        self.error = ""
        return None
