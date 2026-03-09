"""
Chart Widget - High-performance realtime chart using pyqtgraph
"""

import csv
import time
from typing import Dict, List, Optional
from collections import deque

from PySide6.QtWidgets import QWidget, QVBoxLayout

import pyqtgraph as pg


# Configure pyqtgraph for performance
pg.setConfigOptions(antialias=False, useOpenGL=True)


class ChartWidget(QWidget):
    """High-performance realtime chart widget"""

    MAX_POINTS = 10000  # Maximum points to retain
    VISIBLE_DURATION = 30.0  # Show last 30 seconds
    RIGHT_MARGIN = 3.0  # Right margin in seconds (space after latest data point)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._variables: Dict[str, dict] = {}  # var_id -> config
        self._curves: Dict[str, pg.PlotDataItem] = {}  # var_id -> curve
        self._data: Dict[str, deque] = {}  # var_id -> data points
        self._timestamps: deque = deque(maxlen=self.MAX_POINTS)
        self._start_time: Optional[float] = None
        self._sample_count = 0
        self._auto_scroll = True  # Auto-scroll mode
        self._programmatic_change = False  # Flag to ignore programmatic range changes

        self._init_ui()

    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Create plot widget
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setBackground('w')
        self._plot_widget.showGrid(x=True, y=True, alpha=0.3)

        # Configure axes
        self._plot_widget.setLabel('bottom', 'Time', units='s')
        self._plot_widget.setLabel('left', 'Value')

        # Enable mouse interaction
        self._plot_widget.setMouseEnabled(x=True, y=True)

        # Add legend
        self._legend = self._plot_widget.addLegend()

        # Get ViewBox for signal connections
        self._viewbox = self._plot_widget.getViewBox()

        # Connect to manual range change (user drag/zoom) -> exit auto-scroll
        self._viewbox.sigRangeChangedManually.connect(self._on_manual_range_change)

        # Connect to auto button click -> enter auto-scroll mode
        # The "A" button triggers enableAutoRange, we detect this via sigRangeChanged
        self._viewbox.sigRangeChanged.connect(self._on_range_changed)

        layout.addWidget(self._plot_widget)

    def _on_manual_range_change(self):
        """User manually changed range (drag/zoom) - exit auto-scroll mode"""
        # Ignore if this was triggered by our programmatic change
        if self._programmatic_change:
            return
        self._auto_scroll = False

    def _on_range_changed(self, viewbox, ranges):
        """Range changed - check if it was from auto button"""
        # Ignore programmatic changes
        if self._programmatic_change:
            return
        # When autoRange is triggered (by "A" button), re-enable auto-scroll
        # We detect this by checking if both axes have auto-range enabled
        state = viewbox.state
        if state.get('autoRange', [False, False]) == [True, True]:
            self._auto_scroll = True

    def add_variable(self, config: dict):
        """Add a variable to the chart"""
        var_id = config.get('id', '')

        if var_id in self._variables:
            return

        self._variables[var_id] = config
        self._data[var_id] = deque(maxlen=self.MAX_POINTS)

        # Create curve
        color = config.get('color', '#1f77b4')
        label = config.get('label', var_id)

        pen = pg.mkPen(color=color, width=1.5)
        curve = self._plot_widget.plot(
            [], [],
            pen=pen,
            name=label
        )

        self._curves[var_id] = curve

    def remove_variable(self, var_id: str):
        """Remove a variable from the chart"""
        if var_id in self._variables:
            del self._variables[var_id]

        if var_id in self._data:
            del self._data[var_id]

        if var_id in self._curves:
            self._plot_widget.removeItem(self._curves[var_id])
            del self._curves[var_id]

    def clear_variables(self):
        """Remove all variables"""
        for var_id in list(self._variables.keys()):
            self.remove_variable(var_id)

    def set_variable_visible(self, var_id: str, visible: bool):
        """Set visibility of a variable's curve"""
        if var_id in self._curves:
            self._curves[var_id].setVisible(visible)

    def clear_data(self):
        """Clear all collected data"""
        self._timestamps.clear()
        self._start_time = None
        self._sample_count = 0
        self._auto_scroll = True  # Reset to auto-scroll mode
        self._programmatic_change = False  # Reset flag

        for var_id in self._data:
            self._data[var_id].clear()

        # Clear curves
        for curve in self._curves.values():
            curve.setData([], [])

    def add_data_point(self, data: dict) -> dict:
        """Add a data point to the chart and return scaled values"""
        timestamp = data.get('timestamp', time.time())

        if self._start_time is None:
            self._start_time = timestamp

        relative_time = timestamp - self._start_time
        self._timestamps.append(relative_time)
        self._sample_count += 1

        # Update data for each variable and collect scaled values
        scaled_values = {}
        for var_id, config in self._variables.items():
            if var_id in data:
                raw_value = data[var_id]
                scale = config.get('scale', 1.0)
                scaled_value = raw_value * scale
                self._data[var_id].append(scaled_value)
                scaled_values[var_id] = scaled_value

        # Update curves
        timestamps_list = list(self._timestamps)
        for var_id, curve in self._curves.items():
            if var_id in self._data and self._data[var_id]:
                values = list(self._data[var_id])
                # Ensure same length
                min_len = min(len(timestamps_list), len(values))
                curve.setData(timestamps_list[:min_len], values[:min_len])

        # Auto-scroll to show latest 30 seconds (only if in auto-scroll mode)
        if self._auto_scroll and self._timestamps:
            self._auto_range()

        return scaled_values

    def _auto_range(self):
        """Auto-range the view to show last 30 seconds of data"""
        if not self._timestamps:
            return

        # Show last 30 seconds of data with right margin
        # Latest data point will be at (VISIBLE_DURATION - RIGHT_MARGIN) from left edge
        current_time = self._timestamps[-1]
        x_max = current_time + self.RIGHT_MARGIN
        x_min = x_max - self.VISIBLE_DURATION

        # Set flag to indicate this is a programmatic change
        self._programmatic_change = True

        # Set X range for 30-second window
        self._plot_widget.setXRange(x_min, x_max, padding=0)

        # Auto-scale Y axis to fit visible data
        self._plot_widget.enableAutoRange(axis='y')

        # Clear the flag after a short delay to ensure signals are processed
        self._programmatic_change = False

    @property
    def sample_count(self) -> int:
        """Get the number of samples collected"""
        return self._sample_count

    @property
    def is_auto_scroll(self) -> bool:
        """Check if auto-scroll mode is enabled"""
        return self._auto_scroll

    def export_to_csv(self, file_path: str):
        """Export collected data to CSV file"""
        if not self._timestamps:
            return

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)

            # Header
            var_ids = list(self._variables.keys())
            labels = [self._variables[vid].get('label', vid) for vid in var_ids]
            header = ['timestamp', 'time_sec'] + labels
            writer.writerow(header)

            # Data rows
            timestamps_list = list(self._timestamps)
            for i, rel_time in enumerate(timestamps_list):
                abs_time = self._start_time + rel_time if self._start_time else rel_time
                row = [abs_time, f'{rel_time:.3f}']

                for var_id in var_ids:
                    if var_id in self._data and i < len(self._data[var_id]):
                        row.append(self._data[var_id][i])
                    else:
                        row.append('')

                writer.writerow(row)

    def get_data_for_export(self) -> tuple:
        """Get data for external export (timestamps, variable data dict)"""
        return (
            list(self._timestamps),
            {var_id: list(data) for var_id, data in self._data.items()}
        )
