"""
Recognizer Module - Panel image recognition for display panels

This module provides functionality to recognize the state of display panel
elements (icons, segment displays) from photographs.

Main classes:
- PanelRecognizer: Main recognition engine
- IconRecognizer: Detects on/off state of indicator icons
- SegmentRecognizer: Recognizes seven-segment display digits

Usage:
    from ramgs.recognizer import PanelRecognizer

    recognizer, error = PanelRecognizer.from_file("panel.panel.json")
    if recognizer:
        result = recognizer.recognize("photo.jpg")
        print(result.format_cli_output())
"""

from .panel_recognizer import PanelRecognizer
from .icon_recognizer import IconRecognizer
from .segment_recognizer import SegmentRecognizer
from .recognition_result import (
    RecognitionResult, IconResult, SegmentResult, IconState
)
from .image_processor import check_opencv

__all__ = [
    'PanelRecognizer',
    'IconRecognizer',
    'SegmentRecognizer',
    'RecognitionResult',
    'IconResult',
    'SegmentResult',
    'IconState',
    'check_opencv',
]
