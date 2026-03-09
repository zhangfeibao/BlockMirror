"""
Data Types - Data transfer classes for chart module
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
import time


@dataclass
class DataPoint:
    """Single data point with timestamp and variable values"""
    timestamp: float  # Unix timestamp
    values: Dict[str, float]  # {var_name: value}

    @classmethod
    def create(cls, var_names: List[str], var_values: List[float]) -> 'DataPoint':
        """Create DataPoint from parallel lists"""
        return cls(
            timestamp=time.time(),
            values=dict(zip(var_names, var_values))
        )


@dataclass
class ChartConfig:
    """Configuration for chart window"""
    var_names: List[str]  # Variable names to display
    max_points: int = 500  # Maximum data points to show
    update_interval_ms: int = 100  # Chart update interval
    title: str = "RAMViewer Realtime Chart"

    # Line colors for up to 8 variables
    colors: List[str] = field(default_factory=lambda: [
        '#1f77b4',  # blue
        '#ff7f0e',  # orange
        '#2ca02c',  # green
        '#d62728',  # red
        '#9467bd',  # purple
        '#8c564b',  # brown
        '#e377c2',  # pink
        '#7f7f7f',  # gray
    ])


@dataclass
class ChartCommand:
    """Command sent to chart process"""
    cmd: str  # 'data', 'stop', 'close'
    data: Optional[DataPoint] = None


# Sentinel value for queue
QUEUE_STOP = ChartCommand(cmd='stop')
QUEUE_CLOSE = ChartCommand(cmd='close')
