"""
Data Queue - Cross-process data sharing for chart module
"""

import sys
import multiprocessing as mp
from typing import Optional
import queue

from .data_types import DataPoint, ChartCommand, ChartConfig, QUEUE_STOP, QUEUE_CLOSE


# Use spawn context for Windows + PyInstaller compatibility
def _get_mp_context():
    """Get multiprocessing context compatible with Windows and PyInstaller"""
    if sys.platform == 'win32':
        return mp.get_context('spawn')
    return mp


class ChartDataQueue:
    """
    Cross-process queue for sharing data with chart window.

    Usage:
        # In main process
        data_queue = ChartDataQueue()
        data_queue.start_chart(config)

        # In data collection loop
        data_queue.put_data(data_point)

        # When done
        data_queue.stop_collection()  # Stops data, keeps window
        data_queue.close()  # Closes window
    """

    def __init__(self):
        self._ctx = _get_mp_context()
        self._queue = None
        self._process = None
        self._config: Optional[ChartConfig] = None

    @property
    def is_active(self) -> bool:
        """Check if chart process is running"""
        return self._process is not None and self._process.is_alive()

    def start_chart(self, config: ChartConfig) -> bool:
        """
        Start chart window process.

        Returns:
            True if started successfully, False otherwise
        """
        if self.is_active:
            return False

        self._config = config
        self._queue = self._ctx.Queue()

        # Import here to avoid loading matplotlib in main process
        from .chart_window import run_chart_window

        self._process = self._ctx.Process(
            target=run_chart_window,
            args=(self._queue, config),
            daemon=False  # Keep running after main exits for ESC behavior
        )
        self._process.start()
        return True

    def put_data(self, data_point: DataPoint) -> bool:
        """
        Send data point to chart window.

        Returns:
            True if sent successfully, False if queue not active
        """
        if not self.is_active or self._queue is None:
            return False

        try:
            cmd = ChartCommand(cmd='data', data=data_point)
            self._queue.put_nowait(cmd)
            return True
        except queue.Full:
            # Drop data if queue is full (shouldn't happen with unbounded queue)
            return False

    def stop_collection(self):
        """Signal that data collection has stopped (chart stays open)"""
        if self._queue is not None:
            try:
                self._queue.put_nowait(QUEUE_STOP)
            except queue.Full:
                pass

    def close(self):
        """Close chart window and cleanup"""
        if self._queue is not None:
            try:
                self._queue.put_nowait(QUEUE_CLOSE)
            except queue.Full:
                pass

        if self._process is not None:
            # Wait briefly for graceful shutdown
            self._process.join(timeout=2.0)
            if self._process.is_alive():
                self._process.terminate()
            self._process = None

        self._queue = None
        self._config = None

    def wait_for_close(self, timeout: Optional[float] = None):
        """Wait for chart window to be closed by user"""
        if self._process is not None:
            self._process.join(timeout=timeout)
