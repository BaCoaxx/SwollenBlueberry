import time

from gwmultilaunch.models import Account
from gwmultilaunch.monitor import ProcessTracker, query_window_pids
from gwmultilaunch.standin import standin_script_path


def test_standin_process_goes_online_then_offline():
    account = Account(
        id="standin",
        email="demo@example.com",
        password="super-secret",
        character="Demo",
        gwpath=str(standin_script_path()),
        extraargs="--headless",
    )
    tracker = ProcessTracker()
    try:
        tracker.launch(account)
        assert _wait(lambda: tracker.is_online(account))
        tracker.stop(account)
        assert _wait(lambda: not tracker.is_online(account))
    finally:
        tracker.stop(account)


def test_wmctrl_missing_returns_none(monkeypatch):
    monkeypatch.setattr("gwmultilaunch.monitor._wmctrl_missing", False)

    def explode(*args, **kwargs):
        del args, kwargs
        raise FileNotFoundError("wmctrl")

    monkeypatch.setattr("gwmultilaunch.monitor.subprocess.run", explode)
    assert query_window_pids() is None


def _wait(predicate, timeout: float = 5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False
