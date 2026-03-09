"""
Chart Window - Matplotlib-based realtime chart display

Runs in a separate process to avoid blocking main CLI/REPL.
"""

import csv
import queue
import time
from multiprocessing import Queue
from typing import List, Dict, Optional
from tkinter import filedialog
import tkinter as tk

import matplotlib
matplotlib.use('TkAgg')  # Use TkAgg backend for cross-platform compatibility

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.widgets import Button

from .data_types import ChartConfig, ChartCommand, DataPoint


class ChartWindow:
    """Realtime chart window with pause/resume, scroll and export functionality"""

    def __init__(self, data_queue: Queue, config: ChartConfig):
        self.data_queue = data_queue
        self.config = config
        self.var_names = config.var_names
        self.max_display_points = config.max_points  # Points to show in view

        # Data storage - keep ALL data, never delete
        self.timestamps: List[float] = []  # Relative timestamps
        self.raw_timestamps: List[float] = []  # Absolute timestamps for export
        self.data: Dict[str, List[float]] = {
            name: [] for name in self.var_names
        }

        # View state
        self.view_end: Optional[int] = None  # None = follow latest data
        self.paused = False
        self.collection_stopped = False
        self.start_time: Optional[float] = None

        # Setup plot
        self._setup_plot()

    def _setup_plot(self):
        """Initialize matplotlib figure and axes"""
        self.fig, self.ax = plt.subplots(figsize=(10, 6))
        self.fig.canvas.manager.set_window_title(self.config.title)

        # Adjust layout for buttons
        plt.subplots_adjust(bottom=0.2)

        # Create lines for each variable
        self.lines: Dict[str, plt.Line2D] = {}
        for i, name in enumerate(self.var_names):
            color = self.config.colors[i % len(self.config.colors)]
            line, = self.ax.plot([], [], label=name, color=color, linewidth=1.5)
            self.lines[name] = line

        # Configure axes
        self.ax.set_xlabel('Time (s)')
        self.ax.set_ylabel('Value')
        self.ax.legend(loc='upper left')
        self.ax.grid(True, linestyle='--', alpha=0.7)

        # Add buttons
        self._setup_buttons()

    def _setup_buttons(self):
        """Add control buttons"""
        # Navigation buttons (left)
        ax_left = plt.axes([0.02, 0.05, 0.08, 0.05])
        self.btn_left = Button(ax_left, '<< Back')
        self.btn_left.on_clicked(self._on_scroll_left)

        ax_right = plt.axes([0.11, 0.05, 0.08, 0.05])
        self.btn_right = Button(ax_right, 'Fwd >>')
        self.btn_right.on_clicked(self._on_scroll_right)

        ax_latest = plt.axes([0.20, 0.05, 0.08, 0.05])
        self.btn_latest = Button(ax_latest, 'Latest')
        self.btn_latest.on_clicked(self._on_go_latest)

        # Pause/Resume button
        ax_pause = plt.axes([0.70, 0.05, 0.1, 0.05])
        self.btn_pause = Button(ax_pause, 'Pause')
        self.btn_pause.on_clicked(self._on_pause_click)

        # Export button
        ax_export = plt.axes([0.82, 0.05, 0.1, 0.05])
        self.btn_export = Button(ax_export, 'Export')
        self.btn_export.on_clicked(self._on_export_click)

        # Status text
        self.status_text = self.fig.text(
            0.30, 0.02, 'Collecting data...',
            fontsize=9, color='gray'
        )

    def _on_scroll_left(self, event):
        """Scroll view to earlier data"""
        if len(self.timestamps) <= self.max_display_points:
            return

        # Auto-pause when scrolling back
        if not self.paused:
            self.paused = True
            self.btn_pause.label.set_text('Resume')

        if self.view_end is None:
            self.view_end = len(self.timestamps)

        # Scroll back by 1/4 of display window
        scroll_amount = max(1, self.max_display_points // 4)
        self.view_end = max(self.max_display_points, self.view_end - scroll_amount)
        self._update_view()

    def _on_scroll_right(self, event):
        """Scroll view to later data"""
        if self.view_end is None:
            return  # Already at latest

        # Scroll forward by 1/4 of display window
        scroll_amount = max(1, self.max_display_points // 4)
        self.view_end = min(len(self.timestamps), self.view_end + scroll_amount)

        # If reached the end, go back to follow mode
        if self.view_end >= len(self.timestamps):
            self.view_end = None

        self._update_view()

    def _on_go_latest(self, event):
        """Jump to latest data"""
        self.view_end = None
        self._update_view()

    def _on_pause_click(self, event):
        """Handle pause/resume button click"""
        self.paused = not self.paused
        self.btn_pause.label.set_text('Resume' if self.paused else 'Pause')

        # When resuming, go back to following latest data
        if not self.paused:
            self.view_end = None

        self._update_status()

    def _on_export_click(self, event):
        """Handle export button click - save data to CSV"""
        if not self.timestamps:
            return

        # Create a temporary Tk root for file dialog
        root = tk.Tk()
        root.withdraw()  # Hide the root window

        file_path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv'), ('All files', '*.*')],
            title='Export Chart Data'
        )

        root.destroy()

        if file_path:
            self._export_to_csv(file_path)

    def _export_to_csv(self, file_path: str):
        """Export all collected data to CSV file"""
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)

                # Header
                header = ['timestamp', 'time_sec'] + self.var_names
                writer.writerow(header)

                # Data rows - export ALL data
                for i, ts in enumerate(self.raw_timestamps):
                    relative_time = self.timestamps[i] if i < len(self.timestamps) else 0
                    row = [ts, f'{relative_time:.3f}']
                    for name in self.var_names:
                        if i < len(self.data[name]):
                            row.append(self.data[name][i])
                        else:
                            row.append('')
                    writer.writerow(row)

            self._update_status(f'Exported {len(self.timestamps)} points to {file_path}')
        except Exception as e:
            self._update_status(f'Export failed: {e}')

    def _update_status(self, message: Optional[str] = None):
        """Update status text"""
        total_points = len(self.timestamps)

        if message:
            status = message
        elif self.collection_stopped:
            if self.view_end is not None:
                view_start = max(0, self.view_end - self.max_display_points)
                status = f'Stopped. Viewing {view_start+1}-{self.view_end} of {total_points} points'
            else:
                status = f'Stopped. {total_points} points collected.'
        elif self.paused:
            if self.view_end is not None:
                view_start = max(0, self.view_end - self.max_display_points)
                status = f'Paused. Viewing {view_start+1}-{self.view_end} of {total_points} points'
            else:
                status = f'Paused. {total_points} points collected.'
        else:
            status = f'Collecting... {total_points} points'

        self.status_text.set_text(status)

    def _process_queue(self):
        """Process all available data from queue"""
        window_should_close = False

        while True:
            try:
                cmd: ChartCommand = self.data_queue.get_nowait()

                if cmd.cmd == 'close':
                    window_should_close = True
                    break
                elif cmd.cmd == 'stop':
                    self.collection_stopped = True
                    self._update_status()
                elif cmd.cmd == 'data' and cmd.data is not None:
                    self._add_data_point(cmd.data)

            except queue.Empty:
                break

        return window_should_close

    def _add_data_point(self, data_point: DataPoint):
        """Add a data point to storage (never delete old data)"""
        if self.start_time is None:
            self.start_time = data_point.timestamp

        relative_time = data_point.timestamp - self.start_time

        # Store all data
        self.timestamps.append(relative_time)
        self.raw_timestamps.append(data_point.timestamp)

        for name in self.var_names:
            value = data_point.values.get(name, 0.0)
            self.data[name].append(value)

    def _get_view_range(self) -> tuple:
        """Get the current view range (start_idx, end_idx)"""
        total = len(self.timestamps)
        if total == 0:
            return 0, 0

        if self.view_end is None:
            # Follow mode: show latest data
            end_idx = total
        else:
            end_idx = self.view_end

        start_idx = max(0, end_idx - self.max_display_points)
        return start_idx, end_idx

    def _update_view(self):
        """Update the plot with current view range"""
        if not self.timestamps:
            return

        start_idx, end_idx = self._get_view_range()

        # Get visible data
        times = self.timestamps[start_idx:end_idx]

        for name in self.var_names:
            values = self.data[name][start_idx:end_idx]
            self.lines[name].set_data(times, values)

        # Auto-scale axes for visible data
        self._auto_scale_axes(times, start_idx, end_idx)
        self._update_status()
        self.fig.canvas.draw_idle()

    def _update_plot(self, frame):
        """Animation update function"""
        # Process incoming data
        should_close = self._process_queue()
        if should_close:
            plt.close(self.fig)
            return list(self.lines.values())

        # Update status
        if not self.collection_stopped:
            self._update_status()

        # Skip plot update if paused (but still process queue)
        if self.paused:
            return list(self.lines.values())

        # Update lines with current view
        if self.timestamps:
            start_idx, end_idx = self._get_view_range()
            times = self.timestamps[start_idx:end_idx]

            for name in self.var_names:
                values = self.data[name][start_idx:end_idx]
                self.lines[name].set_data(times, values)

            # Auto-scale axes
            self._auto_scale_axes(times, start_idx, end_idx)

        return list(self.lines.values())

    def _auto_scale_axes(self, times: List[float], start_idx: int, end_idx: int):
        """Auto-scale X and Y axes for visible data"""
        if not times:
            return

        # X axis - show visible time range
        x_min, x_max = min(times), max(times)
        x_range = x_max - x_min
        if x_range < 1.0:
            x_range = 1.0
        self.ax.set_xlim(x_min - x_range * 0.02, x_max + x_range * 0.02)

        # Y axis - auto-scale with 10% padding for visible data
        all_values = []
        for name in self.var_names:
            all_values.extend(self.data[name][start_idx:end_idx])

        if all_values:
            y_min, y_max = min(all_values), max(all_values)
            y_range = y_max - y_min
            if y_range == 0:
                y_range = 1.0
            padding = y_range * 0.1
            self.ax.set_ylim(y_min - padding, y_max + padding)

    def run(self):
        """Start the chart window (blocking)"""
        # Create animation
        self.anim = FuncAnimation(
            self.fig,
            self._update_plot,
            interval=self.config.update_interval_ms,
            blit=False,  # Need full redraw for axis scaling
            cache_frame_data=False
        )

        # Show window (blocking)
        plt.show()


def run_chart_window(data_queue: Queue, config: ChartConfig):
    """
    Entry point for chart process.

    This function runs in a separate process and blocks until
    the window is closed.
    """
    window = ChartWindow(data_queue, config)
    window.run()
