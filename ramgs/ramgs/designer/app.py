"""
Application entry point for Panel Designer
"""

import sys
from typing import Optional
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def run_designer(file_path: Optional[str] = None):
    """
    Launch the Panel Designer application.

    Args:
        file_path: Optional path to a .panel.json file to open
    """
    # Check if QApplication already exists (e.g., when called from GUI)
    app = QApplication.instance()
    if app is None:
        # Enable high DPI scaling
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
        app = QApplication(sys.argv)
        app.setApplicationName("RAMViewer Panel Designer")
        app.setOrganizationName("RAMViewer")
        created_app = True
    else:
        created_app = False

    # Import here to avoid circular imports
    from .designer_window import DesignerWindow

    window = DesignerWindow()

    if file_path:
        window.open_file(file_path)

    window.show()

    if created_app:
        sys.exit(app.exec())
