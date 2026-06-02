"""
Health Dashboard UI Component for Mark-XXXIX
============================================
Provides a widget to display system health status in the UI.
"""

from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget


class HealthStatusWidget(QWidget):
    """Widget to display system health status."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(120)

        # Import shared colors from the central theme module
        try:
            from core.ui_theme import C

            self.C = C
        except ImportError:
            # Fallback colors if the shared theme module is unavailable
            class C:
                PANEL = "#010d14"
                BORDER = "#0d3347"
                TEXT_DIM = "#3a8a9a"
                TEXT = "#8ffcff"
                GREEN = "#00ff88"
                RED = "#ff3355"

            self.C = C

        self.setStyleSheet(
            f"background: {self.C.PANEL}; border: 1px solid {self.C.BORDER}; border-radius: 4px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)

        # Status labels
        self._status_labels = {}

        def _status_row(key, label):
            row = QHBoxLayout()
            row.setSpacing(6)
            lbl = QLabel(label)
            lbl.setFont(QFont("Courier New", 7))
            lbl.setStyleSheet(f"color: {self.C.TEXT_DIM}; background: transparent;")
            val = QLabel("--")
            val.setFont(QFont("Courier New", 7, QFont.Weight.Bold))
            val.setStyleSheet(f"color: {self.C.TEXT}; background: transparent;")
            row.addWidget(lbl)
            row.addWidget(val, stretch=1)
            row.addStretch()
            self._status_labels[key] = val
            return row

        layout.addLayout(_status_row("api", "API"))
        layout.addLayout(_status_row("audio", "AUDIO"))
        layout.addLayout(_status_row("memory", "MEMORY"))
        layout.addLayout(_status_row("rag", "RAG"))

        # Timer to update status
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_status)
        self._timer.start(5000)
        self._update_status()

    def _update_status(self):
        """Update health status indicators."""
        try:
            from config.config_loader import get_config
            from core.healthcheck import build_runtime_report

            config = get_config()
            base_dir = Path(__file__).resolve().parent.parent
            report = build_runtime_report(base_dir, config=config)

            # API status
            if report.get("api_key_present"):
                self._status_labels["api"].setText("✓ OK")
                self._status_labels["api"].setStyleSheet(
                    f"color: {self.C.GREEN}; background: transparent;"
                )
            else:
                self._status_labels["api"].setText("✗ MISSING")
                self._status_labels["api"].setStyleSheet(
                    f"color: {self.C.RED}; background: transparent;"
                )

            # Audio status
            audio = report.get("audio", {})
            if audio.get("sounddevice_available"):
                self._status_labels["audio"].setText("✓ OK")
                self._status_labels["audio"].setStyleSheet(
                    f"color: {self.C.GREEN}; background: transparent;"
                )
            else:
                self._status_labels["audio"].setText("✗ N/A")
                self._status_labels["audio"].setStyleSheet(
                    f"color: {self.C.TEXT_DIM}; background: transparent;"
                )

            # Memory status
            memory = report.get("memory", {})
            if memory.get("memory_file_exists"):
                size_kb = memory.get("memory_file_size_kb", 0)
                self._status_labels["memory"].setText(f"✓ {size_kb:.1f}KB")
                self._status_labels["memory"].setStyleSheet(
                    f"color: {self.C.GREEN}; background: transparent;"
                )
            else:
                self._status_labels["memory"].setText("✗ EMPTY")
                self._status_labels["memory"].setStyleSheet(
                    f"color: {self.C.RED}; background: transparent;"
                )

            # RAG status
            features = report.get("features", {})
            if features.get("rag"):
                self._status_labels["rag"].setText("✓ ON")
                self._status_labels["rag"].setStyleSheet(
                    f"color: {self.C.GREEN}; background: transparent;"
                )
            else:
                self._status_labels["rag"].setText("○ OFF")
                self._status_labels["rag"].setStyleSheet(
                    f"color: {self.C.TEXT_DIM}; background: transparent;"
                )

        except Exception as e:
            # On error, show status as unknown
            for key in self._status_labels:
                self._status_labels[key].setText("?")
                self._status_labels[key].setStyleSheet(
                    f"color: {self.C.TEXT_DIM}; background: transparent;"
                )
