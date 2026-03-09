"""
Chart Module - Realtime data visualization for RAMViewer

Provides:
- ChartWindow: Matplotlib-based realtime chart window
- ChartDataQueue: Cross-process data sharing mechanism
- DataPoint, ChartConfig: Data transfer classes
"""

from .data_types import DataPoint, ChartConfig
from .data_queue import ChartDataQueue

# Lazy import for run_chart_window to avoid loading matplotlib at module import
def run_chart_window(data_queue, config):
    """Entry point for chart process (lazy import to avoid matplotlib dependency at import time)"""
    from .chart_window import run_chart_window as _run
    return _run(data_queue, config)

__all__ = [
    'DataPoint',
    'ChartConfig',
    'ChartDataQueue',
    'run_chart_window',
]
