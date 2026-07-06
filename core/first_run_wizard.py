from __future__ import annotations

import getpass
import os
import sys
from typing import Optional

from config.config_loader import get_config
from core.logger import get_logger
from memory.config_manager import is_valid_gemini_key, save_api_keys

logger = get_logger(__name__)


def has_valid_gemini_key() -> bool:
    """Check the merged runtime config for a Gemini key."""
    return is_valid_gemini_key(get_config().get_api_key("gemini"))


def ensure_gemini_api_key(use_gui: bool = True) -> bool:
    """
    Ensure a Gemini API key exists before the assistant starts.

    In GUI mode this opens a small first-run dialog. In CLI mode it falls back
    to a hidden terminal prompt.
    """
    if has_valid_gemini_key():
        return True

    if use_gui and not (os.environ.get("MICA_NO_QT") or os.environ.get("MICA_NO_QT")):
        key = _prompt_with_qt()
    else:
        key = _prompt_in_terminal()

    if not key:
        logger.error("Gemini API key setup was cancelled.")
        return False

    save_api_keys(gemini_api_key=key)
    get_config().reload()
    return has_valid_gemini_key()


def _prompt_with_qt() -> Optional[str]:
    try:
        from PyQt6.QtCore import Qt
        from PyQt6.QtWidgets import (
            QApplication,
            QDialog,
            QDialogButtonBox,
            QLabel,
            QLineEdit,
            QMessageBox,
            QVBoxLayout,
        )
    except Exception as exc:
        logger.warning("Qt first-run wizard unavailable, falling back to CLI: %s", exc)
        return _prompt_in_terminal()

    app = QApplication.instance()
    owns_app = False
    if app is None:
        app = QApplication(sys.argv)
        app.setApplicationName("M.I.C.A")
        owns_app = True

    dialog = QDialog()
    dialog.setWindowTitle("M.I.C.A Erststart")
    dialog.setMinimumWidth(460)
    dialog.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)

    layout = QVBoxLayout(dialog)
    title = QLabel("Gemini API-Key erforderlich")
    title.setStyleSheet("font-size: 18px; font-weight: 600;")
    body = QLabel(
        "Beim ersten Start braucht M.I.C.A einen Gemini API-Key. "
        "Der Key wird lokal in config/api_keys.json gespeichert."
    )
    body.setWordWrap(True)
    hint = QLabel("Der Key muss mit 'AIza' beginnen.")
    hint.setStyleSheet("color: #64748b;")

    key_input = QLineEdit()
    key_input.setPlaceholderText("AIza...")
    key_input.setEchoMode(QLineEdit.EchoMode.Password)
    key_input.setMinimumHeight(34)

    buttons = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
    )
    save_button = buttons.button(QDialogButtonBox.StandardButton.Save)
    save_button.setText("Speichern")
    buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Abbrechen")

    layout.addWidget(title)
    layout.addWidget(body)
    layout.addWidget(hint)
    layout.addWidget(key_input)
    layout.addWidget(buttons)

    captured_key: dict[str, str] = {}

    def accept_if_valid() -> None:
        value = key_input.text().strip()
        if not is_valid_gemini_key(value):
            QMessageBox.warning(
                dialog,
                "Ungueltiger Key",
                "Bitte gib einen Gemini API-Key ein. Gemini Keys beginnen normalerweise mit 'AIza'.",
            )
            return
        captured_key["value"] = value
        dialog.accept()

    buttons.accepted.connect(accept_if_valid)
    buttons.rejected.connect(dialog.reject)

    accepted = dialog.exec() == QDialog.DialogCode.Accepted
    if owns_app:
        app.processEvents()
    return captured_key.get("value") if accepted else None


def _prompt_in_terminal() -> Optional[str]:
    print("M.I.C.A Erststart: Gemini API-Key erforderlich.")
    try:
        key = getpass.getpass("Gemini API-Key: ").strip()
    except (EOFError, KeyboardInterrupt):
        return None
    if not is_valid_gemini_key(key):
        print("Ungueltiger Gemini API-Key. Gemini Keys beginnen normalerweise mit 'AIza'.")
        return None
    return key
