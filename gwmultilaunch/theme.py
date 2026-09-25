"""Dark Fusion theme for the launcher window."""

from __future__ import annotations

from PySide6.QtGui import QColor, QIcon, QPainter, QPalette, QPixmap
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

STYLESHEET = """
QMainWindow, QDialog {
    background: #16181d;
}
QLabel#title {
    font-size: 18px;
    font-weight: 600;
    color: #f2f4f8;
}
QLabel#muted, QStatusBar {
    color: #9aa3b5;
}
QTableWidget {
    background: #12141a;
    alternate-background-color: #181b22;
    border: 1px solid #2a3140;
    border-radius: 6px;
    gridline-color: transparent;
    selection-background-color: #243044;
    selection-color: #f2f4f8;
}
QHeaderView::section {
    background: #1c1f26;
    color: #9aa3b5;
    border: none;
    border-bottom: 1px solid #2a3140;
    padding: 6px 8px;
    font-weight: 600;
}
QPushButton {
    background: #2a3140;
    border: 1px solid #3a4254;
    border-radius: 4px;
    padding: 5px 12px;
    color: #f2f4f8;
}
QPushButton:hover {
    background: #343d51;
}
QPushButton:pressed {
    background: #3d82f0;
    border-color: #3d82f0;
}
QPushButton:disabled {
    color: #6e7687;
    background: #22262e;
    border-color: #2a3140;
}
QLineEdit, QSpinBox {
    background: #0f1115;
    border: 1px solid #343b4a;
    border-radius: 4px;
    padding: 6px 8px;
    color: #f2f4f8;
    selection-background-color: #3d82f0;
}
QCheckBox {
    spacing: 8px;
}
QMenuBar {
    background: #16181d;
    color: #f2f4f8;
}
QMenuBar::item:selected, QMenu::item:selected {
    background: #2a3140;
}
QMenu {
    background: #1c1f26;
    color: #f2f4f8;
    border: 1px solid #2c3240;
}
QStatusBar {
    background: #1c1f26;
}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)
    app.setStyleSheet(STYLESHEET)


def app_icon() -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor("#3d82f0"))
    painter.drawRoundedRect(4, 4, 56, 56, 14, 14)
    painter.setBrush(QColor("#3ddc97"))
    painter.drawEllipse(40, 8, 14, 14)
    painter.end()
    return QIcon(pixmap)


def _dark_palette() -> QPalette:
    palette = QPalette()
    text = QColor("#f2f4f8")
    disabled = QColor("#6e7687")
    palette.setColor(QPalette.ColorRole.Window, QColor("#16181d"))
    palette.setColor(QPalette.ColorRole.WindowText, text)
    palette.setColor(QPalette.ColorRole.Base, QColor("#101218"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c1f26"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1c1f26"))
    palette.setColor(QPalette.ColorRole.ToolTipText, text)
    palette.setColor(QPalette.ColorRole.Text, text)
    palette.setColor(QPalette.ColorRole.Button, QColor("#2a3140"))
    palette.setColor(QPalette.ColorRole.ButtonText, text)
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#3d82f0"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, disabled)
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, disabled)
    return palette
