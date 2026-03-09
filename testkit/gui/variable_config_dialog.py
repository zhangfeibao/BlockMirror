"""
Variable Configuration Dialog - Configure monitoring settings for a variable
"""

from typing import Optional, List
import random

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QDoubleSpinBox, QSpinBox,
    QComboBox, QPushButton, QColorDialog, QWidget
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


# Default colors for curves
DEFAULT_COLORS = [
    "#1f77b4",  # Blue
    "#ff7f0e",  # Orange
    "#2ca02c",  # Green
    "#d62728",  # Red
    "#9467bd",  # Purple
    "#8c564b",  # Brown
    "#e377c2",  # Pink
    "#7f7f7f",  # Gray
]


class ColorButton(QPushButton):
    """Button that displays and selects a color"""

    def __init__(self, color: str = "#1f77b4", parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._update_style()
        self.clicked.connect(self._pick_color)
        self.setFixedSize(60, 24)

    def _update_style(self):
        """Update button style to show current color"""
        self.setStyleSheet(
            f"background-color: {self._color.name()}; "
            f"border: 1px solid #888; border-radius: 2px;"
        )

    def _pick_color(self):
        """Open color picker dialog"""
        color = QColorDialog.getColor(self._color, self.parentWidget())
        if color.isValid():
            self._color = color
            self._update_style()

    @property
    def color(self) -> str:
        """Get current color as hex string"""
        return self._color.name()

    @color.setter
    def color(self, value: str):
        """Set color from hex string"""
        self._color = QColor(value)
        self._update_style()


class VariableConfigDialog(QDialog):
    """Dialog to configure variable monitoring settings"""

    def __init__(self, var_info: dict, parent=None):
        super().__init__(parent)

        self._var_info = var_info
        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("Configure Variable")
        self.setMinimumWidth(350)

        layout = QVBoxLayout(self)

        # Variable info (read-only)
        info_layout = QFormLayout()
        info_layout.addRow("Variable:", QLabel(self._var_info.get('path', '')))
        info_layout.addRow("Type:", QLabel(self._var_info.get('dataType', '')))
        layout.addLayout(info_layout)

        layout.addSpacing(10)

        # Configuration form
        form_layout = QFormLayout()

        # Label input
        self.label_edit = QLineEdit()
        self.label_edit.setText(self._var_info.get('path', ''))
        self.label_edit.setPlaceholderText("Display name for the curve")
        form_layout.addRow("Label:", self.label_edit)

        # Scale factor
        self.scale_spin = QDoubleSpinBox()
        self.scale_spin.setRange(-1000000, 1000000)
        self.scale_spin.setDecimals(6)
        self.scale_spin.setValue(1.0)
        self.scale_spin.setSingleStep(0.1)
        form_layout.addRow("Scale (k):", self.scale_spin)

        # Array index (only for arrays)
        is_array = self._var_info.get('isArray', False)
        dims = self._var_info.get('arrayDimensions', [])

        if is_array and dims:
            self.index_spin = QSpinBox()
            self.index_spin.setRange(0, dims[0] - 1)
            self.index_spin.setValue(0)
            form_layout.addRow("Array Index:", self.index_spin)
        else:
            self.index_spin = None

        # Color picker
        color_idx = random.randint(0, len(DEFAULT_COLORS) - 1)
        self.color_btn = ColorButton(DEFAULT_COLORS[color_idx])
        form_layout.addRow("Curve Color:", self.color_btn)

        layout.addLayout(form_layout)
        layout.addSpacing(20)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        ok_btn = QPushButton("OK")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self.accept)
        btn_layout.addWidget(ok_btn)

        layout.addLayout(btn_layout)

    def get_config(self) -> dict:
        """Get the configured variable settings"""
        path = self._var_info.get('path', '')
        array_index = None

        # Append array index to path if applicable
        if self.index_spin is not None:
            array_index = self.index_spin.value()
            path = f"{path}[{array_index}]"

        return {
            'id': path,  # Unique identifier
            'path': path,
            'basePath': self._var_info.get('path', ''),
            'label': self.label_edit.text() or path,
            'scale': self.scale_spin.value(),
            'arrayIndex': array_index,
            'color': self.color_btn.color,
            'visible': True,
            'dataType': self._var_info.get('dataType', ''),
            'baseType': self._var_info.get('baseType', '')
        }
