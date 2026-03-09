"""
Main Window - Primary application window for RAMViewer GUI
"""

import json
import os
from typing import Optional, List, Dict, Any

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QToolBar, QStatusBar, QLabel, QSpinBox, QPushButton,
    QFileDialog, QMessageBox, QGroupBox
)
from PySide6.QtCore import Qt, QSettings, Signal, Slot
from PySide6.QtGui import QAction, QIcon

from .connection_panel import ConnectionPanel
from .symbol_manager import SymbolManager
from .variable_list import VariableListPanel
from .curve_list import CurveListPanel
from .chart_widget import ChartWidget
from .variable_config_dialog import VariableConfigDialog
from .data_collector import DataCollector
from .project_manager import ProjectManager


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        self._project_file: Optional[str] = None
        self._settings = QSettings("RAMViewer", "GUI")
        self._data_collector: Optional[DataCollector] = None
        self._project_manager = ProjectManager()

        self._init_ui()
        self._connect_signals()
        self._restore_state()

    def _init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle("RAMViewer GUI")
        self.setMinimumSize(1200, 700)

        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(4, 4, 4, 4)
        main_layout.setSpacing(4)

        # Create toolbar
        self._create_toolbar()

        # Create connection and symbol panels (horizontal layout)
        top_panel = QWidget()
        top_layout = QHBoxLayout(top_panel)
        top_layout.setContentsMargins(0, 0, 0, 0)
        top_layout.setSpacing(8)

        self.connection_panel = ConnectionPanel()
        self.symbol_manager = SymbolManager()

        top_layout.addWidget(self.connection_panel)
        top_layout.addWidget(self.symbol_manager)
        top_layout.addStretch()

        main_layout.addWidget(top_panel)

        # Create main content area with splitter
        self.main_splitter = QSplitter(Qt.Horizontal)

        # Left panel - Variable list
        self.variable_list = VariableListPanel()
        self.main_splitter.addWidget(self.variable_list)

        # Center - Chart
        self.chart_widget = ChartWidget()
        self.main_splitter.addWidget(self.chart_widget)

        # Right panel - Curve display list
        self.curve_list = CurveListPanel()
        self.main_splitter.addWidget(self.curve_list)

        # Set initial splitter sizes
        self.main_splitter.setSizes([250, 600, 350])
        self.main_splitter.setStretchFactor(0, 0)
        self.main_splitter.setStretchFactor(1, 1)
        self.main_splitter.setStretchFactor(2, 0)

        # Set minimum width for curve list panel
        self.curve_list.setMinimumWidth(300)

        main_layout.addWidget(self.main_splitter, 1)

        # Create status bar
        self._create_status_bar()

    def _create_toolbar(self):
        """Create the main toolbar"""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        # Sampling interval
        toolbar.addWidget(QLabel(" Interval (ms): "))
        self.interval_spin = QSpinBox()
        self.interval_spin.setRange(10, 10000)
        self.interval_spin.setValue(100)
        self.interval_spin.setFixedWidth(80)
        toolbar.addWidget(self.interval_spin)

        toolbar.addSeparator()

        # Start/Stop buttons
        self.start_btn = QPushButton("Start")
        self.start_btn.setFixedWidth(80)
        toolbar.addWidget(self.start_btn)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setEnabled(False)
        toolbar.addWidget(self.stop_btn)

        toolbar.addSeparator()

        # Save CSV button
        self.save_csv_btn = QPushButton("Save CSV")
        self.save_csv_btn.setFixedWidth(80)
        toolbar.addWidget(self.save_csv_btn)

        toolbar.addSeparator()

        # Project buttons
        self.open_project_btn = QPushButton("Open Project")
        self.open_project_btn.setFixedWidth(100)
        toolbar.addWidget(self.open_project_btn)

        self.save_project_btn = QPushButton("Save Project")
        self.save_project_btn.setFixedWidth(100)
        toolbar.addWidget(self.save_project_btn)

    def _create_status_bar(self):
        """Create the status bar"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Connection status
        self.connection_status_label = QLabel("Disconnected")
        self.status_bar.addWidget(self.connection_status_label)

        # Separator
        self.status_bar.addWidget(QLabel(" | "))

        # Sample count
        self.sample_count_label = QLabel("Samples: 0")
        self.status_bar.addWidget(self.sample_count_label)

        # Error count
        self.error_count_label = QLabel("")
        self.status_bar.addPermanentWidget(self.error_count_label)

    def _connect_signals(self):
        """Connect all signals and slots"""
        # Connection panel
        self.connection_panel.connection_changed.connect(self._on_connection_changed)

        # Symbol manager
        self.symbol_manager.symbols_loaded.connect(self._on_symbols_loaded)

        # Variable list - double click to add
        self.variable_list.variable_double_clicked.connect(self._on_variable_double_clicked)

        # Curve list
        self.curve_list.variable_removed.connect(self._on_variable_removed)

        # Toolbar buttons
        self.start_btn.clicked.connect(self._on_start_collection)
        self.stop_btn.clicked.connect(self._on_stop_collection)
        self.save_csv_btn.clicked.connect(self._on_save_csv)
        self.open_project_btn.clicked.connect(self._on_open_project)
        self.save_project_btn.clicked.connect(self._on_save_project)

    def _restore_state(self):
        """Restore window state from settings"""
        # Window geometry
        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

        # Splitter state
        splitter_state = self._settings.value("splitter_state")
        if splitter_state:
            self.main_splitter.restoreState(splitter_state)

        # Last project file
        last_project = self._settings.value("last_project")
        if last_project and os.path.exists(last_project):
            # Optionally auto-load last project
            pass

    def closeEvent(self, event):
        """Handle window close event"""
        # Stop data collection if running
        if self._data_collector and self._data_collector.isRunning():
            self._data_collector.stop()
            self._data_collector.wait(2000)

        # Disconnect serial
        self.connection_panel.disconnect()

        # Save window state
        self._settings.setValue("geometry", self.saveGeometry())
        self._settings.setValue("splitter_state", self.main_splitter.saveState())

        if self._project_file:
            self._settings.setValue("last_project", self._project_file)

        event.accept()

    @Slot(bool, str)
    def _on_connection_changed(self, connected: bool, message: str):
        """Handle connection state change"""
        if connected:
            self.connection_status_label.setText(f"Connected: {message}")
            self.connection_status_label.setStyleSheet("color: green;")
        else:
            # Only update if not collecting
            if not (self._data_collector and self._data_collector.isRunning()):
                self.connection_status_label.setText("Disconnected")
                self.connection_status_label.setStyleSheet("color: gray;")

    @Slot(object)
    def _on_symbols_loaded(self, resolver):
        """Handle symbols loaded event"""
        self.variable_list.set_resolver(resolver)
        self._update_window_title()

    @Slot(dict)
    def _on_variable_double_clicked(self, var_info: dict):
        """Handle double-click on variable in list"""
        dialog = VariableConfigDialog(var_info, self)
        if dialog.exec():
            config = dialog.get_config()
            self.curve_list.add_variable(config)
            self.chart_widget.add_variable(config)

    @Slot(str)
    def _on_variable_removed(self, var_id: str):
        """Handle variable removal from curve list"""
        self.chart_widget.remove_variable(var_id)

    @Slot()
    def _on_start_collection(self):
        """Start data collection"""
        # Get connection info
        conn_info = self.connection_panel.get_connection_info()

        # Check if port is selected
        if not conn_info['port']:
            QMessageBox.warning(
                self, "No Port Selected",
                "Please select a serial port first."
            )
            return

        # Check if symbols file is loaded
        if not self.symbol_manager.symbols_file:
            QMessageBox.warning(
                self, "No Symbols",
                "Please load a symbols file first."
            )
            return

        # Check if we have variables to monitor
        variables = self.curve_list.get_all_variables()
        if not variables:
            QMessageBox.warning(
                self, "No Variables",
                "Please add variables to monitor first."
            )
            return

        # Disconnect connection panel to release the port for DataCollector
        if self.connection_panel.is_connected:
            self.connection_panel.disconnect()

        interval_ms = self.interval_spin.value()

        # Create and start data collector
        self._data_collector = DataCollector(
            port_name=conn_info['port'],
            baud_rate=conn_info['baud_rate'],
            little_endian=conn_info['little_endian'],
            symbols_file=self.symbol_manager.symbols_file,
            variables=variables,
            interval_ms=interval_ms
        )

        self._data_collector.data_received.connect(self._on_data_received)
        self._data_collector.error_occurred.connect(self._on_collection_error)
        self._data_collector.collection_stopped.connect(self._on_collection_stopped)

        self._data_collector.start()

        # Update UI
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.interval_spin.setEnabled(False)
        self.connection_panel.setEnabled(False)
        self.sample_count_label.setText("Samples: 0")
        self.error_count_label.setText("")

        # Update status
        self.connection_status_label.setText(f"Collecting: {conn_info['port']}")
        self.connection_status_label.setStyleSheet("color: blue;")

        # Clear chart for new collection
        self.chart_widget.clear_data()

    @Slot()
    def _on_stop_collection(self):
        """Stop data collection"""
        if self._data_collector and self._data_collector.isRunning():
            self._data_collector.stop()
            # Wait for thread to finish (with timeout)
            self._data_collector.wait(3000)  # 3 seconds timeout

    @Slot(dict)
    def _on_data_received(self, data: dict):
        """Handle received data point"""
        # Add to chart and get scaled values
        scaled_values = self.chart_widget.add_data_point(data)

        # Update realtime values in curve list
        self.curve_list.update_values(scaled_values)

        # Update sample count
        sample_count = self.chart_widget.sample_count
        self.sample_count_label.setText(f"Samples: {sample_count}")

    @Slot(str)
    def _on_collection_error(self, error: str):
        """Handle collection error"""
        error_count = self._data_collector.error_count if self._data_collector else 0
        self.error_count_label.setText(f"Errors: {error_count}")
        self.error_count_label.setStyleSheet("color: red;")

    @Slot()
    def _on_collection_stopped(self):
        """Handle collection stopped"""
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)
        self.interval_spin.setEnabled(True)
        self.connection_panel.setEnabled(True)

        # Update status
        self.connection_status_label.setText("Stopped")
        self.connection_status_label.setStyleSheet("color: gray;")

    @Slot()
    def _on_save_csv(self):
        """Save collected data to CSV"""
        if self.chart_widget.sample_count == 0:
            QMessageBox.information(
                self, "No Data",
                "No data to export. Start collection first."
            )
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save CSV", "", "CSV Files (*.csv);;All Files (*)"
        )

        if file_path:
            try:
                self.chart_widget.export_to_csv(file_path)
                QMessageBox.information(
                    self, "Export Complete",
                    f"Data exported to {file_path}"
                )
            except Exception as e:
                QMessageBox.critical(
                    self, "Export Failed",
                    f"Failed to export data: {e}"
                )

    @Slot()
    def _on_open_project(self):
        """Open a project file"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Open Project", "",
            "RAMViewer Project (*.ramproj);;JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                project_data = self._project_manager.load_project(file_path)
                self._apply_project(project_data)
                self._project_file = file_path
                self._update_window_title()
            except Exception as e:
                QMessageBox.critical(
                    self, "Load Failed",
                    f"Failed to load project: {e}"
                )

    @Slot()
    def _on_save_project(self):
        """Save current configuration to project file"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Project", "",
            "RAMViewer Project (*.ramproj);;JSON Files (*.json);;All Files (*)"
        )

        if file_path:
            try:
                project_data = self._collect_project_data()
                self._project_manager.save_project(file_path, project_data)
                self._project_file = file_path
                self._update_window_title()
            except Exception as e:
                QMessageBox.critical(
                    self, "Save Failed",
                    f"Failed to save project: {e}"
                )

    def _collect_project_data(self) -> dict:
        """Collect current configuration into project data"""
        conn_info = self.connection_panel.get_connection_info()

        return {
            "version": "1.0",
            "connection": {
                "port": conn_info['port'],
                "baudRate": conn_info['baud_rate'],
                "endian": "little" if conn_info['little_endian'] else "big"
            },
            "symbolsFile": self.symbol_manager.symbols_file,
            "monitoredVariables": self.curve_list.get_all_variables_config(),
            "samplingIntervalMs": self.interval_spin.value()
        }

    def _apply_project(self, project_data: dict):
        """Apply project configuration"""
        # Apply connection settings
        conn = project_data.get("connection", {})
        self.connection_panel.set_connection_info(
            port=conn.get("port", ""),
            baud_rate=conn.get("baudRate", 115200),
            endian=conn.get("endian", "little")
        )

        # Load symbols file
        symbols_file = project_data.get("symbolsFile")
        if symbols_file:
            if os.path.exists(symbols_file):
                self.symbol_manager.load_symbols(symbols_file)
            else:
                QMessageBox.warning(
                    self, "Symbols File Not Found",
                    f"Symbols file not found: {symbols_file}\n"
                    "Please load symbols manually."
                )

        # Apply sampling interval
        self.interval_spin.setValue(project_data.get("samplingIntervalMs", 100))

        # Clear and add monitored variables
        self.curve_list.clear()
        self.chart_widget.clear_variables()

        for var_config in project_data.get("monitoredVariables", []):
            self.curve_list.add_variable(var_config)
            self.chart_widget.add_variable(var_config)

    def _update_window_title(self):
        """Update window title with project name"""
        title = "RAMViewer GUI"
        if self._project_file:
            project_name = os.path.basename(self._project_file)
            title = f"{project_name} - {title}"
        self.setWindowTitle(title)
