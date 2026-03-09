"""
RAMViewer - MCU RAM Read/Write CLI Tool

A serial-based tool for reading and writing MCU RAM variables.
"""

from .config import VERSION

__version__ = VERSION
__all__ = [
    'config',
    'cli',
    'protocol',
    'serial_manager',
    'state_manager',
    'symbol_resolver',
    'type_converter',
    'variable_parser',
]
