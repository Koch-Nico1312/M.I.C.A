"""
Settings Overview UI Component for Mark-XXXIX
==============================================
Provides a widget to view and edit key settings without manual .env/config.yaml editing.
"""

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)


class SettingsOverviewWidget(QWidget):
    """Widget to display and edit key settings."""

    settings_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Import shared colors from the central theme module
        try:
            from core.ui_theme import C

            self.C = C
        except ImportError:
            # Fallback colors
            class C:
                PANEL = "#010d14"
                BORDER = "#0d3347"
                BORDER_B = "#1a5c7a"
                TEXT_DIM = "#3a8a9a"
                TEXT = "#8ffcff"
                PRI = "#00d4ff"
                GREEN = "#00ff88"

            self.C = C

        self.setStyleSheet(
            f"background: {self.C.PANEL}; border: 1px solid {self.C.BORDER}; border-radius: 4px;"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # Title
        title = QLabel("⚙ SETTINGS")
        title.setFont(QFont("Courier New", 9, QFont.Weight.Bold))
        title.setStyleSheet(f"color: {self.C.PRI}; background: transparent;")
        layout.addWidget(title)

        # Scroll area for settings
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"background: transparent; border: none;")

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setSpacing(6)

        # Permission level setting
        content_layout.addWidget(self._create_permission_setting())

        # Feature toggles
        content_layout.addWidget(self._create_feature_toggles())

        # Model settings
        content_layout.addWidget(self._create_model_settings())

        content_layout.addStretch()
        scroll.setWidget(content)
        layout.addWidget(scroll, stretch=1)

        # Reload button
        reload_btn = QPushButton("↻ RELOAD CONFIG")
        reload_btn.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        reload_btn.setFixedHeight(28)
        reload_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent; color: {self.C.PRI};
                border: 1px solid {self.C.BORDER_B}; border-radius: 3px;
            }}
            QPushButton:hover {{
                background: {self.C.PRI_GHO if hasattr(self.C, 'PRI_GHO') else '#001f2e'}; border: 1px solid {self.C.PRI};
            }}
        """)
        reload_btn.clicked.connect(self._reload_config)
        layout.addWidget(reload_btn)

        # Load current settings
        self._load_settings()

    def _create_permission_setting(self):
        """Create permission level setting row."""
        frame = QFrame()
        frame.setStyleSheet(
            f"background: {self.C.PANEL}; border: 1px solid {self.C.BORDER}; border-radius: 3px;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)

        label = QLabel("Permission Level")
        label.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {self.C.TEXT}; background: transparent;")
        layout.addWidget(label)

        row = QHBoxLayout()
        self._perm_combo = QComboBox()
        self._perm_combo.addItems(["safe", "normal", "admin"])
        self._perm_combo.setFont(QFont("Courier New", 8))
        self._perm_combo.setStyleSheet(f"""
            QComboBox {{
                background: #000d14; color: {self.C.TEXT};
                border: 1px solid {self.C.BORDER}; border-radius: 3px; padding: 2px;
            }}
        """)
        self._perm_combo.currentTextChanged.connect(self._on_permission_changed)
        row.addWidget(self._perm_combo, stretch=1)
        layout.addLayout(row)

        hint = QLabel("Controls which actions require confirmation")
        hint.setFont(QFont("Courier New", 7))
        hint.setStyleSheet(f"color: {self.C.TEXT_DIM}; background: transparent;")
        layout.addWidget(hint)

        return frame

    def _create_feature_toggles(self):
        """Create feature toggle section."""
        frame = QFrame()
        frame.setStyleSheet(
            f"background: {self.C.PANEL}; border: 1px solid {self.C.BORDER}; border-radius: 3px;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)

        label = QLabel("Features")
        label.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {self.C.TEXT}; background: transparent;")
        layout.addWidget(label)

        self._feature_checks = {}
        features = [
            ("passive_vision", "Passive Vision"),
            ("rag", "Semantic Search (RAG)"),
            ("hud", "HUD Overlay"),
            ("proactive", "Proactive Suggestions"),
            ("emotion", "Voice Emotion Analysis"),
        ]

        for key, name in features:
            check = QCheckBox(name)
            check.setFont(QFont("Courier New", 8))
            check.setStyleSheet(f"""
                QCheckBox {{
                    color: {self.C.TEXT}; background: transparent;
                }}
                QCheckBox::indicator {{
                    width: 14px; height: 14px;
                }}
            """)
            check.stateChanged.connect(lambda _, k=key: self._on_feature_changed(k))
            layout.addWidget(check)
            self._feature_checks[key] = check

        return frame

    def _create_model_settings(self):
        """Create model settings section."""
        frame = QFrame()
        frame.setStyleSheet(
            f"background: {self.C.PANEL}; border: 1px solid {self.C.BORDER}; border-radius: 3px;"
        )
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(8, 6, 8, 6)

        label = QLabel("Models")
        label.setFont(QFont("Courier New", 8, QFont.Weight.Bold))
        label.setStyleSheet(f"color: {self.C.TEXT}; background: transparent;")
        layout.addWidget(label)

        # Live model
        row = QHBoxLayout()
        lbl = QLabel("Live Model:")
        lbl.setFont(QFont("Courier New", 8))
        lbl.setStyleSheet(f"color: {self.C.TEXT_DIM}; background: transparent;")
        row.addWidget(lbl)

        self._live_model_input = QLineEdit()
        self._live_model_input.setFont(QFont("Courier New", 8))
        self._live_model_input.setStyleSheet(f"""
            QLineEdit {{
                background: #000d14; color: {self.C.TEXT};
                border: 1px solid {self.C.BORDER}; border-radius: 3px; padding: 2px 4px;
            }}
        """)
        self._live_model_input.editingFinished.connect(self._on_model_changed)
        row.addWidget(self._live_model_input, stretch=1)
        layout.addLayout(row)

        return frame

    def _load_settings(self):
        """Load current settings from config."""
        try:
            from config.config_loader import get_config

            config = get_config()

            # Permission level
            perm_level = config.get("security.permission_level", "normal")
            index = self._perm_combo.findText(perm_level)
            if index >= 0:
                self._perm_combo.setCurrentIndex(index)

            # Features
            features = config.get("features", {})
            for key, check in self._feature_checks.items():
                enabled = features.get(f"{key}.enabled", False)
                check.setChecked(bool(enabled))

            # Live model
            live_model = config.get("models.live", "")
            self._live_model_input.setText(live_model)

        except Exception as e:
            print(f"Error loading settings: {e}")

    def _on_permission_changed(self, value):
        """Handle permission level change."""
        try:
            from config.config_loader import get_config

            config = get_config()
            config["security.permission_level"] = value
            self.settings_changed.emit()
        except Exception as e:
            print(f"Error changing permission: {e}")

    def _on_feature_changed(self, key):
        """Handle feature toggle change."""
        try:
            from config.config_loader import get_config

            config = get_config()
            enabled = self._feature_checks[key].isChecked()
            config[f"{key}.enabled"] = enabled
            self.settings_changed.emit()
        except Exception as e:
            print(f"Error changing feature {key}: {e}")

    def _on_model_changed(self):
        """Handle model setting change."""
        try:
            from config.config_loader import get_config

            config = get_config()
            config["models.live"] = self._live_model_input.text()
            self.settings_changed.emit()
        except Exception as e:
            print(f"Error changing model: {e}")

    def _reload_config(self):
        """Reload configuration from files."""
        try:
            from config.config_loader import get_config

            config = get_config()
            config.reload()
            self._load_settings()
            self.settings_changed.emit()
        except Exception as e:
            print(f"Error reloading config: {e}")
