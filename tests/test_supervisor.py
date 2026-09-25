from gwmultilaunch.models import Account
from gwmultilaunch.monitor import LaunchError
from gwmultilaunch.supervisor import Supervisor


class FakeTracker:
    def __init__(self) -> None:
        self.online = False
        self.launches = 0
        self.stops = 0
        self.awaiting = False
        self.fail = False

    def is_online(self, account, window_pids=None):
        del account, window_pids
        return self.online

    def poll_all(self, accounts, window_pids=None):
        del window_pids
        result = {}
        for account in accounts:
            if self.online:
                self.awaiting = False
                result[account.id] = "online"
            elif self.awaiting:
                self.awaiting = False
                result[account.id] = "exited"
            else:
                result[account.id] = "offline"
        return result

    def launch(self, account, default_wine="wine"):
        del account, default_wine
        if self.fail:
            raise LaunchError("executable not found")
        self.launches += 1
        self.awaiting = True
        self.online = True
        return 123

    def stop(self, account):
        del account
        self.stops += 1
        self.online = False
        self.awaiting = False


def _account(**overrides) -> Account:
    data = dict(
        id="1",
        email="a@b.c",
        password="super-secret",
        gwpath="/opt/gw/Gw.exe",
        auto_relaunch=True,
    )
    data.update(overrides)
    return Account(**data)


def test_supervisor_waits_three_seconds_then_relaunches():
    clock = {"now": 0.0}
    tracker = FakeTracker()
    supervisor = Supervisor(tracker, clock=lambda: clock["now"])
    account = _account()
    supervisor.launch(account)
    assert tracker.launches == 1
    clock["now"] = 1
    supervisor.tick([account], window_pids=None)
    tracker.online = False
    clock["now"] = 5
    supervisor.tick([account], window_pids=None)
    assert tracker.launches == 1
    clock["now"] = 8
    supervisor.tick([account], window_pids=None)
    assert tracker.launches == 2


def test_supervisor_stop_suppresses_relaunch():
    clock = {"now": 0.0}
    tracker = FakeTracker()
    supervisor = Supervisor(tracker, clock=lambda: clock["now"])
    account = _account()
    supervisor.launch(account)
    clock["now"] = 1
    supervisor.tick([account], window_pids=None)
    tracker.online = False
    clock["now"] = 5
    supervisor.tick([account], window_pids=None)
    supervisor.stop(account)
    clock["now"] = 30
    supervisor.tick([account], window_pids=None)
    assert tracker.launches == 1
    assert tracker.stops == 1


def test_spawn_error_does_not_contain_the_password():
    tracker = FakeTracker()
    tracker.fail = True
    supervisor = Supervisor(tracker, clock=lambda: 0.0)
    account = _account()
    supervisor.launch(account)
    message = supervisor.spawn_errors[account.id]
    assert message == "executable not found"
    assert account.password not in message
    assert supervisor.row_status(account, online=False) == "executable not found"
    assert supervisor.machine_for(account.id).failures == [0.0]
