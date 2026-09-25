from gwmultilaunch.relaunch import (
    DEFAULT_DELAY_S,
    DEFAULT_MAX_FAILURES,
    DEFAULT_STABLE_S,
    DEFAULT_WINDOW_S,
    PAUSED_MESSAGE,
    RelaunchConfig,
    RelaunchMachine,
)


def test_defaults_match_spec():
    config = RelaunchConfig()
    assert config.delay_s == DEFAULT_DELAY_S == 3
    assert config.window_s == DEFAULT_WINDOW_S == 120
    assert config.max_failures == DEFAULT_MAX_FAILURES == 5
    assert config.stable_s == DEFAULT_STABLE_S == 30


def test_does_not_launch_until_the_user_starts_it():
    machine = RelaunchMachine()
    assert machine.observe(False, 0, auto_relaunch=True).launch is False
    assert machine.observe(False, 30, auto_relaunch=True).launch is False


def test_relaunches_after_three_seconds_and_not_before():
    machine = RelaunchMachine()
    assert machine.user_launch(0).launch is True
    assert machine.observe(True, 1, auto_relaunch=True).launch is False
    death = machine.observe(False, 10, auto_relaunch=True)
    assert death.launch is False
    assert machine.offline_since == 10
    assert machine.observe(False, 12.999, auto_relaunch=True).launch is False
    assert machine.relaunch_due_in(12.999, auto_relaunch=True) == pytest_approx_delay(10, 12.999)
    relaunch = machine.observe(False, 13, auto_relaunch=True)
    assert relaunch.launch is True
    assert machine.observe(False, 13.1, auto_relaunch=True).launch is False


def test_stop_suppresses_relaunch():
    machine = RelaunchMachine()
    machine.user_launch(0)
    machine.observe(True, 1, auto_relaunch=True)
    machine.observe(False, 5, auto_relaunch=True)
    stopped = machine.user_stop(6)
    assert stopped.stop is True
    assert machine.failures == []
    assert machine.observe(False, 100, auto_relaunch=True).launch is False


def test_auto_relaunch_off_does_not_start_again():
    machine = RelaunchMachine()
    machine.user_launch(0)
    machine.observe(True, 1, auto_relaunch=False)
    assert machine.observe(False, 2, auto_relaunch=False).launch is False
    assert machine.observe(False, 20, auto_relaunch=False).launch is False


def test_five_failures_inside_two_minutes_pause_relaunch():
    machine = RelaunchMachine()
    machine.user_launch(0)
    now = 1.0
    for index in range(5):
        machine.observe(True, now, auto_relaunch=True)
        now += 1
        death = machine.observe(False, now, auto_relaunch=True)
        assert death.launch is False
        if index < 4:
            assert machine.paused is False
            now += 3
            assert machine.observe(False, now, auto_relaunch=True).launch is True
            now += 1
        else:
            assert machine.paused is True
            assert death.message == PAUSED_MESSAGE
            assert len(machine.failures) == 5
    assert machine.observe(False, now + 10, auto_relaunch=True).launch is False


def test_failures_older_than_two_minutes_drop_out():
    machine = RelaunchMachine()
    machine.user_launch(0)
    for die_at in (1, 11, 21, 31):
        machine.observe(True, die_at - 0.5, auto_relaunch=True)
        assert machine.observe(False, die_at, auto_relaunch=True).launch is False
        assert machine.observe(False, die_at + 3, auto_relaunch=True).launch is True
    die_at = 152
    machine.observe(True, die_at - 0.5, auto_relaunch=True)
    death = machine.observe(False, die_at, auto_relaunch=True)
    assert death.launch is False
    assert machine.paused is False
    assert len(machine.failures) == 1
    assert machine.observe(False, die_at + 3, auto_relaunch=True).launch is True


def test_staying_online_more_than_30s_resets_failures():
    machine = RelaunchMachine()
    machine.user_launch(0)
    now = 1.0
    for _ in range(4):
        machine.observe(True, now, auto_relaunch=True)
        now += 1
        machine.observe(False, now, auto_relaunch=True)
        now += 3
        assert machine.observe(False, now, auto_relaunch=True).launch is True
        now += 1
    assert len(machine.failures) == 4
    machine.observe(True, now, auto_relaunch=True)
    machine.observe(True, now + 30, auto_relaunch=True)
    assert len(machine.failures) == 4
    machine.observe(True, now + 30.5, auto_relaunch=True)
    assert machine.failures == []
    assert machine.paused is False


def test_manual_launch_and_stop_reset_the_breaker():
    machine = _paused_machine()
    launched = machine.user_launch(10_000)
    assert launched.launch is True
    assert machine.paused is False
    assert machine.failures == []

    machine = _paused_machine()
    machine.user_stop(10_000)
    assert machine.paused is False
    assert machine.failures == []
    assert machine.error == ""
    assert machine.observe(False, 10_100, auto_relaunch=True).launch is False


def test_failed_start_counts_and_waits():
    machine = RelaunchMachine()
    machine.user_launch(0)
    death = machine.observe(False, 0, auto_relaunch=True, confirmed_exit=True)
    assert death.launch is False
    assert len(machine.failures) == 1
    assert machine.observe(False, 2.9, auto_relaunch=True).launch is False
    assert machine.observe(False, 3, auto_relaunch=True).launch is True


def _paused_machine() -> RelaunchMachine:
    machine = RelaunchMachine()
    machine.user_launch(0)
    now = 1.0
    for _ in range(5):
        machine.observe(True, now, auto_relaunch=True)
        now += 1
        machine.observe(False, now, auto_relaunch=True)
        if not machine.paused:
            now += 3
            machine.observe(False, now, auto_relaunch=True)
            now += 1
    assert machine.paused
    return machine


def pytest_approx_delay(offline_since: float, now: float) -> float:
    return 3 - (now - offline_since)
