import time

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from gwmultilaunch.app import MainWindow
from gwmultilaunch.models import Account
from gwmultilaunch.settings import Settings
from gwmultilaunch.standin import standin_script_path


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_dialogs_construct(qapp):
    del qapp
    from gwmultilaunch.dialogs import (
        AccountDialog,
        ChangePasswordDialog,
        MasterPasswordDialog,
        SettingsDialog,
    )

    MasterPasswordDialog(creating=True)
    MasterPasswordDialog(creating=False)
    AccountDialog(None)
    ChangePasswordDialog()
    SettingsDialog(Settings())


def test_window_lists_account_and_launch_stop_round_trip(qapp, tmp_path):
    del qapp
    account = Account(
        id="ui-standin",
        title="Stand-in",
        email="demo@example.com",
        password="super-secret",
        character="Demo",
        gwpath=str(standin_script_path()),
        extraargs="--headless",
    )
    saved: list = []

    def persist_accounts(accounts, new_password):
        saved.append((list(accounts), new_password))

    def persist_settings(settings):
        saved.append(settings)

    window = MainWindow(
        accounts=[account],
        settings=Settings(),
        persist_accounts=persist_accounts,
        persist_settings=persist_settings,
    )
    try:
        window.show()
        QApplication.processEvents()
        assert window.table.rowCount() == 1
        assert window.table.item(0, 1).text() == "Stand-in"
        assert window.table.item(0, 2).text() == "Offline"
        assert "super-secret" not in window.table.item(0, 1).toolTip()
        window._launch(account)
        assert _wait(lambda: window.supervisor.tracker.is_online(account))
        QApplication.processEvents()
        assert window.table.item(0, 2).text() == "Online"
        window._stop(account)
        assert _wait(lambda: not window.supervisor.tracker.is_online(account))
        assert window.table.item(0, 2).text() == "Offline"
        assert all("super-secret" not in str(item) for item in saved)
    finally:
        window.supervisor.stop(account)
        window.close()


def _wait(predicate, timeout: float = 5) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.05)
    return False
