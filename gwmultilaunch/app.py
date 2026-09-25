"""PySide6 window for GWMultiLaunch."""

from __future__ import annotations

import os
import sys
import time
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QAction, QPainter, QCloseEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gwmultilaunch import __version__
from gwmultilaunch.crypto import CryptoError, VaultCorruptError
from gwmultilaunch.dialogs import (
    AccountDialog,
    ChangePasswordDialog,
    MasterPasswordDialog,
    SettingsDialog,
)
from gwmultilaunch.models import Account, new_account_id
from gwmultilaunch.monitor import query_window_pids
from gwmultilaunch.paths import default_config_dir
from gwmultilaunch.relaunch import PAUSED_MESSAGE
from gwmultilaunch.settings import Settings
from gwmultilaunch.standin import standin_script_path
from gwmultilaunch.store import Vault
from gwmultilaunch.supervisor import Supervisor
from gwmultilaunch.theme import app_icon, apply_theme

PersistAccounts = Callable[[list[Account], str | None], None]
PersistSettings = Callable[[Settings], None]


class StatusDot(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._online = False
        self.setFixedSize(18, 18)

    def set_online(self, online: bool) -> None:
        if self._online != online:
            self._online = online
            self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 Qt override
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#3ddc97" if self._online else "#f07178"))
        painter.drawEllipse(4, 4, 10, 10)
        painter.end()


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        accounts: list[Account],
        settings: Settings,
        persist_accounts: PersistAccounts,
        persist_settings: PersistSettings,
        supervisor: Supervisor | None = None,
    ) -> None:
        super().__init__()
        self.accounts = list(accounts)
        self.settings = settings.normalized()
        self._persist_accounts = persist_accounts
        self._persist_settings = persist_settings
        self.supervisor = supervisor or Supervisor(default_wine=self.settings.wine_bin)
        self.supervisor.default_wine = self.settings.wine_bin
        self._dots: dict[str, StatusDot] = {}
        self._in_tick = False
        self._notice = ""
        self._notice_until = 0.0

        self.setWindowTitle("GWMultiLaunch")
        self.setWindowIcon(app_icon())
        self.resize(760, 480)
        self.setMinimumSize(640, 360)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(16, 14, 16, 12)
        root.setSpacing(10)

        title = QLabel("GWMultiLaunch")
        title.setObjectName("title")
        subtitle = QLabel("Each account needs its own Gw.exe and Gw.dat folder.")
        subtitle.setObjectName("muted")
        root.addWidget(title)
        root.addWidget(subtitle)

        bar = QHBoxLayout()
        self._add_btn = QPushButton("Add")
        self._edit_btn = QPushButton("Edit")
        self._remove_btn = QPushButton("Remove")
        self._start_all_btn = QPushButton("Start all")
        self._stop_all_btn = QPushButton("Stop all")
        for button in (self._add_btn, self._edit_btn, self._remove_btn):
            bar.addWidget(button)
        bar.addStretch(1)
        bar.addWidget(self._start_all_btn)
        bar.addWidget(self._stop_all_btn)
        root.addLayout(bar)

        self._empty = QLabel("No accounts yet. Add one to launch a client.")
        self._empty.setObjectName("muted")
        self._empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._empty)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["", "Account", "Status", ""])
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(0, 36)
        self.table.setColumnWidth(2, 150)
        self.table.setColumnWidth(3, 168)
        self.table.cellDoubleClicked.connect(self._on_double_click)
        self.table.itemSelectionChanged.connect(self._update_actions)
        root.addWidget(self.table, 1)

        status = QStatusBar()
        self.setStatusBar(status)

        self._add_btn.clicked.connect(self._add)
        self._edit_btn.clicked.connect(self._edit_selected)
        self._remove_btn.clicked.connect(self._remove_selected)
        self._start_all_btn.clicked.connect(self._start_all)
        self._stop_all_btn.clicked.connect(self._stop_all)

        self._build_menu()
        self._rebuild()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_tick)
        self._poll_timer.start(self.settings.poll_interval_ms)
        self._soon_timer = QTimer(self)
        self._soon_timer.setSingleShot(True)
        self._soon_timer.timeout.connect(self._on_tick)
        self._on_tick()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 Qt override
        self._poll_timer.stop()
        self._soon_timer.stop()
        super().closeEvent(event)

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("File")
        change = QAction("Change master password", self)
        change.triggered.connect(self._change_master_password)
        settings = QAction("Settings", self)
        settings.triggered.connect(self._edit_settings)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        menu.addAction(change)
        menu.addAction(settings)
        menu.addSeparator()
        menu.addAction(quit_action)

        help_menu = self.menuBar().addMenu("Help")
        about = QAction("About", self)
        about.triggered.connect(self._about)
        help_menu.addAction(about)

    def _about(self) -> None:
        QMessageBox.about(
            self,
            "About GWMultiLaunch",
            (
                f"GWMultiLaunch {__version__}\n\n"
                "Linux launcher for Guild Wars clients under Wine. "
                "It does not inject DLLs, load Toolbox, or patch game memory.\n\n"
                "The game's own -password argument is visible in the process list. "
                "This app does not print it."
            ),
        )

    def _add(self) -> None:
        dialog = AccountDialog(parent=self)
        if dialog.exec() != AccountDialog.DialogCode.Accepted:
            return
        account = dialog.result_account()
        if not self._path_available(account):
            return
        self._commit(self.accounts + [account])

    def _edit_selected(self) -> None:
        account = self._selected_account()
        if account is None:
            return
        dialog = AccountDialog(account, parent=self)
        if dialog.exec() != AccountDialog.DialogCode.Accepted:
            return
        updated = dialog.result_account()
        if not self._path_available(updated):
            return
        self._commit([updated if item.id == account.id else item for item in self.accounts])

    def _remove_selected(self) -> None:
        account = self._selected_account()
        if account is None:
            return
        answer = QMessageBox.question(
            self,
            "Remove account",
            f"Remove {account.display_name()}? This does not delete the game folder.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.supervisor.stop(account)
        self.supervisor.forget(account.id)
        self._commit([item for item in self.accounts if item.id != account.id])

    def _start_all(self) -> None:
        self.supervisor.default_wine = self.settings.wine_bin
        for account in self.accounts:
            self.supervisor.launch(account)
        self._on_tick()

    def _stop_all(self) -> None:
        for account in self.accounts:
            self.supervisor.stop(account)
        self._on_tick()

    def _launch(self, account: Account) -> None:
        self.supervisor.default_wine = self.settings.wine_bin
        self.supervisor.launch(account)
        self._on_tick()

    def _stop(self, account: Account) -> None:
        self.supervisor.stop(account)
        self._on_tick()

    def _on_double_click(self, row: int, column: int) -> None:
        del column
        if 0 <= row < len(self.accounts):
            self._launch(self.accounts[row])

    def _edit_settings(self) -> None:
        dialog = SettingsDialog(self.settings, parent=self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        self.settings = dialog.result_settings()
        self._persist_settings(self.settings)
        self.supervisor.default_wine = self.settings.wine_bin
        self._poll_timer.setInterval(self.settings.poll_interval_ms)

    def _change_master_password(self) -> None:
        dialog = ChangePasswordDialog(self)
        if dialog.exec() != ChangePasswordDialog.DialogCode.Accepted:
            return
        try:
            self._persist_accounts(self.accounts, dialog.password())
        except CryptoError:
            QMessageBox.critical(
                self,
                "Could not change password",
                "The vault could not be re-encrypted.",
            )
            return
        self._notice = "master password updated"
        self._notice_until = time.monotonic() + 4
        self._refresh_rows()

    def _commit(self, accounts: list[Account]) -> None:
        try:
            self._persist_accounts(accounts, None)
        except CryptoError:
            QMessageBox.critical(self, "Save failed", "The account vault could not be saved.")
            return
        self.accounts = accounts
        self._rebuild()

    def _path_available(self, account: Account) -> bool:
        target = os.path.abspath(account.gwpath) if account.gwpath else ""
        for other in self.accounts:
            if other.id == account.id or not other.gwpath:
                continue
            if os.path.abspath(other.gwpath) == target:
                QMessageBox.warning(
                    self,
                    "Duplicate client",
                    "Another account already uses this client path. "
                    "Copy the Guild Wars folder so each account has its own Gw.exe.",
                )
                return False
        return True

    def _selected_account(self) -> Account | None:
        selected = self.table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self.accounts):
            return self.accounts[row]
        return None

    def _update_actions(self) -> None:
        has_selection = self._selected_account() is not None
        self._edit_btn.setEnabled(has_selection)
        self._remove_btn.setEnabled(has_selection)
        has_accounts = bool(self.accounts)
        self._start_all_btn.setEnabled(has_accounts)
        self._stop_all_btn.setEnabled(has_accounts)

    def _rebuild(self) -> None:
        self._dots.clear()
        self.table.setRowCount(len(self.accounts))
        self._empty.setVisible(not self.accounts)
        for row, account in enumerate(self.accounts):
            self.table.setRowHeight(row, 40)
            dot = StatusDot()
            self._dots[account.id] = dot
            self.table.setCellWidget(row, 0, _centered(dot))

            name = QTableWidgetItem(account.display_name())
            name.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            name.setToolTip(_tooltip(account))
            self.table.setItem(row, 1, name)

            status = QTableWidgetItem("Offline")
            status.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, 2, status)

            launch = QPushButton("Launch")
            stop = QPushButton("Stop")
            launch.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            stop.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            account_id = account.id
            launch.clicked.connect(lambda _checked=False, ident=account_id: self._launch_id(ident))
            stop.clicked.connect(lambda _checked=False, ident=account_id: self._stop_id(ident))
            wrap = QWidget()
            wrap.setStyleSheet("background: transparent;")
            row_layout = QHBoxLayout(wrap)
            row_layout.setContentsMargins(4, 4, 4, 4)
            row_layout.setSpacing(6)
            row_layout.addWidget(launch)
            row_layout.addWidget(stop)
            self.table.setCellWidget(row, 3, wrap)
        self._update_actions()
        self._refresh_rows()

    def _launch_id(self, account_id: str) -> None:
        account = self._account_by_id(account_id)
        if account is not None:
            self._launch(account)

    def _stop_id(self, account_id: str) -> None:
        account = self._account_by_id(account_id)
        if account is not None:
            self._stop(account)

    def _account_by_id(self, account_id: str) -> Account | None:
        for account in self.accounts:
            if account.id == account_id:
                return account
        return None

    def _on_tick(self) -> None:
        if self._in_tick:
            return
        self._in_tick = True
        try:
            self.supervisor.default_wine = self.settings.wine_bin
            self.supervisor.tick(self.accounts, window_pids=query_window_pids())
            self._refresh_rows()
            delay = self.supervisor.next_relaunch_delay(self.accounts, now=self.supervisor.clock())
            if delay is not None:
                self._soon_timer.start(max(50, int(delay * 1000)))
        finally:
            self._in_tick = False

    def _refresh_rows(self) -> None:
        paused = 0
        for row, account in enumerate(self.accounts):
            online = self.supervisor.tracker.is_online(account)
            text = self.supervisor.row_status(account, online=online)
            if text == PAUSED_MESSAGE:
                paused += 1
            dot = self._dots.get(account.id)
            if dot is not None:
                dot.set_online(online)
            status_item = self.table.item(row, 2)
            if status_item is not None:
                status_item.setText(text)
                if text == PAUSED_MESSAGE:
                    color = "#f0b45a"
                elif online:
                    color = "#8ee0b2"
                else:
                    color = "#f0a0a6"
                status_item.setForeground(QBrush(QColor(color)))
        count = len(self.accounts)
        noun = "account" if count == 1 else "accounts"
        paused_text = f" · {paused} relaunch paused" if paused else ""
        notice = f" · {self._notice}" if self._notice and time.monotonic() < self._notice_until else ""
        self.statusBar().showMessage(f"{count} {noun} · watching{paused_text}{notice}")


