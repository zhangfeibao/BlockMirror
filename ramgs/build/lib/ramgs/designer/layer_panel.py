"""
Layer Panel - Layer management for Panel Designer

Provides UI for managing the three fixed layers:
reference, background, and design.
"""

from typing import Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSlider, QFrame, QGroupBox
)
from PySide6.QtCore import Qt, Signal, Slot

from .panel_schema import PanelDesign, LayerConfig


class LayerRow(QWidget):
    """A single layer row in the layer panel"""

    visibility_changed = Signal(str, bool)
    lock_changed = Signal(str, bool)
    opacity_changed = Signal(str, float)
    selected = Signal(str)

    def __init__(self, layer_name: str, display_name: str, parent=None):
        super().__init__(parent)
        self._layer_name = layer_name
        self._is_selected = False
        self._init_ui(display_name)

    def _init_ui(self, display_name: str):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Visibility button
        self.visible_btn = QPushButton()
        self.visible_btn.setFixedSize(24, 24)
        self.visible_btn.setCheckable(True)
        self.visible_btn.setChecked(True)
        self.visible_btn.setText("V")
        self.visible_btn.setToolTip("Toggle Visibility")
        self.visible_btn.toggled.connect(self._on_visibility_toggled)
        layout.addWidget(self.visible_btn)

        # Lock button
        self.lock_btn = QPushButton()
        self.lock_btn.setFixedSize(24, 24)
        self.lock_btn.setCheckable(True)
        self.lock_btn.setText("L")
        self.lock_btn.setToolTip("Toggle Lock")
        self.lock_btn.toggled.connect(self._on_lock_toggled)
        layout.addWidget(self.lock_btn)

        # Layer name (clickable)
        self.name_label = QPushButton(display_name)
        self.name_label.setFlat(True)
        self.name_label.clicked.connect(self._on_selected)
        layout.addWidget(self.name_label, 1)

        # Opacity slider
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(0, 100)
        self.opacity_slider.setValue(100)
        self.opacity_slider.setFixedWidth(60)
        self.opacity_slider.setToolTip("Opacity")
        self.opacity_slider.valueChanged.connect(self._on_opacity_changed)
        layout.addWidget(self.opacity_slider)

        self._update_style()

    def set_config(self, config: LayerConfig):
        """Set layer configuration"""
        self.visible_btn.blockSignals(True)
        self.visible_btn.setChecked(config.visible)
        self.visible_btn.blockSignals(False)

        self.lock_btn.blockSignals(True)
        self.lock_btn.setChecked(config.locked)
        self.lock_btn.blockSignals(False)

        self.opacity_slider.blockSignals(True)
        self.opacity_slider.setValue(int(config.opacity * 100))
        self.opacity_slider.blockSignals(False)

    def set_selected(self, selected: bool):
        """Set selection state"""
        self._is_selected = selected
        self._update_style()

    def _update_style(self):
        """Update visual style based on state"""
        if self._is_selected:
            self.setStyleSheet("background-color: #3a5f8a;")
        else:
            self.setStyleSheet("")

        # Update button styles
        if self.visible_btn.isChecked():
            self.visible_btn.setStyleSheet("background-color: #4a90d9;")
        else:
            self.visible_btn.setStyleSheet("background-color: #555;")

        if self.lock_btn.isChecked():
            self.lock_btn.setStyleSheet("background-color: #d94a4a;")
        else:
            self.lock_btn.setStyleSheet("background-color: #555;")

    def _on_visibility_toggled(self, checked: bool):
        self._update_style()
        self.visibility_changed.emit(self._layer_name, checked)

    def _on_lock_toggled(self, checked: bool):
        self._update_style()
        self.lock_changed.emit(self._layer_name, checked)

    def _on_opacity_changed(self, value: int):
        self.opacity_changed.emit(self._layer_name, value / 100.0)

    def _on_selected(self):
        self.selected.emit(self._layer_name)


class LayerPanel(QWidget):
    """Panel for managing layers"""

    layer_changed = Signal(str, dict)
    active_layer_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._design: Optional[PanelDesign] = None
        self._active_layer: str = "design"
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Title
        title = QLabel("Layers")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)

        # Layer rows (top to bottom = front to back)
        self.design_row = LayerRow("design", "Design Layer")
        self.design_row.visibility_changed.connect(self._on_visibility_changed)
        self.design_row.lock_changed.connect(self._on_lock_changed)
        self.design_row.opacity_changed.connect(self._on_opacity_changed)
        self.design_row.selected.connect(self._on_layer_selected)
        layout.addWidget(self.design_row)

        self.background_row = LayerRow("background", "Background Layer")
        self.background_row.visibility_changed.connect(self._on_visibility_changed)
        self.background_row.lock_changed.connect(self._on_lock_changed)
        self.background_row.opacity_changed.connect(self._on_opacity_changed)
        self.background_row.selected.connect(self._on_layer_selected)
        layout.addWidget(self.background_row)

        self.reference_row = LayerRow("reference", "Reference Layer")
        self.reference_row.visibility_changed.connect(self._on_visibility_changed)
        self.reference_row.lock_changed.connect(self._on_lock_changed)
        self.reference_row.opacity_changed.connect(self._on_opacity_changed)
        self.reference_row.selected.connect(self._on_layer_selected)
        layout.addWidget(self.reference_row)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)

        # Reference image info
        self.ref_info_group = QGroupBox("Reference Image")
        ref_layout = QVBoxLayout(self.ref_info_group)

        self.ref_path_label = QLabel("No image loaded")
        self.ref_path_label.setWordWrap(True)
        self.ref_path_label.setStyleSheet("color: #888;")
        ref_layout.addWidget(self.ref_path_label)

        layout.addWidget(self.ref_info_group)

        # Spacer
        layout.addStretch()

        # Set initial selection
        self._update_selection()

    def set_design(self, design: PanelDesign):
        """Set the panel design"""
        self._design = design
        self.update_layer_state()

    def update_layer_state(self):
        """Update layer UI from design"""
        if not self._design:
            return

        self.design_row.set_config(self._design.layers.get("design", LayerConfig()))
        self.background_row.set_config(self._design.layers.get("background", LayerConfig()))
        self.reference_row.set_config(self._design.layers.get("reference", LayerConfig()))

        # Update reference image info
        ref_layer = self._design.layers.get("reference")
        if ref_layer and ref_layer.image_path:
            self.ref_path_label.setText(ref_layer.image_path)
            self.ref_path_label.setStyleSheet("color: #aaa;")
        else:
            self.ref_path_label.setText("No image loaded")
            self.ref_path_label.setStyleSheet("color: #888;")

    def _update_selection(self):
        """Update selection visual state"""
        self.design_row.set_selected(self._active_layer == "design")
        self.background_row.set_selected(self._active_layer == "background")
        self.reference_row.set_selected(self._active_layer == "reference")

    def _on_visibility_changed(self, layer_name: str, visible: bool):
        self.layer_changed.emit(layer_name, {"visible": visible})

    def _on_lock_changed(self, layer_name: str, locked: bool):
        self.layer_changed.emit(layer_name, {"locked": locked})

    def _on_opacity_changed(self, layer_name: str, opacity: float):
        self.layer_changed.emit(layer_name, {"opacity": opacity})

    def _on_layer_selected(self, layer_name: str):
        # Don't allow selecting reference layer for drawing
        if layer_name == "reference":
            return

        self._active_layer = layer_name
        self._update_selection()
        self.active_layer_changed.emit(layer_name)
