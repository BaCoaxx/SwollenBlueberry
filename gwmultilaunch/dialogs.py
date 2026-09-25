"""Modal dialogs for the vault and account list."""

from __future__ import annotations

import os

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gwmultilaunch.models import Account, new_account_id
from gwmultilaunch.settings import Settings

MIN_MASTER_PASSWORD = 8


class MasterPasswordDialog(QDialog):
    def __init__(self, *, creating: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._creating = creating
        self._password = ""
        self.setWindowTitle("Create master password" if creating else "Unlock GWMultiLaunch")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        if creating:
            intro = (
                "Choose a master password. It encrypts the account vault on this "
                "machine and is not sent anywhere.\n\n"
                "Guild Wars still receives each account password on the game "
                "command line when a client starts. GWMultiLaunch never prints those passwords."
            )
        else:
            intro = "Enter the master password for the account vault on this machine."
        label = QLabel(intro)
        label.setWordWrap(True)
        label.setObjectName("muted")
        layout.addWidget(label)

        form = QFormLayout()
        self._entry = QLineEdit()
        self._entry.setEchoMode(QLineEdit.EchoMode.Password)
        self._entry.setPlaceholderText(f"At least {MIN_MASTER_PASSWORD} characters")
        form.addRow("Master password", self._entry)
        self._confirm = QLineEdit()
        self._confirm.setEchoMode(QLineEdit.EchoMode.Password)
        if creating:
            form.addRow("Confirm", self._confirm)
        else:
            self._confirm.hide()
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._entry.setFocus()

    def password(self) -> str:
        return self._password

    def accept(self) -> None:
        chosen = self._entry.text()
        if len(chosen) < MIN_MASTER_PASSWORD:
            QMessageBox.warning(
                self,
                "Master password",
                f"Use at least {MIN_MASTER_PASSWORD} characters.",
            )
            return
        if self._creating and chosen != self._confirm.text():
            QMessageBox.warning(self, "Master password", "Those passwords don't match.")
            return
        self._password = chosen
        super().accept()


class ChangePasswordDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._password = ""
        self.setWindowTitle("Change master password")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        note = QLabel("The vault is re-encrypted with the new password. Account passwords are unchanged.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        form = QFormLayout()
        self._entry = QLineEdit()
        self._confirm = QLineEdit()
        for field in (self._entry, self._confirm):
            field.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("New password", self._entry)
        form.addRow("Confirm", self._confirm)
        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def password(self) -> str:
        return self._password

    def accept(self) -> None:
        chosen = self._entry.text()
        if len(chosen) < MIN_MASTER_PASSWORD:
            QMessageBox.warning(
                self,
                "Master password",
                f"Use at least {MIN_MASTER_PASSWORD} characters.",
            )
            return
        if chosen != self._confirm.text():
            QMessageBox.warning(self, "Master password", "Those passwords don't match.")
            return
        self._password = chosen
        super().accept()


class AccountDialog(QDialog):
    def __init__(self, account: Account | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._account = account
        self.setWindowTitle("Edit account" if account else "Add account")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._title = QLineEdit(account.title if account else "")
        self._title.setPlaceholderText("Optional display name")
        self._email = QLineEdit(account.email if account else "")
        self._password = QLineEdit(account.password if account else "")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Not shown in the list or logs")
        self._character = QLineEdit(account.character if account else "")
        self._character.setPlaceholderText("Omit to skip -character")
        self._gwpath = QLineEdit(account.gwpath if account else "")
        self._extra = QLineEdit(account.extraargs if account else "")
        self._extra.setPlaceholderText("Example: -windowed")
        self._prefix = QLineEdit(account.wine_prefix if account else "")
        self._prefix.setPlaceholderText("Empty uses the default Wine prefix")
        self._wine = QLineEdit(account.wine_bin if account else "")
        self._wine.setPlaceholderText("Empty uses the wine setting")
        self._auto = QCheckBox("Relaunch if the client closes")
        self._auto.setChecked(True if account is None else account.auto_relaunch)

        form.addRow("Title", self._title)
        form.addRow("Email", self._email)
        form.addRow("Password", self._password)
        form.addRow("Character", self._character)
        form.addRow("Gw.exe", _path_row(self._gwpath, self._browse_exe))
        form.addRow("Extra args", self._extra)
        form.addRow("Wine prefix", _path_row(self._prefix, self._browse_prefix))
        form.addRow("Wine binary", _path_row(self._wine, self._browse_wine))
        form.addRow("", self._auto)
        layout.addLayout(form)

        hint = QLabel(
            "Multi-box needs a separate install folder per account, each with its own Gw.exe and Gw.dat."
        )
        hint.setWordWrap(True)
        hint.setObjectName("muted")
        layout.addWidget(hint)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_account(self) -> Account:
        current = self._account
        return Account(
            id=current.id if current else new_account_id(),
            title=self._title.text().strip(),
            email=self._email.text().strip(),
            password=self._password.text(),
            character=self._character.text().strip(),
            gwpath=self._gwpath.text().strip(),
            extraargs=self._extra.text().strip(),
            wine_prefix=self._prefix.text().strip(),
            wine_bin=self._wine.text().strip(),
            auto_relaunch=self._auto.isChecked(),
        )

    def accept(self) -> None:
        if not self._email.text().strip():
            QMessageBox.warning(self, "Missing email", "Email is required.")
            return
        path = self._gwpath.text().strip()
        if not path:
            QMessageBox.warning(
                self,
                "Missing client",
                "Choose the Gw.exe, or a native stand-in, for this account.",
            )
            return
        if not os.path.exists(path):
            answer = QMessageBox.question(
                self,
                "Path not found",
                "That path does not exist yet. Save the account anyway?",
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().accept()

    def _browse_exe(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Guild Wars client",
            self._gwpath.text() or os.path.expanduser("~"),
            "Clients (Gw.exe gw-standin *);;All files (*)",
        )
        if filename:
            self._gwpath.setText(filename)

    def _browse_prefix(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self,
            "Wine prefix",
            self._prefix.text() or os.path.expanduser("~"),
        )
        if directory:
            self._prefix.setText(directory)

    def _browse_wine(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Wine binary",
            self._wine.text() or "/usr/bin",
        )
        if filename:
            self._wine.setText(filename)


class SettingsDialog(QDialog):
    def __init__(self, settings: Settings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumWidth(420)
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._wine = QLineEdit(settings.wine_bin)
        self._wine.setPlaceholderText("wine")
        self._poll = QSpinBox()
        self._poll.setRange(250, 10_000)
        self._poll.setSingleStep(50)
        self._poll.setSuffix(" ms")
        self._poll.setValue(settings.normalized().poll_interval_ms)
        form.addRow("Default wine binary", self._wine)
        form.addRow("Status poll", self._poll)
        layout.addLayout(form)
        note = QLabel("Per-account wine binary and prefix override these defaults. Nothing here is secret.")
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_settings(self) -> Settings:
        return Settings(wine_bin=self._wine.text(), poll_interval_ms=self._poll.value()).normalized()


def _path_row(edit: QLineEdit, browse) -> QWidget:
    row = QWidget()
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.addWidget(edit, 1)
    button = QPushButton("Browse")
    button.clicked.connect(browse)
    layout.addWidget(button)
    return row
