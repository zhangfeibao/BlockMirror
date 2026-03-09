"""
Canvas Size Dialog - Dialog for setting canvas dimensions
"""

from typing import Tuple

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QSpinBox, QComboBox, QPushButton, QLabel, QGroupBox
)
from PySide6.QtCore import Qt


# Common canvas size presets
PRESETS = [
    ("Custom", 0, 0),
    ("128 x 64 (Small LCD)", 128, 64),
    ("160 x 128 (TFT)", 160, 128),
    ("240 x 240 (Square)", 240, 240),
    ("320 x 240 (QVGA)", 320, 240),
    ("480 x 320 (HVGA)", 480, 320),
    ("800 x 480 (WVGA)", 800, 480),
    ("1024 x 600", 1024, 600),
]


class CanvasSizeDialog(QDialog):
    """Dialog for setting canvas size"""

    def __init__(self, parent=None, width: int = 800, height: int = 480):
        super().__init__(parent)
        self._width = width
        self._height = height
        self._init_ui()

    def _init_ui(self):
        self.setWindowTitle("Canvas Size")
        self.setMinimumWidth(300)

        layout = QVBoxLayout(self)

        # Preset selector
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("Preset:"))
        self.preset_combo = QComboBox()
        for name, w, h in PRESETS:
            self.preset_combo.addItem(name)
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        preset_layout.addWidget(self.preset_combo, 1)
        layout.addLayout(preset_layout)

        # Size inputs
        size_group = QGroupBox("Dimensions")
        size_layout = QFormLayout(size_group)

        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 4096)
        self.width_spin.setValue(self._width)
        self.width_spin.setSuffix(" px")
        self.width_spin.valueChanged.connect(self._on_size_changed)
        size_layout.addRow("Width:", self.width_spin)

        self.height_spin = QSpinBox()
        self.height_spin.setRange(16, 4096)
        self.height_spin.setValue(self._height)
        self.height_spin.setSuffix(" px")
        self.height_spin.valueChanged.connect(self._on_size_changed)
        size_layout.addRow("Height:", self.height_spin)

        layout.addWidget(size_group)

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

        # Check if current size matches a preset
        self._update_preset_selection()

    def _on_preset_changed(self, index: int):
        """Handle preset selection"""
        if index > 0:  # Not "Custom"
            _, w, h = PRESETS[index]
            self.width_spin.blockSignals(True)
            self.height_spin.blockSignals(True)
            self.width_spin.setValue(w)
            self.height_spin.setValue(h)
            self.width_spin.blockSignals(False)
            self.height_spin.blockSignals(False)

    def _on_size_changed(self):
        """Handle manual size change"""
        self._update_preset_selection()

    def _update_preset_selection(self):
        """Update preset combo to match current size"""
        w = self.width_spin.value()
        h = self.height_spin.value()

        self.preset_combo.blockSignals(True)
        for i, (name, pw, ph) in enumerate(PRESETS):
            if pw == w and ph == h:
                self.preset_combo.setCurrentIndex(i)
                break
        else:
            self.preset_combo.setCurrentIndex(0)  # Custom
        self.preset_combo.blockSignals(False)

    def get_size(self) -> Tuple[int, int]:
        """Get the selected canvas size"""
        return self.width_spin.value(), self.height_spin.value()
