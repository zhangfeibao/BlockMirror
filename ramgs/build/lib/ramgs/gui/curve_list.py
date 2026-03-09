"""
Curve List Panel - List of monitored variables with realtime value display
"""

from typing import List, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea,
    QLabel, QPushButton, QGroupBox, QFrame
)
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtGui import QColor, QFont


class CurveItemWidget(QFrame):
    """Widget representing a single curve item with realtime value"""

    remove_clicked = Signal(str)  # var_id

    def __init__(self, config: dict, parent=None):
        super().__init__(parent)

        self._config = config
        self._var_id = config.get('id', '')

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        self.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
        self.setLineWidth(1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Color indicator
        color = self._config.get('color', '#1f77b4')
        color_label = QLabel()
        color_label.setFixedSize(16, 16)
        color_label.setStyleSheet(
            f"background-color: {color}; border: 1px solid #888; border-radius: 2px;"
        )
        layout.addWidget(color_label)

        # Label
        label = self._config.get('label', self._var_id)
        label_widget = QLabel(label)
        label_widget.setToolTip(f"Path: {self._config.get('path', '')}\n"
                                f"Scale: {self._config.get('scale', 1.0)}")
        layout.addWidget(label_widget, 1)

        # Realtime value display
        self.value_label = QLabel("---")
        self.value_label.setFixedWidth(80)
        self.value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.value_label.setStyleSheet(
            "background-color: #f0f0f0; border: 1px solid #ccc; "
            "border-radius: 2px; padding: 1px 4px; color: red;"
        )
        font = QFont()
        font.setFamily("Consolas")
        font.setBold(True)
        self.value_label.setFont(font)
        layout.addWidget(self.value_label)

        # Remove button
        remove_btn = QPushButton("X")
        remove_btn.setFixedSize(20, 20)
        remove_btn.setStyleSheet("color: red; font-weight: bold;")
        remove_btn.clicked.connect(self._on_remove_clicked)
        layout.addWidget(remove_btn)

    @Slot()
    def _on_remove_clicked(self):
        """Handle remove button click"""
        self.remove_clicked.emit(self._var_id)

    def update_value(self, value: float):
        """Update the displayed realtime value"""
        # Format based on magnitude
        if abs(value) >= 1000:
            text = f"{value:.1f}"
        elif abs(value) >= 1:
            text = f"{value:.2f}"
        elif abs(value) >= 0.01:
            text = f"{value:.4f}"
        else:
            text = f"{value:.6f}"
        self.value_label.setText(text)

    @property
    def var_id(self) -> str:
        """Get variable ID"""
        return self._var_id

    @property
    def config(self) -> dict:
        """Get variable configuration"""
        return self._config


class CurveListPanel(QWidget):
    """Panel showing list of monitored variables with realtime values"""

    variable_removed = Signal(str)  # var_id

    def __init__(self, parent=None):
        super().__init__(parent)

        self._items: Dict[str, CurveItemWidget] = {}

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        group = QGroupBox("Monitored Variables")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(group)

        group_layout = QVBoxLayout(group)
        group_layout.setSpacing(4)

        # Scroll area for variable list
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container widget
        self._container = QWidget()
        self._container_layout = QVBoxLayout(self._container)
        self._container_layout.setContentsMargins(2, 2, 2, 2)
        self._container_layout.setSpacing(2)
        self._container_layout.addStretch()

        scroll.setWidget(self._container)
        group_layout.addWidget(scroll)

    def add_variable(self, config: dict):
        """Add a variable to the monitoring list"""
        var_id = config.get('id', '')

        # Check if already exists
        if var_id in self._items:
            return

        # Create item widget
        item = CurveItemWidget(config)
        item.remove_clicked.connect(self._on_item_remove_clicked)

        # Insert before stretch
        count = self._container_layout.count()
        self._container_layout.insertWidget(count - 1, item)

        self._items[var_id] = item

    def remove_variable(self, var_id: str):
        """Remove a variable from the list"""
        if var_id in self._items:
            item = self._items.pop(var_id)
            self._container_layout.removeWidget(item)
            item.deleteLater()

    def clear(self):
        """Clear all variables"""
        for var_id in list(self._items.keys()):
            self.remove_variable(var_id)

    def update_values(self, data: dict):
        """Update realtime values for all variables"""
        for var_id, item in self._items.items():
            if var_id in data:
                item.update_value(data[var_id])

    def get_all_variables(self) -> List[dict]:
        """Get all variable configurations (all are monitored)"""
        return [item.config for item in self._items.values()]

    def get_all_variables_config(self) -> List[dict]:
        """Get all variable configurations for project save"""
        return [item.config for item in self._items.values()]

    @Slot(str)
    def _on_item_remove_clicked(self, var_id: str):
        """Handle item remove click"""
        self.remove_variable(var_id)
        self.variable_removed.emit(var_id)
