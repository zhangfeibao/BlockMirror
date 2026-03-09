"""
Property Panel - Object property editor for Panel Designer

Provides UI for editing display object properties including
geometry, style, and data binding.
"""

from typing import Optional, List

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
    QLabel, QSpinBox, QDoubleSpinBox, QLineEdit, QPushButton,
    QComboBox, QColorDialog, QScrollArea, QFrame, QPlainTextEdit
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor

from .panel_schema import (
    DisplayObject, ObjectType, ObjectStyle, DataBinding, BitBinding, BindingLogic
)


class ColorButton(QPushButton):
    """Button that displays and allows selecting a color"""

    color_changed = Signal(str)

    def __init__(self, color: str = "#000000", parent=None):
        super().__init__(parent)
        self._color = color
        self.setFixedSize(60, 24)
        self._update_style()
        self.clicked.connect(self._on_clicked)

    def set_color(self, color: str):
        self._color = color
        self._update_style()

    def get_color(self) -> str:
        return self._color

    def _update_style(self):
        self.setStyleSheet(f"background-color: {self._color}; border: 1px solid #666;")

    def _on_clicked(self):
        color = QColorDialog.getColor(QColor(self._color), self)
        if color.isValid():
            self._color = color.name()
            self._update_style()
            self.color_changed.emit(self._color)


class BindingEditor(QWidget):
    """Editor for data binding configuration"""

    binding_changed = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._binding: Optional[DataBinding] = None
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Logic selector
        logic_layout = QHBoxLayout()
        logic_layout.addWidget(QLabel("Logic:"))
        self.logic_combo = QComboBox()
        self.logic_combo.addItems(["OR", "AND"])
        self.logic_combo.currentIndexChanged.connect(self._on_logic_changed)
        logic_layout.addWidget(self.logic_combo)
        logic_layout.addStretch()
        layout.addLayout(logic_layout)

        # Bits list
        self.bits_layout = QVBoxLayout()
        layout.addLayout(self.bits_layout)

        # Add button
        add_btn = QPushButton("+ Add Binding")
        add_btn.clicked.connect(self._on_add_binding)
        layout.addWidget(add_btn)

    def set_binding(self, binding: DataBinding):
        self._binding = binding

        # Update logic
        self.logic_combo.blockSignals(True)
        self.logic_combo.setCurrentIndex(0 if binding.logic == BindingLogic.OR else 1)
        self.logic_combo.blockSignals(False)

        # Clear existing bits
        while self.bits_layout.count():
            item = self.bits_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add bit editors
        for bit in binding.bits:
            self._add_bit_row(bit)

    def _add_bit_row(self, bit: BitBinding):
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)

        row_layout.addWidget(QLabel("Byte:"))
        byte_spin = QSpinBox()
        byte_spin.setRange(0, 255)
        byte_spin.setValue(bit.byte_index)
        byte_spin.valueChanged.connect(lambda v: self._on_bit_changed())
        row_layout.addWidget(byte_spin)

        row_layout.addWidget(QLabel("Bit:"))
        bit_spin = QSpinBox()
        bit_spin.setRange(0, 7)
        bit_spin.setValue(bit.bit_index)
        bit_spin.valueChanged.connect(lambda v: self._on_bit_changed())
        row_layout.addWidget(bit_spin)

        remove_btn = QPushButton("X")
        remove_btn.setFixedWidth(24)
        remove_btn.clicked.connect(lambda: self._on_remove_bit(row))
        row_layout.addWidget(remove_btn)

        row.byte_spin = byte_spin
        row.bit_spin = bit_spin

        self.bits_layout.addWidget(row)

    def _on_logic_changed(self, index: int):
        if self._binding:
            self._binding.logic = BindingLogic.OR if index == 0 else BindingLogic.AND
            self.binding_changed.emit(self._binding)

    def _on_add_binding(self):
        if self._binding:
            self._binding.bits.append(BitBinding(0, 0))
            self._add_bit_row(self._binding.bits[-1])
            self.binding_changed.emit(self._binding)

    def _on_remove_bit(self, row: QWidget):
        if self._binding:
            index = self.bits_layout.indexOf(row)
            if 0 <= index < len(self._binding.bits):
                self._binding.bits.pop(index)
                row.deleteLater()
                self.binding_changed.emit(self._binding)

    def _on_bit_changed(self):
        if self._binding:
            self._binding.bits = []
            for i in range(self.bits_layout.count()):
                row = self.bits_layout.itemAt(i).widget()
                if row and hasattr(row, 'byte_spin'):
                    self._binding.bits.append(BitBinding(
                        row.byte_spin.value(),
                        row.bit_spin.value()
                    ))
            self.binding_changed.emit(self._binding)