def run_app(args: object) -> int:
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GWMultiLaunch")
    app.setWindowIcon(app_icon())
    apply_theme(app)

    config_arg = getattr(args, "config_dir", None)
    directory = Path(config_arg) if config_arg else default_config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass
    vault = Vault(directory)
    settings = vault.load_settings()

    unlocked = _unlock(vault)
    if unlocked is None:
        return 0
    accounts: list[Account] = unlocked["accounts"]
    holder: dict[str, str] = {"password": unlocked["password"]}

    if getattr(args, "demo", False) and not accounts:
        accounts = [_demo_account()]
        vault.save_accounts(accounts, holder["password"])

    def persist_accounts(next_accounts: list[Account], new_password: str | None) -> None:
        password = holder["password"] if new_password is None else new_password
        vault.save_accounts(next_accounts, password)
        holder["password"] = password

    def persist_settings(next_settings: Settings) -> None:
        vault.save_settings(next_settings)

    window = MainWindow(
        accounts=accounts,
        settings=settings,
        persist_accounts=persist_accounts,
        persist_settings=persist_settings,
    )
    window.show()
    return int(app.exec())


def _unlock(vault: Vault) -> dict[str, object] | None:
    creating = not vault.exists()
    while True:
        dialog = MasterPasswordDialog(creating=creating)
        if dialog.exec() != MasterPasswordDialog.DialogCode.Accepted:
            return None
        password = dialog.password()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if creating:
                vault.save_accounts([], password)
                accounts: list[Account] = []
            else:
                accounts = vault.load_accounts(password)
        except VaultCorruptError:
            QMessageBox.critical(
                None,
                "Vault unreadable",
                "The vault file is unreadable or was tampered with.",
            )
            continue
        except CryptoError:
            QMessageBox.warning(
                None,
                "Unlock failed",
                "That master password didn't unlock the vault.",
            )
            continue
        finally:
            QApplication.restoreOverrideCursor()
        return {"accounts": accounts, "password": password}


def _demo_account() -> Account:
    return Account(
        id=new_account_id(),
        title="Stand-in",
        email="demo@example.com",
        password="REPLACE_ME",
        character="Demo Character",
        gwpath=str(standin_script_path()),
        extraargs="",
        auto_relaunch=True,
    )


def _centered(widget: QWidget) -> QWidget:
    wrap = QWidget()
    wrap.setStyleSheet("background: transparent;")
    layout = QHBoxLayout(wrap)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addStretch(1)
    layout.addWidget(widget)
    layout.addStretch(1)
    return wrap


def _tooltip(account: Account) -> str:
    lines = [account.display_name()]
    if account.email.strip():
        lines.append(account.email.strip())
    if account.character.strip():
        lines.append(account.character.strip())
    if account.gwpath.strip():
        lines.append(account.gwpath.strip())
    return "\n".join(lines)
