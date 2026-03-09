"""
Canvas Widget - Main drawing canvas for Panel Designer

Provides the central canvas area where users can draw and manipulate
display objects.
"""

from typing import Optional, List, Dict, Any, Tuple
from enum import Enum
import copy

from PySide6.QtWidgets import QWidget, QInputDialog
from PySide6.QtCore import Qt, Signal, Slot, QPointF, QRectF, QPoint
from PySide6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QPolygonF,
    QMouseEvent, QWheelEvent, QKeyEvent, QImage, QPixmap,
    QTransform, QCursor
)

from .panel_schema import (
    PanelDesign, DisplayObject, ObjectType, ObjectStyle, DataBinding
)


class ResizeHandle(Enum):
    """Resize handle positions"""
    NONE = 0
    TOP_LEFT = 1
    TOP_RIGHT = 2
    BOTTOM_LEFT = 3
    BOTTOM_RIGHT = 4
    TOP = 5
    BOTTOM = 6
    LEFT = 7
    RIGHT = 8


class CanvasWidget(QWidget):
    """Canvas widget for drawing and editing display objects"""

    # Signals
    mouse_moved = Signal(int, int)
    zoom_changed = Signal(float)
    selection_changed = Signal(list)
    object_created = Signal(object)
    object_modified = Signal(str)

    # Tool constants
    TOOL_SELECT = "select"
    TOOL_RECTANGLE = "rectangle"
    TOOL_CIRCLE = "circle"
    TOOL_ELLIPSE = "ellipse"
    TOOL_POLYGON = "polygon"
    TOOL_TEXT = "text"

    # Handle size in pixels (screen space)
    HANDLE_SIZE = 8

    def __init__(self, parent=None):
        super().__init__(parent)

        self._design: Optional[PanelDesign] = None
        self._zoom: float = 1.0
        self._pan_offset: QPointF = QPointF(50, 50)
        self._current_tool: str = self.TOOL_SELECT
        self._active_layer: str = "design"

        # Selection state
        self._selected_ids: List[str] = []
        self._clipboard: List[DisplayObject] = []

        # Drawing state
        self._is_drawing: bool = False
        self._draw_start: Optional[QPointF] = None
        self._draw_current: Optional[QPointF] = None
        self._polygon_points: List[QPointF] = []

        # Dragging state
        self._is_dragging: bool = False
        self._drag_start: Optional[QPointF] = None
        self._drag_offset: Dict[str, QPointF] = {}

        # Resizing state
        self._is_resizing: bool = False
        self._resize_handle: ResizeHandle = ResizeHandle.NONE
        self._resize_start: Optional[QPointF] = None
        self._resize_obj_id: Optional[str] = None
        self._resize_original_geom: Optional[Dict] = None

        # Selection box state
        self._is_selecting: bool = False
        self._select_start: Optional[QPointF] = None
        self._select_current: Optional[QPointF] = None

        # Panning state
        self._is_panning: bool = False
        self._pan_start: Optional[QPoint] = None

        # Reference image cache
        self._ref_image: Optional[QPixmap] = None
        self._ref_image_path: Optional[str] = None

        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMinimumSize(400, 300)

    def set_design(self, design: PanelDesign):
        """Set the panel design to display"""
        self._design = design
        self._selected_ids = []
        self._ref_image = None
        self._ref_image_path = None
        self.update()

    def set_tool(self, tool: str):
        """Set the current drawing tool"""
        self._current_tool = tool
        self._cancel_drawing()
        self.update()

    def set_active_layer(self, layer: str):
        """Set the active layer for drawing"""
        self._active_layer = layer

    def set_zoom(self, zoom: float):
        """Set zoom level"""
        self._zoom = max(0.1, min(10.0, zoom))
        self.zoom_changed.emit(self._zoom)
        self.update()

    def zoom_in(self):
        """Zoom in by 25%"""
        self.set_zoom(self._zoom * 1.25)

    def zoom_out(self):
        """Zoom out by 25%"""
        self.set_zoom(self._zoom / 1.25)

    def fit_to_view(self):
        """Fit canvas to view"""
        if not self._design:
            return

        canvas_w = self._design.canvas.width
        canvas_h = self._design.canvas.height
        view_w = self.width() - 100
        view_h = self.height() - 100

        zoom_w = view_w / canvas_w
        zoom_h = view_h / canvas_h
        self._zoom = min(zoom_w, zoom_h, 1.0)

        # Center canvas
        self._pan_offset = QPointF(
            (self.width() - canvas_w * self._zoom) / 2,
            (self.height() - canvas_h * self._zoom) / 2
        )

        self.zoom_changed.emit(self._zoom)
        self.update()

    def _screen_to_canvas(self, pos: QPointF) -> QPointF:
        """Convert screen coordinates to canvas coordinates"""
        return QPointF(
            (pos.x() - self._pan_offset.x()) / self._zoom,
            (pos.y() - self._pan_offset.y()) / self._zoom
        )

    def _canvas_to_screen(self, pos: QPointF) -> QPointF:
        """Convert canvas coordinates to screen coordinates"""
        return QPointF(
            pos.x() * self._zoom + self._pan_offset.x(),
            pos.y() * self._zoom + self._pan_offset.y()
        )

    def _cancel_drawing(self):
        """Cancel current drawing operation"""
        self._is_drawing = False
        self._draw_start = None
        self._draw_current = None
        self._polygon_points = []

    # Selection methods
    def select_all(self):
        """Select all objects in active layer"""
        if not self._design:
            return

        layer = self._design.layers.get(self._active_layer)
        if layer and layer.locked:
            return

        self._selected_ids = [
            obj.id for obj in self._design.objects
            if obj.layer == self._active_layer
        ]
        self.selection_changed.emit(self._selected_ids)
        self.update()

    def copy_selection(self):
        """Copy selected objects to clipboard"""
        if not self._design:
            return

        self._clipboard = []
        for obj_id in self._selected_ids:
            obj = self._design.get_object(obj_id)
            if obj:
                self._clipboard.append(copy.deepcopy(obj))

    def paste(self):
        """Paste objects from clipboard"""
        if not self._design or not self._clipboard:
            return

        new_ids = []
        for obj in self._clipboard:
            new_obj = copy.deepcopy(obj)
            new_obj.id = self._design.generate_object_id()
            new_obj.layer = self._active_layer

            # Offset position
            if "x" in new_obj.geometry:
                new_obj.geometry["x"] += 20
            if "y" in new_obj.geometry:
                new_obj.geometry["y"] += 20
            if "center_x" in new_obj.geometry:
                new_obj.geometry["center_x"] += 20
            if "center_y" in new_obj.geometry:
                new_obj.geometry["center_y"] += 20
            if "points" in new_obj.geometry:
                new_obj.geometry["points"] = [
                    [p[0] + 20, p[1] + 20] for p in new_obj.geometry["points"]
                ]

            self.object_created.emit(new_obj)
            new_ids.append(new_obj.id)

        self._selected_ids = new_ids
        self.selection_changed.emit(self._selected_ids)
        self.update()

    def duplicate_selection(self):
        """Duplicate selected objects"""
        self.copy_selection()
        self.paste()

    def delete_selection(self):
        """Delete selected objects"""
        if not self._design:
            return

        for obj_id in self._selected_ids:
            self._design.remove_object(obj_id)

        self._selected_ids = []
        self.selection_changed.emit(self._selected_ids)
        self.update()

    def _get_object_at(self, pos: QPointF) -> Optional[str]:
        """Get object ID at canvas position"""
        if not self._design:
            return None

        # Check in reverse order (top objects first)
        for obj in reversed(self._design.objects):
            layer = self._design.layers.get(obj.layer)
            if layer and (not layer.visible or layer.locked):
                continue

            x, y, w, h = obj.get_bounding_rect()
            rect = QRectF(x, y, w, h)
            if rect.contains(pos):
                return obj.id

        return None

    def _get_objects_in_rect(self, rect: QRectF) -> List[str]:
        """Get all object IDs within a rectangle"""
        if not self._design:
            return []

        result = []
        for obj in self._design.objects:
            layer = self._design.layers.get(obj.layer)
            if layer and (not layer.visible or layer.locked):
                continue

            x, y, w, h = obj.get_bounding_rect()
            obj_rect = QRectF(x, y, w, h)
            if rect.intersects(obj_rect):
                result.append(obj.id)

        return result

    def _get_handle_at(self, canvas_pos: QPointF) -> Tuple[Optional[str], ResizeHandle]:
        """Check if canvas position is on a resize handle of a selected object"""
        if not self._design or not self._selected_ids:
            return None, ResizeHandle.NONE

        handle_size = self.HANDLE_SIZE / self._zoom

        for obj_id in self._selected_ids:
            obj = self._design.get_object(obj_id)
            if not obj:
                continue

            x, y, w, h = obj.get_bounding_rect()
            rect = QRectF(x, y, w, h)

            # Define handle positions and their types
            handles = [
                (rect.topLeft(), ResizeHandle.TOP_LEFT),
                (rect.topRight(), ResizeHandle.TOP_RIGHT),
                (rect.bottomLeft(), ResizeHandle.BOTTOM_LEFT),
                (rect.bottomRight(), ResizeHandle.BOTTOM_RIGHT),
            ]

            for corner, handle_type in handles:
                handle_rect = QRectF(
                    corner.x() - handle_size / 2,
                    corner.y() - handle_size / 2,
                    handle_size, handle_size
                )
                if handle_rect.contains(canvas_pos):
                    return obj_id, handle_type

        return None, ResizeHandle.NONE

    def _get_cursor_for_handle(self, handle: ResizeHandle) -> Qt.CursorShape:
        """Get appropriate cursor for resize handle"""
        cursor_map = {
            ResizeHandle.TOP_LEFT: Qt.SizeFDiagCursor,
            ResizeHandle.BOTTOM_RIGHT: Qt.SizeFDiagCursor,
            ResizeHandle.TOP_RIGHT: Qt.SizeBDiagCursor,
            ResizeHandle.BOTTOM_LEFT: Qt.SizeBDiagCursor,
            ResizeHandle.TOP: Qt.SizeVerCursor,
            ResizeHandle.BOTTOM: Qt.SizeVerCursor,
            ResizeHandle.LEFT: Qt.SizeHorCursor,
            ResizeHandle.RIGHT: Qt.SizeHorCursor,
        }
        return cursor_map.get(handle, Qt.ArrowCursor)

    def _apply_resize(self, obj: DisplayObject, handle: ResizeHandle,
                      start_pos: QPointF, current_pos: QPointF, original_geom: Dict):
        """Apply resize transformation to object"""
        dx = current_pos.x() - start_pos.x()
        dy = current_pos.y() - start_pos.y()

        if obj.obj_type == ObjectType.RECTANGLE:
            x = original_geom.get("x", 0)
            y = original_geom.get("y", 0)
            w = original_geom.get("width", 50)
            h = original_geom.get("height", 30)

            if handle == ResizeHandle.TOP_LEFT:
                obj.geometry["x"] = x + dx
                obj.geometry["y"] = y + dy
                obj.geometry["width"] = max(10, w - dx)
                obj.geometry["height"] = max(10, h - dy)
            elif handle == ResizeHandle.TOP_RIGHT:
                obj.geometry["y"] = y + dy
                obj.geometry["width"] = max(10, w + dx)
                obj.geometry["height"] = max(10, h - dy)
            elif handle == ResizeHandle.BOTTOM_LEFT:
                obj.geometry["x"] = x + dx
                obj.geometry["width"] = max(10, w - dx)
                obj.geometry["height"] = max(10, h + dy)
            elif handle == ResizeHandle.BOTTOM_RIGHT:
                obj.geometry["width"] = max(10, w + dx)
                obj.geometry["height"] = max(10, h + dy)

        elif obj.obj_type == ObjectType.CIRCLE:
            cx = original_geom.get("center_x", 0)
            cy = original_geom.get("center_y", 0)
            r = original_geom.get("radius", 25)

            # Calculate new radius based on drag distance
            if handle in (ResizeHandle.TOP_LEFT, ResizeHandle.BOTTOM_RIGHT):
                delta = (dx + dy) / 2
            else:
                delta = (-dx + dy) / 2

            if handle in (ResizeHandle.TOP_LEFT, ResizeHandle.TOP_RIGHT):
                delta = -delta

            new_r = max(5, r + delta)
            obj.geometry["radius"] = new_r

        elif obj.obj_type == ObjectType.ELLIPSE:
            cx = original_geom.get("center_x", 0)
            cy = original_geom.get("center_y", 0)
            rx = original_geom.get("radius_x", 30)
            ry = original_geom.get("radius_y", 20)

            if handle == ResizeHandle.TOP_LEFT:
                obj.geometry["radius_x"] = max(5, rx - dx / 2)
                obj.geometry["radius_y"] = max(5, ry - dy / 2)
                obj.geometry["center_x"] = cx + dx / 2
                obj.geometry["center_y"] = cy + dy / 2
            elif handle == ResizeHandle.TOP_RIGHT:
                obj.geometry["radius_x"] = max(5, rx + dx / 2)
                obj.geometry["radius_y"] = max(5, ry - dy / 2)
                obj.geometry["center_x"] = cx + dx / 2
                obj.geometry["center_y"] = cy + dy / 2
            elif handle == ResizeHandle.BOTTOM_LEFT:
                obj.geometry["radius_x"] = max(5, rx - dx / 2)
                obj.geometry["radius_y"] = max(5, ry + dy / 2)
                obj.geometry["center_x"] = cx + dx / 2
                obj.geometry["center_y"] = cy + dy / 2
            elif handle == ResizeHandle.BOTTOM_RIGHT:
                obj.geometry["radius_x"] = max(5, rx + dx / 2)
                obj.geometry["radius_y"] = max(5, ry + dy / 2)
                obj.geometry["center_x"] = cx + dx / 2
                obj.geometry["center_y"] = cy + dy / 2

        elif obj.obj_type == ObjectType.POLYGON:
            # Scale polygon points
            points = original_geom.get("points", [])
            if not points:
                return

            # Get original bounding box
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            orig_w = max_x - min_x
            orig_h = max_y - min_y

            if orig_w < 1 or orig_h < 1:
                return

            # Calculate scale factors based on handle
            scale_x = 1.0
            scale_y = 1.0
            offset_x = 0
            offset_y = 0

            if handle == ResizeHandle.BOTTOM_RIGHT:
                scale_x = max(0.1, (orig_w + dx) / orig_w)
                scale_y = max(0.1, (orig_h + dy) / orig_h)
            elif handle == ResizeHandle.TOP_LEFT:
                scale_x = max(0.1, (orig_w - dx) / orig_w)
                scale_y = max(0.1, (orig_h - dy) / orig_h)
                offset_x = dx
                offset_y = dy
            elif handle == ResizeHandle.TOP_RIGHT:
                scale_x = max(0.1, (orig_w + dx) / orig_w)
                scale_y = max(0.1, (orig_h - dy) / orig_h)
                offset_y = dy
            elif handle == ResizeHandle.BOTTOM_LEFT:
                scale_x = max(0.1, (orig_w - dx) / orig_w)
                scale_y = max(0.1, (orig_h + dy) / orig_h)
                offset_x = dx

            # Apply transformation
            new_points = []
            for p in points:
                new_x = min_x + offset_x + (p[0] - min_x) * scale_x
                new_y = min_y + offset_y + (p[1] - min_y) * scale_y
                new_points.append([new_x, new_y])

            obj.geometry["points"] = new_points

    # Event handlers
    def paintEvent(self, event):
        """Paint the canvas"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)

        # Fill background
        painter.fillRect(self.rect(), QColor("#2d2d2d"))

        if not self._design:
            return

        # Apply transform
        painter.translate(self._pan_offset)
        painter.scale(self._zoom, self._zoom)

        # Draw canvas background
        canvas_rect = QRectF(0, 0, self._design.canvas.width, self._design.canvas.height)
        painter.fillRect(canvas_rect, QColor(self._design.canvas.background_color))

        # Draw canvas border
        painter.setPen(QPen(QColor("#666666"), 1 / self._zoom))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(canvas_rect)

        # Draw reference layer
        ref_layer = self._design.layers.get("reference")
        if ref_layer and ref_layer.visible and ref_layer.image_path:
            self._draw_reference_image(painter, ref_layer)

        # Draw background layer
        bg_layer = self._design.layers.get("background")
        if bg_layer and bg_layer.visible:
            painter.setOpacity(bg_layer.opacity)
            self._draw_layer_objects("background", painter)

        # Draw design layer
        design_layer = self._design.layers.get("design")
        if design_layer and design_layer.visible:
            painter.setOpacity(design_layer.opacity)
            self._draw_layer_objects("design", painter)

        painter.setOpacity(1.0)

        # Draw selection handles
        self._draw_selection_handles(painter)

        # Draw current drawing preview
        self._draw_preview(painter)

        # Draw selection box
        if self._is_selecting and self._select_start and self._select_current:
            painter.setPen(QPen(QColor("#4a90d9"), 1 / self._zoom, Qt.DashLine))
            painter.setBrush(QBrush(QColor(74, 144, 217, 50)))
            rect = QRectF(self._select_start, self._select_current).normalized()
            painter.drawRect(rect)

    def _draw_reference_image(self, painter: QPainter, layer):
        """Draw reference image"""
        if layer.image_path != self._ref_image_path:
            self._ref_image = QPixmap(layer.image_path)
            self._ref_image_path = layer.image_path

        if self._ref_image and not self._ref_image.isNull():
            painter.setOpacity(layer.opacity)
            painter.drawPixmap(0, 0, self._ref_image)

    def _draw_layer_objects(self, layer_name: str, painter: QPainter):
        """Draw all objects in a layer"""
        for obj in self._design.objects:
            if obj.layer == layer_name:
                self._draw_object(obj, painter, is_active=True)

    def _draw_object(self, obj: DisplayObject, painter: QPainter, is_active: bool = True):
        """Draw a single display object"""
        style = obj.style

        if is_active:
            border_color = QColor(style.active_border_color)
            fill_color = QColor(style.active_fill_color)
        else:
            border_color = QColor(style.inactive_border_color)
            fill_color = QColor(style.inactive_fill_color)

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
            painter.setPen(fill_color)
            painter.drawText(QPointF(x, y + style.font_size), text)

    def _draw_selection_handles(self, painter: QPainter):
        """Draw selection handles for selected objects"""
        if not self._design:
            return

        handle_size = self.HANDLE_SIZE / self._zoom

        for obj_id in self._selected_ids:
            obj = self._design.get_object(obj_id)
            if not obj:
                continue

            x, y, w, h = obj.get_bounding_rect()
            rect = QRectF(x, y, w, h)

            # Draw selection rectangle
            painter.setPen(QPen(QColor("#4a90d9"), 2 / self._zoom))
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)

            # Draw corner handles
            painter.setPen(QPen(QColor("#4a90d9"), 1 / self._zoom))
            painter.setBrush(QBrush(QColor("#ffffff")))
            corners = [
                rect.topLeft(), rect.topRight(),
                rect.bottomLeft(), rect.bottomRight()
            ]
            for corner in corners:
                handle_rect = QRectF(
                    corner.x() - handle_size / 2,
                    corner.y() - handle_size / 2,
                    handle_size, handle_size
                )
                painter.drawRect(handle_rect)

    def _draw_preview(self, painter: QPainter):
        """Draw preview of current drawing operation"""
        if self._current_tool == self.TOOL_POLYGON:
            self._draw_polygon_preview(painter)
            return

        if not self._is_drawing or not self._draw_start:
            return

        painter.setPen(QPen(QColor("#4a90d9"), 2 / self._zoom, Qt.DashLine))
        painter.setBrush(QBrush(QColor(74, 144, 217, 100)))

        if self._current_tool == self.TOOL_RECTANGLE and self._draw_current:
            rect = QRectF(self._draw_start, self._draw_current).normalized()
            painter.drawRect(rect)

        elif self._current_tool == self.TOOL_CIRCLE and self._draw_current:
            radius = (self._draw_current - self._draw_start).manhattanLength() / 2
            painter.drawEllipse(self._draw_start, radius, radius)

        elif self._current_tool == self.TOOL_ELLIPSE and self._draw_current:
            rect = QRectF(self._draw_start, self._draw_current).normalized()
            painter.drawEllipse(rect)

    def _draw_polygon_preview(self, painter: QPainter):
        """Draw polygon preview with better visual feedback"""
        # Always show current mouse position when polygon tool is active
        if not self._is_drawing and not self._polygon_points:
            return

        point_size = 6 / self._zoom

        # Draw completed segments (solid line)
        if len(self._polygon_points) >= 2:
            painter.setPen(QPen(QColor("#4a90d9"), 2 / self._zoom))
            painter.setBrush(Qt.NoBrush)
            for i in range(len(self._polygon_points) - 1):
                painter.drawLine(self._polygon_points[i], self._polygon_points[i + 1])

        # Draw line from last point to current mouse position (solid)
        if self._polygon_points and self._draw_current:
            painter.setPen(QPen(QColor("#4a90d9"), 2 / self._zoom))
            painter.drawLine(self._polygon_points[-1], self._draw_current)

        # Draw closing line from current position back to first point (dashed)
        if len(self._polygon_points) >= 2 and self._draw_current:
            painter.setPen(QPen(QColor("#4a90d9"), 1 / self._zoom, Qt.DashLine))
            painter.drawLine(self._draw_current, self._polygon_points[0])

        # Draw preview fill if we have enough points
        if len(self._polygon_points) >= 2 and self._draw_current:
            preview_points = self._polygon_points + [self._draw_current]
            polygon = QPolygonF(preview_points)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(74, 144, 217, 50)))
            painter.drawPolygon(polygon)

        # Draw vertex points
        painter.setPen(QPen(QColor("#4a90d9"), 1 / self._zoom))
        painter.setBrush(QBrush(QColor("#ffffff")))
        for i, pt in enumerate(self._polygon_points):
            # First point is larger and different color to indicate closing point
            if i == 0 and len(self._polygon_points) >= 2:
                painter.setBrush(QBrush(QColor("#ff6600")))
                painter.drawEllipse(pt, point_size * 1.2, point_size * 1.2)
                painter.setBrush(QBrush(QColor("#ffffff")))
            else:
                painter.drawEllipse(pt, point_size, point_size)

        # Draw current mouse position point
        if self._draw_current:
            painter.setBrush(QBrush(QColor("#4a90d9")))
            painter.drawEllipse(self._draw_current, point_size * 0.8, point_size * 0.8)

        # Draw instruction text
        if self._polygon_points:
            painter.setPen(QColor("#ffffff"))
            font = QFont("Arial", int(10 / self._zoom))
            painter.setFont(font)
            text_pos = self._polygon_points[0] + QPointF(10 / self._zoom, -10 / self._zoom)
            hint = f"Points: {len(self._polygon_points)} (Double-click or Enter to finish, ESC to cancel)"
            painter.drawText(text_pos, hint)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if not self._design:
            return

        canvas_pos = self._screen_to_canvas(QPointF(event.pos()))

        # Middle button for panning
        if event.button() == Qt.MiddleButton:
            self._is_panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            return

        if event.button() != Qt.LeftButton:
            return

        if self._current_tool == self.TOOL_SELECT:
            # First check if clicking on a resize handle
            obj_id, handle = self._get_handle_at(canvas_pos)
            if obj_id and handle != ResizeHandle.NONE:
                # Start resizing
                self._is_resizing = True
                self._resize_handle = handle
                self._resize_start = canvas_pos
                self._resize_obj_id = obj_id
                obj = self._design.get_object(obj_id)
                if obj:
                    self._resize_original_geom = copy.deepcopy(obj.geometry)
                self.setCursor(self._get_cursor_for_handle(handle))
                return

            # Check if clicking on an object
            obj_id = self._get_object_at(canvas_pos)

            if obj_id:
                if event.modifiers() & Qt.ControlModifier:
                    # Toggle selection
                    if obj_id in self._selected_ids:
                        self._selected_ids.remove(obj_id)
                    else:
                        self._selected_ids.append(obj_id)
                else:
                    if obj_id not in self._selected_ids:
                        self._selected_ids = [obj_id]

                    # Start dragging
                    self._is_dragging = True
                    self._drag_start = canvas_pos
                    self._drag_offset = {}
                    for sid in self._selected_ids:
                        obj = self._design.get_object(sid)
                        if obj:
                            x, y, _, _ = obj.get_bounding_rect()
                            self._drag_offset[sid] = QPointF(canvas_pos.x() - x, canvas_pos.y() - y)
            else:
                # Start selection box
                if not (event.modifiers() & Qt.ControlModifier):
                    self._selected_ids = []
                self._is_selecting = True
                self._select_start = canvas_pos
                self._select_current = canvas_pos

            self.selection_changed.emit(self._selected_ids)

        elif self._current_tool == self.TOOL_POLYGON:
            if not self._is_drawing:
                self._is_drawing = True
                self._polygon_points = [canvas_pos]
            else:
                self._polygon_points.append(canvas_pos)
            self._draw_current = canvas_pos

        elif self._current_tool == self.TOOL_TEXT:
            # Show text input dialog
            text, ok = QInputDialog.getText(self, "Enter Text", "Text:")
            if ok and text:
                obj = DisplayObject(
                    id=self._design.generate_object_id(),
                    obj_type=ObjectType.TEXT,
                    layer=self._active_layer,
                    geometry={"x": canvas_pos.x(), "y": canvas_pos.y()},
                    text=text
                )
                self.object_created.emit(obj)
                self._selected_ids = [obj.id]
                self.selection_changed.emit(self._selected_ids)

        else:
            # Start drawing shape
            self._is_drawing = True
            self._draw_start = canvas_pos
            self._draw_current = canvas_pos

        self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move"""
        canvas_pos = self._screen_to_canvas(QPointF(event.pos()))

        # Emit mouse position
        self.mouse_moved.emit(int(canvas_pos.x()), int(canvas_pos.y()))

        # Handle panning
        if self._is_panning and self._pan_start:
            delta = event.pos() - self._pan_start
            self._pan_offset += QPointF(delta)
            self._pan_start = event.pos()
            self.update()
            return

        # Handle resizing
        if self._is_resizing and self._resize_obj_id and self._resize_original_geom:
            obj = self._design.get_object(self._resize_obj_id)
            if obj:
                self._apply_resize(obj, self._resize_handle, self._resize_start,
                                   canvas_pos, self._resize_original_geom)
                self.object_modified.emit(self._resize_obj_id)
                # Update property panel during resize
                self.selection_changed.emit(self._selected_ids)
            self.update()
            return

        # Handle dragging
        if self._is_dragging and self._design:
            for obj_id in self._selected_ids:
                obj = self._design.get_object(obj_id)
                if obj and obj_id in self._drag_offset:
                    offset = self._drag_offset[obj_id]
                    new_x = canvas_pos.x() - offset.x()
                    new_y = canvas_pos.y() - offset.y()

                    if obj.obj_type in (ObjectType.CIRCLE, ObjectType.ELLIPSE):
                        obj.geometry["center_x"] = new_x + obj.get_bounding_rect()[2] / 2
                        obj.geometry["center_y"] = new_y + obj.get_bounding_rect()[3] / 2
                    elif obj.obj_type == ObjectType.POLYGON:
                        old_x, old_y, _, _ = obj.get_bounding_rect()
                        dx = new_x - old_x
                        dy = new_y - old_y
                        obj.geometry["points"] = [
                            [p[0] + dx, p[1] + dy] for p in obj.geometry.get("points", [])
                        ]
                    else:
                        obj.geometry["x"] = new_x
                        obj.geometry["y"] = new_y

                    self.object_modified.emit(obj_id)

            # Update property panel during drag (fix issue #3)
            self.selection_changed.emit(self._selected_ids)
            self.update()
            return

        # Handle selection box
        if self._is_selecting:
            self._select_current = canvas_pos
            self.update()
            return

        # Handle drawing
        if self._is_drawing:
            self._draw_current = canvas_pos
            self.update()
            return

        # Update polygon preview even when not drawing
        if self._current_tool == self.TOOL_POLYGON:
            self._draw_current = canvas_pos
            self.update()

        # Update cursor based on handle hover
        if self._current_tool == self.TOOL_SELECT and not self._is_dragging:
            obj_id, handle = self._get_handle_at(canvas_pos)
            if handle != ResizeHandle.NONE:
                self.setCursor(self._get_cursor_for_handle(handle))
            else:
                self.setCursor(Qt.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if event.button() == Qt.MiddleButton:
            self._is_panning = False
            self._pan_start = None
            self.setCursor(Qt.ArrowCursor)
            return

        if event.button() != Qt.LeftButton:
            return

        canvas_pos = self._screen_to_canvas(QPointF(event.pos()))

        # Handle resizing end
        if self._is_resizing:
            self._is_resizing = False
            self._resize_handle = ResizeHandle.NONE
            self._resize_start = None
            self._resize_obj_id = None
            self._resize_original_geom = None
            self.setCursor(Qt.ArrowCursor)
            # Final update of property panel
            self.selection_changed.emit(self._selected_ids)
            return

        # Handle selection box
        if self._is_selecting and self._select_start:
            rect = QRectF(self._select_start, canvas_pos).normalized()
            new_selection = self._get_objects_in_rect(rect)
            self._selected_ids = list(set(self._selected_ids + new_selection))
            self._is_selecting = False
            self._select_start = None
            self._select_current = None
            self.selection_changed.emit(self._selected_ids)
            self.update()
            return

        # Handle dragging end
        if self._is_dragging:
            self._is_dragging = False
            self._drag_start = None
            self._drag_offset = {}
            # Final update of property panel (fix issue #3)
            self.selection_changed.emit(self._selected_ids)
            return

        # Handle drawing completion
        if self._is_drawing and self._draw_start and self._design:
            if self._current_tool == self.TOOL_RECTANGLE:
                rect = QRectF(self._draw_start, canvas_pos).normalized()
                if rect.width() > 5 and rect.height() > 5:
                    obj = DisplayObject(
                        id=self._design.generate_object_id(),
                        obj_type=ObjectType.RECTANGLE,
                        layer=self._active_layer,
                        geometry={
                            "x": rect.x(), "y": rect.y(),
                            "width": rect.width(), "height": rect.height()
                        }
                    )
                    self.object_created.emit(obj)
                    self._selected_ids = [obj.id]
                    self.selection_changed.emit(self._selected_ids)

            elif self._current_tool == self.TOOL_CIRCLE:
                radius = (canvas_pos - self._draw_start).manhattanLength() / 2
                if radius > 5:
                    obj = DisplayObject(
                        id=self._design.generate_object_id(),
                        obj_type=ObjectType.CIRCLE,
                        layer=self._active_layer,
                        geometry={
                            "center_x": self._draw_start.x(),
                            "center_y": self._draw_start.y(),
                            "radius": radius
                        }
                    )
                    self.object_created.emit(obj)
                    self._selected_ids = [obj.id]
                    self.selection_changed.emit(self._selected_ids)

            elif self._current_tool == self.TOOL_ELLIPSE:
                rect = QRectF(self._draw_start, canvas_pos).normalized()
                if rect.width() > 5 and rect.height() > 5:
                    obj = DisplayObject(
                        id=self._design.generate_object_id(),
                        obj_type=ObjectType.ELLIPSE,
                        layer=self._active_layer,
                        geometry={
                            "center_x": rect.center().x(),
                            "center_y": rect.center().y(),
                            "radius_x": rect.width() / 2,
                            "radius_y": rect.height() / 2
                        }
                    )
                    self.object_created.emit(obj)
                    self._selected_ids = [obj.id]
                    self.selection_changed.emit(self._selected_ids)

            # Don't end polygon drawing on single click
            if self._current_tool != self.TOOL_POLYGON:
                self._cancel_drawing()

        self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        """Handle mouse double click"""
        if event.button() != Qt.LeftButton:
            return

        # Complete polygon on double click
        if self._current_tool == self.TOOL_POLYGON and self._is_drawing and self._design:
            if len(self._polygon_points) >= 3:
                obj = DisplayObject(
                    id=self._design.generate_object_id(),
                    obj_type=ObjectType.POLYGON,
                    layer=self._active_layer,
                    geometry={
                        "points": [[p.x(), p.y()] for p in self._polygon_points]
                    }
                )
                self.object_created.emit(obj)
                self._selected_ids = [obj.id]
                self.selection_changed.emit(self._selected_ids)

            self._cancel_drawing()
            self.update()

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zooming"""
        delta = event.angleDelta().y()

        # Get mouse position before zoom
        mouse_pos = QPointF(event.position())
        canvas_pos_before = self._screen_to_canvas(mouse_pos)

        # Apply zoom
        if delta > 0:
            self._zoom *= 1.1
        else:
            self._zoom /= 1.1

        self._zoom = max(0.1, min(10.0, self._zoom))

        # Adjust pan to keep mouse position stable
        canvas_pos_after = self._screen_to_canvas(mouse_pos)
        delta_canvas = canvas_pos_after - canvas_pos_before
        self._pan_offset += QPointF(delta_canvas.x() * self._zoom, delta_canvas.y() * self._zoom)

        self.zoom_changed.emit(self._zoom)
        self.update()

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press"""
        if event.key() == Qt.Key_Delete:
            self.delete_selection()
        elif event.key() == Qt.Key_Escape:
            if self._is_drawing:
                self._cancel_drawing()
                self.update()
            else:
                self._selected_ids = []
                self.selection_changed.emit(self._selected_ids)
                self.update()
        elif event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            # Complete polygon on Enter
            if self._current_tool == self.TOOL_POLYGON and self._is_drawing and self._design:
                if len(self._polygon_points) >= 3:
                    obj = DisplayObject(
                        id=self._design.generate_object_id(),
                        obj_type=ObjectType.POLYGON,
                        layer=self._active_layer,
                        geometry={
                            "points": [[p.x(), p.y()] for p in self._polygon_points]
                        }
                    )
                    self.object_created.emit(obj)
                    self._selected_ids = [obj.id]
                    self.selection_changed.emit(self._selected_ids)

                self._cancel_drawing()
                self.update()
        else:
            super().keyPressEvent(event)
