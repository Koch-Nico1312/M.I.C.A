"""
Screen Overlay HUD System
Transparent overlay with glowing highlights for autonomous actions
"""

import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

try:
    from PyQt6.QtCore import QPoint, QRectF, Qt, QTimer
    from PyQt6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QRadialGradient
    from PyQt6.QtWidgets import QApplication, QWidget

    PYQT_AVAILABLE = True
except ImportError:
    PYQT_AVAILABLE = False

from config.config_loader import get_config


@dataclass
class Highlight:
    """Represents a screen highlight"""

    x: int
    y: int
    width: int
    height: int
    color: str = "#00ff00"
    duration: float = 2.0
    timestamp: float = 0.0


if PYQT_AVAILABLE:

    class HUDOverlay(QWidget):
        """Transparent overlay window for HUD elements"""

        def __init__(self):
            super().__init__()
            self.config = get_config()
            self.enabled = self.config.get("hud.enabled", False)
            self.transparency = self.config.get("hud.transparency", 0.7)
            self.highlight_color = self.config.get("hud.highlight_color", "#00ff00")
            self.show_click_targets = self.config.get("hud.show_click_targets", True)

            # Window setup
            transparent_flag = getattr(
                Qt.WindowType,
                "WindowTransparentForInput",
                None,
            )
            window_flags = (
                Qt.WindowType.FramelessWindowHint
                | Qt.WindowType.WindowStaysOnTopHint
                | Qt.WindowType.Tool
            )
            if transparent_flag is not None:
                window_flags |= transparent_flag
            self.setWindowFlags(window_flags)
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

            # State
            self.highlights: Dict[str, Highlight] = {}
            self.mouse_trail: list = []
            self.current_action: Optional[str] = None
            self.status_text: str = ""

            # Timer for animation
            self.timer = QTimer()
            self.timer.timeout.connect(self.update_animation)
            self.timer.start(30)  # 30ms = ~33 FPS

            if self.enabled:
                self.show_fullscreen()
                print(f"[HUD] ✅ Overlay initialized (transparency: {self.transparency})")

        def show_fullscreen(self):
            """Show overlay covering entire screen"""
            if not self.enabled:
                return

            screen = QApplication.primaryScreen()
            if screen:
                geometry = screen.geometry()
                self.setGeometry(geometry)
                self.show()

        def add_highlight(
            self,
            x: int,
            y: int,
            width: int = 50,
            height: int = 50,
            color: str = None,
            duration: float = 2.0,
        ) -> str:
            """Add a highlight to the screen"""
            if not self.enabled:
                return ""

            highlight_id = f"hl_{time.time()}_{len(self.highlights)}"
            self.highlights[highlight_id] = Highlight(
                x=x,
                y=y,
                width=width,
                height=height,
                color=color or self.highlight_color,
                duration=duration,
                timestamp=time.time(),
            )

            print(f"[HUD] 🎯 Highlight at ({x}, {y})")
            return highlight_id

        def add_click_target(self, x: int, y: int):
            """Add a glowing target for a click action"""
            if not self.enabled or not self.show_click_targets:
                return

            self.add_highlight(x, y, width=60, height=60, color="#ff0000", duration=1.5)

        def update_mouse_position(self, x: int, y: int):
            """Update mouse position for trail effect"""
            if not self.enabled:
                return

            self.mouse_trail.append((x, y, time.time()))
            # Keep only last 20 points
            if len(self.mouse_trail) > 20:
                self.mouse_trail.pop(0)

        def set_status(self, text: str):
            """Set status text to display"""
            self.status_text = text

        def set_current_action(self, action: str):
            """Set the current action being performed"""
            self.current_action = action

        def update_animation(self):
            """Update animation state"""
            current_time = time.time()

            # Remove expired highlights
            expired = [
                hid
                for hid, hl in self.highlights.items()
                if current_time - hl.timestamp > hl.duration
            ]
            for hid in expired:
                del self.highlights[hid]

            # Remove old mouse trail points
            self.mouse_trail = [(x, y, t) for x, y, t in self.mouse_trail if current_time - t < 1.0]

            self.update()

        def paintEvent(self, event):
            """Paint the HUD overlay"""
            if not self.enabled:
                return

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            current_time = time.time()

            # Draw highlights
            for highlight in self.highlights.values():
                age = current_time - highlight.timestamp
                if age > highlight.duration:
                    continue

                # Fade out based on age
                alpha = int(255 * (1 - age / highlight.duration))

                # Parse color
                color = QColor(highlight.color)
                color.setAlpha(alpha)

                # Create radial gradient for glow effect
                center_x = highlight.x + highlight.width / 2
                center_y = highlight.y + highlight.height / 2
                radius = max(highlight.width, highlight.height) / 2

                gradient = QRadialGradient(center_x, center_y, radius)
                gradient.setColorAt(0, color)
                gradient.setColorAt(1, QColor(0, 0, 0, 0))

                painter.setBrush(QBrush(gradient))
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawEllipse(
                    int(center_x - radius), int(center_y - radius), int(radius * 2), int(radius * 2)
                )

                # Draw border
                pen = QPen(color)
                pen.setWidth(2)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRect(highlight.x, highlight.y, highlight.width, highlight.height)

            # Draw mouse trail
            if self.mouse_trail:
                for i, (x, y, t) in enumerate(self.mouse_trail):
                    age = current_time - t
                    alpha = int(255 * (1 - age))
                    size = int(10 * (1 - age))

                    color = QColor(0, 255, 255, alpha)
                    painter.setBrush(QBrush(color))
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawEllipse(x - size // 2, y - size // 2, size, size)

            # Draw status text
            if self.status_text:
                painter.setPen(QColor(255, 255, 255, 200))
                painter.setFont(QFont("Arial", 14, QFont.Weight.Bold))
                painter.drawText(20, 40, self.status_text)

            # Draw current action
            if self.current_action:
                painter.setPen(QColor(0, 255, 0, 200))
                painter.setFont(QFont("Arial", 12))
                painter.drawText(20, 70, f"Action: {self.current_action}")

        def clear_highlights(self):
            """Clear all highlights"""
            self.highlights.clear()

        def close_overlay(self):
            """Close the overlay"""
            self.close()

else:

    class HUDOverlay:
        """No-op HUD used in headless environments."""

        def add_highlight(
            self,
            x: int,
            y: int,
            width: int = 50,
            height: int = 50,
            color: str = None,
            duration: float = 2.0,
        ) -> str:
            return ""

        def add_click_target(self, x: int, y: int):
            return None

        def update_mouse_position(self, x: int, y: int):
            return None

        def set_status(self, text: str):
            return None

        def set_current_action(self, action: str):
            return None

        def clear_highlights(self):
            return None

        def close_overlay(self):
            return None


class HUDManager:
    """Manages the HUD overlay"""

    def __init__(self):
        self.overlay: Optional[HUDOverlay] = None
        self.app: Optional[QApplication] = None

    def initialize(self):
        """Initialize the HUD overlay"""
        if not PYQT_AVAILABLE:
            print("[HUDManager] ⚠️ PyQt6 not available")
            return False

        if self.overlay is not None:
            return True

        try:
            self.app = QApplication.instance()
            if self.app is None:
                self.app = QApplication([])

            self.overlay = HUDOverlay()
            return True
        except Exception as e:
            print(f"[HUDManager] ❌ Initialization error: {e}")
            return False

    def highlight_click(self, x: int, y: int):
        """Highlight a click position"""
        if self.overlay:
            self.overlay.add_click_target(x, y)

    def highlight_region(self, x: int, y: int, width: int, height: int, color: str = None):
        """Highlight a region"""
        if self.overlay:
            self.overlay.add_highlight(x, y, width, height, color)

    def update_mouse(self, x: int, y: int):
        """Update mouse position"""
        if self.overlay:
            self.overlay.update_mouse_position(x, y)

    def set_status(self, text: str):
        """Set status text"""
        if self.overlay:
            self.overlay.set_status(text)

    def set_action(self, action: str):
        """Set current action"""
        if self.overlay:
            self.overlay.set_current_action(action)

    def close(self):
        """Close the HUD"""
        if self.overlay:
            self.overlay.close_overlay()
            self.overlay = None


# Global instance
_hud_manager: Optional[HUDManager] = None


def get_hud_manager() -> HUDManager:
    """Get the global HUD manager instance"""
    global _hud_manager
    if _hud_manager is None:
        _hud_manager = HUDManager()
    return _hud_manager
