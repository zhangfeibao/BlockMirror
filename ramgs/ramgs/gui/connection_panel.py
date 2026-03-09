"""
Connection Panel - Serial port connection management widget
"""

from typing import Optional, Tuple

from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QVBoxLayout, QLabel, QComboBox,
    QPushButton, QGroupBox
)
from PySide6.QtCore import Signal, Slot

from ..serial_manager import SerialManager


class ConnectionPanel(QWidget):
    """Widget for managing serial port connection"""

    connection_changed = Signal(bool, str)  # connected, message

    # Common baud rates
    BAUD_RATES = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]

    def __init__(self, parent=None):
        super().__init__(parent)

        self._serial_manager: Optional[SerialManager] = None
        self._is_connected = False

        self._init_ui()
        self._refresh_ports()

    def _init_ui(self):
        """Initialize the user interface"""
        group = QGroupBox("Connection")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

        group_layout = QHBoxLayout(group)
        group_layout.setSpacing(8)

        # Port selector
        group_layout.addWidget(QLabel("Port:"))
        self.port_combo = QComboBox()
        self.port_combo.setMinimumWidth(100)
        group_layout.addWidget(self.port_combo)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedWidth(60)
        self.refresh_btn.clicked.connect(self._refresh_ports)
        group_layout.addWidget(self.refresh_btn)

        # Baud rate selector
        group_layout.addWidget(QLabel("Baud:"))
        self.baud_combo = QComboBox()
        for baud in self.BAUD_RATES:
            self.baud_combo.addItem(str(baud), baud)
        self.baud_combo.setCurrentText("115200")
        group_layout.addWidget(self.baud_combo)

        # Endian selector
        group_layout.addWidget(QLabel("Endian:"))
        self.endian_combo = QComboBox()
        self.endian_combo.addItem("Little", "little")
        self.endian_combo.addItem("Big", "big")
        group_layout.addWidget(self.endian_combo)

        # Connect button
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setFixedWidth(80)
        self.connect_btn.clicked.connect(self._toggle_connection)
        group_layout.addWidget(self.connect_btn)

    def _refresh_ports(self):
        """Refresh available serial ports"""
        current_port = self.port_combo.currentText()
        self.port_combo.clear()

        ports = SerialManager.list_ports()
        for port_name, description, _ in ports:
            self.port_combo.addItem(f"{port_name}", port_name)

        # Try to restore previous selection
        idx = self.port_combo.findData(current_port)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)

    @Slot()
    def _toggle_connection(self):
        """Toggle connection state"""
        if self._is_connected:
            self.disconnect()
        else:
            self._connect()

    def _connect(self):
        """Establish serial connection"""
        port = self.port_combo.currentData()
        if not port:
            self.connection_changed.emit(False, "No port selected")
            return

        baud = self.baud_combo.currentData()

        self._serial_manager = SerialManager()
        success, error = self._serial_manager.open(port, baud)

        if success:
            self._is_connected = True
            self.connect_btn.setText("Disconnect")
            self._set_controls_enabled(False)
            self.connection_changed.emit(True, f"{port} @ {baud}")
        else:
            self._serial_manager = None
            self.connection_changed.emit(False, error or "Connection failed")

    def disconnect(self):
        """Close serial connection"""
        if self._serial_manager:
            self._serial_manager.close()
            self._serial_manager = None

        self._is_connected = False
        self.connect_btn.setText("Connect")
        self._set_controls_enabled(True)
        self.connection_changed.emit(False, "Disconnected")

    def _set_controls_enabled(self, enabled: bool):
        """Enable/disable connection controls"""
        self.port_combo.setEnabled(enabled)
        self.baud_combo.setEnabled(enabled)
        self.endian_combo.setEnabled(enabled)
        self.refresh_btn.setEnabled(enabled)

    @property
    def is_connected(self) -> bool:
        """Check if connected"""
        return self._is_connected

    @property
    def serial_manager(self) -> Optional[SerialManager]:
        """Get the serial manager instance"""
        return self._serial_manager

    def get_connection_info(self) -> dict:
        """Get current connection info"""
        return {
            'port': self.port_combo.currentData() or "",
            'baud_rate': self.baud_combo.currentData() or 115200,
            'little_endian': self.endian_combo.currentData() == "little"
        }

    def set_connection_info(self, port: str, baud_rate: int, endian: str):
        """Set connection parameters (for project loading)"""
        # Set port
        idx = self.port_combo.findData(port)
        if idx >= 0:
            self.port_combo.setCurrentIndex(idx)

        # Set baud rate
        idx = self.baud_combo.findData(baud_rate)
        if idx >= 0:
            self.baud_combo.setCurrentIndex(idx)

        # Set endian
        idx = self.endian_combo.findData(endian)
        if idx >= 0:
            self.endian_combo.setCurrentIndex(idx)