class PropertyPanel(QWidget):
    """Panel for editing object properties"""

    property_changed = Signal(str, dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._object: Optional[DisplayObject] = None
        self._init_ui()

    def _init_ui(self):
        # Create scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        # Content widget
        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setAlignment(Qt.AlignTop)

        # Annotation group (at top)
        self._annotation_group = QGroupBox("Annotation")
        annotation_layout = QVBoxLayout(self._annotation_group)
        self.annotation_edit = QPlainTextEdit()
        self.annotation_edit.setPlaceholderText("Add description for this object...")
        self.annotation_edit.setMaximumHeight(80)
        self.annotation_edit.textChanged.connect(self._on_annotation_changed)
        annotation_layout.addWidget(self.annotation_edit)
        self._layout.addWidget(self._annotation_group)

        # Geometry group
        self._geom_group = QGroupBox("Geometry")
        self._geom_layout = QFormLayout(self._geom_group)
        self._layout.addWidget(self._geom_group)

        # Style group
        self._style_group = QGroupBox("Style")
        style_layout = QFormLayout(self._style_group)

        self.active_border_btn = ColorButton("#00FF00")
        self.active_border_btn.color_changed.connect(lambda c: self._on_style_changed("active_border_color", c))
        style_layout.addRow("Active Border:", self.active_border_btn)

        self.active_fill_btn = ColorButton("#00FF00")
        self.active_fill_btn.color_changed.connect(lambda c: self._on_style_changed("active_fill_color", c))
        style_layout.addRow("Active Fill:", self.active_fill_btn)

        self.inactive_border_btn = ColorButton("#333333")
        self.inactive_border_btn.color_changed.connect(lambda c: self._on_style_changed("inactive_border_color", c))
        style_layout.addRow("Inactive Border:", self.inactive_border_btn)

        self.inactive_fill_btn = ColorButton("#111111")
        self.inactive_fill_btn.color_changed.connect(lambda c: self._on_style_changed("inactive_fill_color", c))
        style_layout.addRow("Inactive Fill:", self.inactive_fill_btn)

        self.border_width_spin = QSpinBox()
        self.border_width_spin.setRange(0, 20)
        self.border_width_spin.valueChanged.connect(lambda v: self._on_style_changed("border_width", v))
        style_layout.addRow("Border Width:", self.border_width_spin)

        self._layout.addWidget(self._style_group)

        # Text group (only for text objects)
        self._text_group = QGroupBox("Text")
        text_layout = QFormLayout(self._text_group)

        self.text_edit = QLineEdit()
        self.text_edit.textChanged.connect(self._on_text_changed)
        text_layout.addRow("Text:", self.text_edit)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.valueChanged.connect(lambda v: self._on_style_changed("font_size", v))
        text_layout.addRow("Font Size:", self.font_size_spin)

        self.font_family_edit = QLineEdit()
        self.font_family_edit.textChanged.connect(lambda t: self._on_style_changed("font_family", t))
        text_layout.addRow("Font Family:", self.font_family_edit)

        self._layout.addWidget(self._text_group)
        self._text_group.hide()

        # Binding group
        self._binding_group = QGroupBox("Data Binding")
        binding_layout = QVBoxLayout(self._binding_group)

        self.binding_editor = BindingEditor()
        self.binding_editor.binding_changed.connect(self._on_binding_changed)
        binding_layout.addWidget(self.binding_editor)

        self._layout.addWidget(self._binding_group)

        # Spacer
        self._layout.addStretch()

        scroll.setWidget(content)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        # Initially hide all
        self.clear()

    def clear(self):
        """Clear the property panel"""
        self._object = None
        self._annotation_group.hide()
        self._geom_group.hide()
        self._style_group.hide()
        self._text_group.hide()
        self._binding_group.hide()

    def set_object(self, obj: DisplayObject):
        """Set the object to edit"""
        self._object = obj

        # Update annotation
        self.annotation_edit.blockSignals(True)
        self.annotation_edit.setPlainText(obj.annotation)
        self.annotation_edit.blockSignals(False)

        # Clear geometry layout
        while self._geom_layout.count():
            item = self._geom_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add geometry fields based on object type
        geom = obj.geometry

        if obj.obj_type == ObjectType.RECTANGLE:
            self._add_geom_field("X:", "x", geom.get("x", 0))
            self._add_geom_field("Y:", "y", geom.get("y", 0))
            self._add_geom_field("Width:", "width", geom.get("width", 50))
            self._add_geom_field("Height:", "height", geom.get("height", 30))

        elif obj.obj_type == ObjectType.CIRCLE:
            self._add_geom_field("Center X:", "center_x", geom.get("center_x", 0))
            self._add_geom_field("Center Y:", "center_y", geom.get("center_y", 0))
            self._add_geom_field("Radius:", "radius", geom.get("radius", 25))

        elif obj.obj_type == ObjectType.ELLIPSE:
            self._add_geom_field("Center X:", "center_x", geom.get("center_x", 0))
            self._add_geom_field("Center Y:", "center_y", geom.get("center_y", 0))
            self._add_geom_field("Radius X:", "radius_x", geom.get("radius_x", 30))
            self._add_geom_field("Radius Y:", "radius_y", geom.get("radius_y", 20))

        elif obj.obj_type == ObjectType.TEXT:
            self._add_geom_field("X:", "x", geom.get("x", 0))
            self._add_geom_field("Y:", "y", geom.get("y", 0))

        # Update style fields
        style = obj.style
        self.active_border_btn.set_color(style.active_border_color)
        self.active_fill_btn.set_color(style.active_fill_color)
        self.inactive_border_btn.set_color(style.inactive_border_color)
        self.inactive_fill_btn.set_color(style.inactive_fill_color)
        self.border_width_spin.blockSignals(True)
        self.border_width_spin.setValue(style.border_width)
        self.border_width_spin.blockSignals(False)

        # Update text fields
        if obj.obj_type == ObjectType.TEXT:
            self.text_edit.blockSignals(True)
            self.text_edit.setText(obj.text)
            self.text_edit.blockSignals(False)
            self.font_size_spin.blockSignals(True)
            self.font_size_spin.setValue(style.font_size)
            self.font_size_spin.blockSignals(False)
            self.font_family_edit.blockSignals(True)
            self.font_family_edit.setText(style.font_family)
            self.font_family_edit.blockSignals(False)
            self._text_group.show()
        else:
            self._text_group.hide()

        # Update binding
        self.binding_editor.set_binding(obj.binding)

        # Show groups
        self._annotation_group.show()
        self._geom_group.show()
        self._style_group.show()
        self._binding_group.show()

    def set_multiple_objects(self, objects: List[DisplayObject]):
        """Set multiple objects (limited editing)"""
        self._object = None
        self._annotation_group.hide()
        self._geom_group.hide()
        self._text_group.hide()

        # Only show style and binding for multiple selection
        if objects:
            self._style_group.show()
            self._binding_group.show()
        else:
            self.clear()

    def _add_geom_field(self, label: str, key: str, value: float):
        """Add a geometry field"""
        spin = QDoubleSpinBox()
        spin.setRange(-10000, 10000)
        spin.setDecimals(1)
        spin.setValue(value)
        spin.valueChanged.connect(lambda v: self._on_geom_changed(key, v))
        self._geom_layout.addRow(label, spin)

    def _on_geom_changed(self, key: str, value: float):
        """Handle geometry change"""
        if self._object:
            self.property_changed.emit(self._object.id, {"geometry": {key: value}})

    def _on_style_changed(self, key: str, value):
        """Handle style change"""
        if self._object:
            self.property_changed.emit(self._object.id, {"style": {key: value}})

    def _on_text_changed(self, text: str):
        """Handle text change"""
        if self._object:
            self.property_changed.emit(self._object.id, {"text": text})

    def _on_binding_changed(self, binding: DataBinding):
        """Handle binding change"""
        if self._object:
            self.property_changed.emit(self._object.id, {"binding": binding})

    def _on_annotation_changed(self):
        """Handle annotation change"""
        if self._object:
            self.property_changed.emit(self._object.id, {"annotation": self.annotation_edit.toPlainText()})
