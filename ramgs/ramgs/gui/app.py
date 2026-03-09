"""
Application entry point for GUI mode
"""

import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt


def run_gui():
    """Launch the GUI application"""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("RAMViewer GUI")
    app.setOrganizationName("RAMViewer")

    # Import here to avoid circular imports
    from .main_window import MainWindow

    window = MainWindow()
    window.show()

    sys.exit(app.exec())
