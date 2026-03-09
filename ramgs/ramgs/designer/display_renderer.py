"""
Display Renderer - Render panel design to image with buffer data

Renders a panel design file with MCU buffer data to generate
a PNG image showing the display state.
"""

import os
import sys
from datetime import datetime
from typing import Optional, Tuple, List

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QPen, QBrush, QFont, QPolygonF
from PySide6.QtWidgets import QApplication

from .panel_schema import PanelDesign, DisplayObject, ObjectType
from .file_manager import FileManager


# Temp directory for generated images
TEMP_DIR = 'ramgs_tmp_imgs'

# Global QApplication instance for headless rendering
_app_instance = None


def _ensure_qapp():
    """Ensure a QApplication instance exists for Qt rendering"""
    global _app_instance
    if QApplication.instance() is None:
        # Create a headless QApplication for rendering
        _app_instance = QApplication(sys.argv)
    return QApplication.instance()


class DisplayRenderer:
    """Renders panel designs to images"""

    def __init__(self, design: PanelDesign):
        """
        Initialize renderer with a panel design.

        Args:
            design: PanelDesign to render
        """
        self.design = design

    @classmethod
    def from_file(cls, file_path: str) -> Tuple[Optional['DisplayRenderer'], Optional[str]]:
        """
        Create renderer from a design file.

        Args:
            file_path: Path to .panel.json file

        Returns:
            Tuple of (DisplayRenderer or None, error message or None)
        """
        design, error = FileManager.load(file_path)
        if error:
            return None, error
        return cls(design), None

    def render(self, buffer_data: bytes, output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Render the panel with buffer data and save to file.

        Args:
            buffer_data: MCU buffer data bytes
            output_dir: Output directory (default: ramgs_tmp_imgs in cwd)

        Returns:
            Tuple of (image file path or None, error message or None)
        """
        # Ensure QApplication exists for Qt rendering
        _ensure_qapp()

        if output_dir is None:
            output_dir = os.path.join(os.getcwd(), TEMP_DIR)

        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)

        # Create image
        width = self.design.canvas.width
        height = self.design.canvas.height

        image = QImage(width, height, QImage.Format_ARGB32)
        image.fill(QColor(self.design.canvas.background_color))

        # Create painter
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        try:
            # Render background layer (if visible)
            bg_layer = self.design.layers.get("background")
            if bg_layer and bg_layer.visible:
                self._render_layer("background", buffer_data, painter, bg_layer.opacity)

            # Render design layer (if visible)
            design_layer = self.design.layers.get("design")
            if design_layer and design_layer.visible:
                self._render_layer("design", buffer_data, painter, design_layer.opacity)

        finally:
            painter.end()

        # Generate filename
        filename = self._generate_filename()
        file_path = os.path.join(output_dir, filename)

        # Save image
        if not image.save(file_path, "PNG"):
            return None, f"Failed to save image: {file_path}"

        return file_path, None

    def _render_layer(self, layer_name: str, buffer_data: bytes,
                      painter: QPainter, opacity: float):
        """Render all objects in a layer"""
        objects = self.design.get_objects_by_layer(layer_name)

        for obj in objects:
            # Evaluate binding to determine active state
            is_active = obj.binding.evaluate(buffer_data)

            # Set opacity
            painter.setOpacity(opacity)

            # Render object
            self._render_object(obj, is_active, painter)

    def _render_object(self, obj: DisplayObject, is_active: bool, painter: QPainter):
        """Render a single display object"""
        style = obj.style

        # Choose colors based on active state
        if is_active:
            border_color = QColor(style.active_border_color)
            fill_color = QColor(style.active_fill_color)
        else:
            border_color = QColor(style.inactive_border_color)
            fill_color = QColor(style.inactive_fill_color)

        # Set pen and brush
        pen = QPen(border_color, style.border_width)
        brush = QBrush(fill_color)
        painter.setPen(pen)
        painter.setBrush(brush)

        geom = obj.geometry

        if obj.obj_type == ObjectType.RECTANGLE:
            x = geom.get("x", 0)
            y = geom.get("y", 0)
            w = geom.get("width", 50)
            h = geom.get("height", 30)
            painter.drawRect(QRectF(x, y, w, h))

        elif obj.obj_type == ObjectType.CIRCLE:
            cx = geom.get("center_x", 0)
            cy = geom.get("center_y", 0)
            r = geom.get("radius", 25)
            painter.drawEllipse(QPointF(cx, cy), r, r)

        elif obj.obj_type == ObjectType.ELLIPSE:
            cx = geom.get("center_x", 0)
            cy = geom.get("center_y", 0)
            rx = geom.get("radius_x", 30)
            ry = geom.get("radius_y", 20)
            painter.drawEllipse(QPointF(cx, cy), rx, ry)

        elif obj.obj_type == ObjectType.POLYGON:
            points = geom.get("points", [])
            if points:
                polygon = QPolygonF([QPointF(p[0], p[1]) for p in points])
                painter.drawPolygon(polygon)

        elif obj.obj_type == ObjectType.TEXT:
            x = geom.get("x", 0)
            y = geom.get("y", 0)
            text = obj.text

            font = QFont(style.font_family, style.font_size)
            painter.setFont(font)

            # For text, use fill color as text color
            painter.setPen(fill_color)
            painter.drawText(QPointF(x, y + style.font_size), text)

    def _generate_filename(self) -> str:
        """Generate a unique filename for the output image"""
        now = datetime.now()
        timestamp = now.strftime('%Y%m%d_%H%M%S') + f'_{now.microsecond // 1000:03d}'
        return f'display_{timestamp}.png'


def render_display(design_file: str, buffer_data: bytes,
                   output_dir: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Convenience function to render a display image.

    Args:
        design_file: Path to .panel.json file
        buffer_data: MCU buffer data bytes
        output_dir: Output directory (optional)

    Returns:
        Tuple of (image file path or None, error message or None)
    """
    renderer, error = DisplayRenderer.from_file(design_file)
    if error:
        return None, error

    return renderer.render(buffer_data, output_dir)
