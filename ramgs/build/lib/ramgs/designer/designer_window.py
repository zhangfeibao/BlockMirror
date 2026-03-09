"""
Designer Window - Main window for Panel Designer application
"""

import os
from typing import Optional, List

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QStatusBar, QLabel, QFileDialog, QMessageBox,
    QToolButton, QButtonGroup, QDockWidget, QInputDialog
)
from PySide6.QtCore import Qt, QSettings, Signal, Slot, QSize
from PySide6.QtGui import QAction, QIcon, QKeySequence, QColor

from .panel_schema import PanelDesign, DisplayObject, ObjectType, CanvasConfig
from .file_manager import FileManager
from .canvas_widget import CanvasWidget
from .property_panel import PropertyPanel
from .layer_panel import LayerPanel


class DesignerWindow(QMainWindow):
    """Main window for Panel Designer"""

    def __init__(self):
        super().__init__()

        self._current_file: Optional[str] = None
        self._design: PanelDesign = PanelDesign()
        self._modified: bool = False
        self._settings = QSettings("RAMViewer", "PanelDesigner")

        self._init_ui()
        self._create_menus()
        self._create_toolbar()
        self._connect_signals()
        self._restore_state()
        self._update_title()

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("RAMViewer Panel Designer")
        self.setMinimumSize(1200, 800)

        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create main splitter
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Layer panel
        self.layer_panel = LayerPanel()
        self.layer_panel.setMinimumWidth(200)
        self.layer_panel.setMaximumWidth(300)
        self.main_splitter.addWidget(self.layer_panel)

        # Center - Canvas
        self.canvas = CanvasWidget()
        self.canvas.set_design(self._design)
        self.main_splitter.addWidget(self.canvas)

        # Right panel - Property panel
        self.property_panel = PropertyPanel()
        self.property_panel.setMinimumWidth(250)
        self.property_panel.setMaximumWidth(400)
        self.main_splitter.addWidget(self.property_panel)

        # Set splitter sizes
        self.main_splitter.setSizes([220, 700, 280])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

        main_layout.addWidget(self.main_splitter)

        # Create status bar
        self._create_status_bar()

    def _create_menus(self):
        """Create menu bar"""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        self.new_action = QAction("&New", self)
        self.new_action.setShortcut(QKeySequence.New)
        file_menu.addAction(self.new_action)

        self.open_action = QAction("&Open...", self)
        self.open_action.setShortcut(QKeySequence.Open)
        file_menu.addAction(self.open_action)

        file_menu.addSeparator()

        self.save_action = QAction("&Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        file_menu.addAction(self.save_action)

        self.save_as_action = QAction("Save &As...", self)
        self.save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))
        file_menu.addAction(self.save_as_action)

        file_menu.addSeparator()

        self.import_ref_action = QAction("&Import Reference Image...", self)
        file_menu.addAction(self.import_ref_action)

        self.clear_ref_action = QAction("&Clear Reference Image", self)
        file_menu.addAction(self.clear_ref_action)

        file_menu.addSeparator()

        self.exit_action = QAction("E&xit", self)
        self.exit_action.setShortcut(QKeySequence.Quit)
        file_menu.addAction(self.exit_action)

        # Edit menu
        edit_menu = menubar.addMenu("&Edit")

        self.copy_action = QAction("&Copy", self)
        self.copy_action.setShortcut(QKeySequence.Copy)
        edit_menu.addAction(self.copy_action)

        self.paste_action = QAction("&Paste", self)
        self.paste_action.setShortcut(QKeySequence.Paste)
        edit_menu.addAction(self.paste_action)

        self.duplicate_action = QAction("&Duplicate", self)
        self.duplicate_action.setShortcut(QKeySequence("Ctrl+D"))
        edit_menu.addAction(self.duplicate_action)

        self.delete_action = QAction("&Delete", self)
        self.delete_action.setShortcut(QKeySequence.Delete)
        edit_menu.addAction(self.delete_action)

        edit_menu.addSeparator()

        self.select_all_action = QAction("Select &All", self)
        self.select_all_action.setShortcut(QKeySequence.SelectAll)
        edit_menu.addAction(self.select_all_action)

        edit_menu.addSeparator()

        self.canvas_size_action = QAction("Canvas &Size...", self)
        edit_menu.addAction(self.canvas_size_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        self.fit_view_action = QAction("&Fit to Window", self)
        self.fit_view_action.setShortcut(QKeySequence("Ctrl+0"))
        view_menu.addAction(self.fit_view_action)

        self.actual_size_action = QAction("&Actual Size", self)
        self.actual_size_action.setShortcut(QKeySequence("Ctrl+1"))
        view_menu.addAction(self.actual_size_action)

        view_menu.addSeparator()

        self.zoom_in_action = QAction("Zoom &In", self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        view_menu.addAction(self.zoom_in_action)

        self.zoom_out_action = QAction("Zoom &Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        view_menu.addAction(self.zoom_out_action)

    def _create_toolbar(self):
        """Create the main toolbar"""
        toolbar = QToolBar("Tools")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(24, 24))
        self.addToolBar(Qt.LeftToolBarArea, toolbar)

        # Tool button group (mutually exclusive)
        self.tool_group = QButtonGroup(self)
        self.tool_group.setExclusive(True)

        # Select tool
        self.select_tool_btn = QToolButton()
        self.select_tool_btn.setText("Select")
        self.select_tool_btn.setToolTip("Select Tool (V)")
        self.select_tool_btn.setCheckable(True)
        self.select_tool_btn.setChecked(True)
        self.select_tool_btn.setShortcut("V")
        self.tool_group.addButton(self.select_tool_btn, 0)
        toolbar.addWidget(self.select_tool_btn)

        toolbar.addSeparator()

        # Rectangle tool
        self.rect_tool_btn = QToolButton()
        self.rect_tool_btn.setText("Rect")
        self.rect_tool_btn.setToolTip("Rectangle Tool (R)")
        self.rect_tool_btn.setCheckable(True)
        self.rect_tool_btn.setShortcut("R")
        self.tool_group.addButton(self.rect_tool_btn, 1)
        toolbar.addWidget(self.rect_tool_btn)

        # Circle tool
        self.circle_tool_btn = QToolButton()
        self.circle_tool_btn.setText("Circle")
        self.circle_tool_btn.setToolTip("Circle Tool (C)")
        self.circle_tool_btn.setCheckable(True)
        self.circle_tool_btn.setShortcut("C")
        self.tool_group.addButton(self.circle_tool_btn, 2)
        toolbar.addWidget(self.circle_tool_btn)

        # Ellipse tool
        self.ellipse_tool_btn = QToolButton()
        self.ellipse_tool_btn.setText("Ellipse")
        self.ellipse_tool_btn.setToolTip("Ellipse Tool (E)")
        self.ellipse_tool_btn.setCheckable(True)
        self.ellipse_tool_btn.setShortcut("E")
        self.tool_group.addButton(self.ellipse_tool_btn, 3)
        toolbar.addWidget(self.ellipse_tool_btn)

        # Polygon tool
        self.polygon_tool_btn = QToolButton()
        self.polygon_tool_btn.setText("Polygon")
        self.polygon_tool_btn.setToolTip("Polygon Tool (P)")
        self.polygon_tool_btn.setCheckable(True)
        self.polygon_tool_btn.setShortcut("P")
        self.tool_group.addButton(self.polygon_tool_btn, 4)
        toolbar.addWidget(self.polygon_tool_btn)

        # Text tool
        self.text_tool_btn = QToolButton()
        self.text_tool_btn.setText("Text")
        self.text_tool_btn.setToolTip("Text Tool (T)")
        self.text_tool_btn.setCheckable(True)
        self.text_tool_btn.setShortcut("T")
        self.tool_group.addButton(self.text_tool_btn, 5)
        toolbar.addWidget(self.text_tool_btn)

    def _create_status_bar(self):
        """Create the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Mouse position
        self.pos_label = QLabel("X: 0, Y: 0")
        self.status_bar.addWidget(self.pos_label)

        # Separator
        self.status_bar.addWidget(QLabel(" | "))

        # Zoom level
        self.zoom_label = QLabel("100%")
        self.status_bar.addWidget(self.zoom_label)

        # Separator
        self.status_bar.addWidget(QLabel(" | "))

        # Selection info
        self.selection_label = QLabel("No selection")
        self.status_bar.addPermanentWidget(self.selection_label)

    def _connect_signals(self):
        """Connect all signals and slots"""
        # File menu
        self.new_action.triggered.connect(self._on_new)
        self.open_action.triggered.connect(self._on_open)
        self.save_action.triggered.connect(self._on_save)
        self.save_as_action.triggered.connect(self._on_save_as)
        self.import_ref_action.triggered.connect(self._on_import_reference)
        self.clear_ref_action.triggered.connect(self._on_clear_reference)
        self.exit_action.triggered.connect(self.close)

        # Edit menu
        self.copy_action.triggered.connect(self._on_copy)
        self.paste_action.triggered.connect(self._on_paste)
        self.duplicate_action.triggered.connect(self._on_duplicate)
        self.delete_action.triggered.connect(self._on_delete)
        self.select_all_action.triggered.connect(self._on_select_all)
        self.canvas_size_action.triggered.connect(self._on_canvas_size)

        # View menu
        self.fit_view_action.triggered.connect(self._on_fit_view)
        self.actual_size_action.triggered.connect(self._on_actual_size)
        self.zoom_in_action.triggered.connect(self._on_zoom_in)
        self.zoom_out_action.triggered.connect(self._on_zoom_out)

        # Tool buttons
        self.tool_group.idClicked.connect(self._on_tool_changed)

        # Canvas signals
        self.canvas.mouse_moved.connect(self._on_canvas_mouse_moved)
        self.canvas.zoom_changed.connect(self._on_canvas_zoom_changed)
        self.canvas.selection_changed.connect(self._on_selection_changed)
        self.canvas.object_created.connect(self._on_object_created)
        self.canvas.object_modified.connect(self._on_object_modified)

        # Property panel signals
        self.property_panel.property_changed.connect(self._on_property_changed)

        # Layer panel signals
        self.layer_panel.layer_changed.connect(self._on_layer_changed)
        self.layer_panel.active_layer_changed.connect(self._on_active_layer_changed)

    def _restore_state(self):
        """Restore window state from settings"""
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        splitter_state = self._settings.value("splitter_state")
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)

    def closeEvent(self, event):
        """Handle window close event"""
        if self._modified:
            result = QMessageBox.question(
                self, "Unsaved Changes",
                "Save changes before closing?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if result == QMessageBox.Save:
                if not self._on_save():
                    event.ignore()
                    return
            elif result == QMessageBox.Cancel:
                event.ignore()
                return

        # Save window state
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter_state", self.main_splitter.saveState())

        event.accept()

    def _update_title(self):
        """Update window title"""
        title = "RAMViewer Panel Designer"
        if self._current_file:
            filename = os.path.basename(self._current_file)
            title = f"{filename} - {title}"
        if self._modified:
            title = f"* {title}"
        self.setWindowTitle(title)

    def _set_modified(self, modified: bool = True):
        """Set modified state"""
        if self._modified != modified:
            self._modified = modified
            self._update_title()

    def open_file(self, file_path: str):
        """Open a design file"""
        design, error = FileManager.load(file_path)
        if error:
            QMessageBox.critical(self, "Open Failed", error)
            return

        self._design = design
        self._current_file = file_path
        self._set_modified(False)

        # Update UI
        self.canvas.set_design(self._design)
        self.layer_panel.set_design(self._design)
        self._update_title()

    # File menu handlers
    @Slot()
    def _on_new(self):
        """Create new design"""
        if self._modified:
            result = QMessageBox.question(
                self, "Unsaved Changes",
                "Save changes before creating new design?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if result == QMessageBox.Save:
                if not self._on_save():
                    return
            elif result == QMessageBox.Cancel:
                return

        # Ask for canvas size
        from .canvas_size_dialog import CanvasSizeDialog
        dialog = CanvasSizeDialog(self)
        if dialog.exec():
            width, height = dialog.get_size()
            self._design = PanelDesign()
            self._design.canvas.width = width
            self._design.canvas.height = height
            self._current_file = None
            self._set_modified(False)

            self.canvas.set_design(self._design)
            self.layer_panel.set_design(self._design)
            self._update_title()

    @Slot()
    def _on_open(self):
        """Open design file"""
        if self._modified:
            result = QMessageBox.question(
                self, "Unsaved Changes",
                "Save changes before opening another file?",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            if result == QMessageBox.Save:
                if not self._on_save():
                    return
            elif result == QMessageBox.Cancel:
                return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Design",
            "",
            FileManager.get_file_filter()
        )

        if file_path:
            self.open_file(file_path)

    @Slot()
    def _on_save(self) -> bool:
        """Save design file"""
        if self._current_file:
            error = FileManager.save(self._current_file, self._design)
            if error:
                QMessageBox.critical(self, "Save Failed", error)
                return False
            self._set_modified(False)
            return True
        else:
            return self._on_save_as()

    @Slot()
    def _on_save_as(self) -> bool:
        """Save design file as"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Design As",
            "",
            FileManager.get_file_filter()
        )

        if file_path:
            error = FileManager.save(file_path, self._design)
            if error:
                QMessageBox.critical(self, "Save Failed", error)
                return False
            self._current_file = file_path
            self._set_modified(False)
            self._update_title()
            return True
        return False

    @Slot()
    def _on_import_reference(self):
        """Import reference image"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Import Reference Image",
            "",
            "Images (*.png *.jpg *.jpeg *.bmp);;All Files (*)"
        )

        if file_path:
            self._design.layers["reference"].image_path = file_path
            self._design.layers["reference"].visible = True
            self.canvas.update()
            self.layer_panel.update_layer_state()
            self._set_modified(True)

    @Slot()
    def _on_clear_reference(self):
        """Clear reference image"""
        self._design.layers["reference"].image_path = None
        self.canvas.update()
        self.layer_panel.update_layer_state()
        self._set_modified(True)

    # Edit menu handlers
    @Slot()
    def _on_copy(self):
        """Copy selected objects"""
        self.canvas.copy_selection()

    @Slot()
    def _on_paste(self):
        """Paste objects"""
        self.canvas.paste()
        self._set_modified(True)

    @Slot()
    def _on_duplicate(self):
        """Duplicate selected objects"""
        self.canvas.duplicate_selection()
        self._set_modified(True)

    @Slot()
    def _on_delete(self):
        """Delete selected objects"""
        self.canvas.delete_selection()
        self._set_modified(True)

    @Slot()
    def _on_select_all(self):
        """Select all objects in active layer"""
        self.canvas.select_all()

    @Slot()
    def _on_canvas_size(self):
        """Change canvas size"""
        from .canvas_size_dialog import CanvasSizeDialog
        dialog = CanvasSizeDialog(
            self,
            self._design.canvas.width,
            self._design.canvas.height
        )
        if dialog.exec():
            width, height = dialog.get_size()
            self._design.canvas.width = width
            self._design.canvas.height = height
            self.canvas.update()
            self._set_modified(True)

    # View menu handlers
    @Slot()
    def _on_fit_view(self):
        """Fit canvas to view"""
        self.canvas.fit_to_view()

    @Slot()
    def _on_actual_size(self):
        """Reset zoom to 100%"""
        self.canvas.set_zoom(1.0)

    @Slot()
    def _on_zoom_in(self):
        """Zoom in"""
        self.canvas.zoom_in()

    @Slot()
    def _on_zoom_out(self):
        """Zoom out"""
        self.canvas.zoom_out()

    # Tool handlers
    @Slot(int)
    def _on_tool_changed(self, tool_id: int):
        """Handle tool change"""
        tool_map = {
            0: "select",
            1: "rectangle",
            2: "circle",
            3: "ellipse",
            4: "polygon",
            5: "text"
        }
        tool_name = tool_map.get(tool_id, "select")
        self.canvas.set_tool(tool_name)

    # Canvas signal handlers
    @Slot(int, int)
    def _on_canvas_mouse_moved(self, x: int, y: int):
        """Update mouse position in status bar"""
        self.pos_label.setText(f"X: {x}, Y: {y}")

    @Slot(float)
    def _on_canvas_zoom_changed(self, zoom: float):
        """Update zoom level in status bar"""
        self.zoom_label.setText(f"{int(zoom * 100)}%")

    @Slot(list)
    def _on_selection_changed(self, selected_ids: list):
        """Handle selection change"""
        count = len(selected_ids)
        if count == 0:
            self.selection_label.setText("No selection")
            self.property_panel.clear()
        elif count == 1:
            obj = self._design.get_object(selected_ids[0])
            if obj:
                self.selection_label.setText(f"Selected: {obj.obj_type.value}")
                self.property_panel.set_object(obj)
        else:
            self.selection_label.setText(f"Selected: {count} objects")
            self.property_panel.set_multiple_objects(
                [self._design.get_object(oid) for oid in selected_ids if self._design.get_object(oid)]
            )

    @Slot(object)
    def _on_object_created(self, obj: DisplayObject):
        """Handle new object created"""
        self._design.add_object(obj)
        self._set_modified(True)

    @Slot(str)
    def _on_object_modified(self, obj_id: str):
        """Handle object modified"""
        self._set_modified(True)

    # Property panel handlers
    @Slot(str, object)
    def _on_property_changed(self, obj_id: str, changes: dict):
        """Handle property change from property panel"""
        obj = self._design.get_object(obj_id)
        if obj:
            for key, value in changes.items():
                if key == "geometry":
                    obj.geometry.update(value)
                elif key == "style":
                    for sk, sv in value.items():
                        setattr(obj.style, sk, sv)
                elif key == "binding":
                    obj.binding = value
                elif key == "text":
                    obj.text = value
                elif key == "annotation":
                    obj.annotation = value
            self.canvas.update()
            self._set_modified(True)

    # Layer panel handlers
    @Slot(str, dict)
    def _on_layer_changed(self, layer_name: str, changes: dict):
        """Handle layer property change"""
        layer = self._design.layers.get(layer_name)
        if layer:
            for key, value in changes.items():
                setattr(layer, key, value)
            self.canvas.update()
            self._set_modified(True)

    @Slot(str)
    def _on_active_layer_changed(self, layer_name: str):
        """Handle active layer change"""
        self.canvas.set_active_layer(layer_name)
