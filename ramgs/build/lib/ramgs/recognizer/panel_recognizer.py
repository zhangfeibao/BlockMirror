"""
Panel Recognizer - Main recognition engine for display panels

Coordinates icon and segment display recognition based on panel design files.
"""

from typing import Optional, Tuple, List
import json
import os

import numpy as np

from .image_processor import load_image, check_opencv, enhance_contrast
from .icon_recognizer import IconRecognizer
from .segment_recognizer import SegmentRecognizer
from .recognition_result import (
    RecognitionResult, IconResult, SegmentResult, IconState
)

# Import panel schema from designer module
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from ..designer.panel_schema import PanelDesign, DisplayObject, ObjectType


# Keywords for detecting segment displays in annotations
SEGMENT_KEYWORDS = [
    "数码管", "segment", "digit", "7-seg", "七段",
    "display", "显示", "number", "数字"
]


class PanelRecognizer:
    """Main recognizer for display panel images"""

    def __init__(self, design: PanelDesign, brightness_threshold: float = 0.4):
        """
        Initialize panel recognizer.

        Args:
            design: Panel design specification
            brightness_threshold: Threshold for on/off detection
        """
        self.design = design
        self.brightness_threshold = brightness_threshold
        self.icon_recognizer = IconRecognizer(brightness_threshold)
        self.segment_recognizer = SegmentRecognizer(brightness_threshold)

    @classmethod
    def from_file(cls, design_path: str,
                  brightness_threshold: float = 0.4) -> Tuple[Optional['PanelRecognizer'], Optional[str]]:
        """
        Create recognizer from a design file.

        Args:
            design_path: Path to .panel.json file
            brightness_threshold: Threshold for on/off detection

        Returns:
            Tuple of (recognizer, error_message)
        """
        if not os.path.exists(design_path):
            return (None, f"Design file not found: {design_path}")

        try:
            with open(design_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            design = PanelDesign.from_dict(data)
            return (cls(design, brightness_threshold), None)
        except json.JSONDecodeError as e:
            return (None, f"Invalid JSON: {e}")
        except Exception as e:
            return (None, f"Failed to load design: {e}")

    def recognize(self, image_path: str) -> RecognitionResult:
        """
        Recognize all elements in a panel image.

        Args:
            image_path: Path to panel image file

        Returns:
            RecognitionResult with all detected elements
        """
        # Check OpenCV availability
        if not check_opencv():
            return RecognitionResult(
                success=False,
                error="OpenCV not available. Install with: pip install opencv-python"
            )

        # Load image
        image = load_image(image_path)
        if image is None:
            return RecognitionResult(
                success=False,
                error=f"Failed to load image: {image_path}"
            )

        # Apply contrast enhancement for better recognition
        image = enhance_contrast(image)

        result = RecognitionResult()

        # Process each object in the design
        for obj in self.design.objects:
            # Skip objects without annotations (can't determine type or label)
            if not obj.annotation:
                continue

            # Determine element type from annotation
            element_type = self._detect_element_type(obj)

            if element_type == "segment_display":
                seg_result = self._recognize_segment(image, obj)
                if seg_result:
                    result.segment_displays.append(seg_result)
            else:
                icon_result = self._recognize_icon(image, obj)
                if icon_result:
                    result.icons.append(icon_result)

        return result

    def _detect_element_type(self, obj: DisplayObject) -> str:
        """
        Detect element type from annotation keywords.

        Args:
            obj: Display object to analyze

        Returns:
            "segment_display" or "icon"
        """
        annotation_lower = obj.annotation.lower()

        for keyword in SEGMENT_KEYWORDS:
            if keyword.lower() in annotation_lower:
                return "segment_display"

        return "icon"

    def _recognize_icon(self, image: np.ndarray,
                       obj: DisplayObject) -> Optional[IconResult]:
        """
        Recognize an icon's state.

        Args:
            image: Panel image
            obj: Display object definition

        Returns:
            IconResult or None
        """
        geom = obj.geometry
        active_color = obj.style.active_fill_color

        if obj.obj_type == ObjectType.RECTANGLE:
            state, confidence = self.icon_recognizer.recognize_rectangle(
                image,
                int(geom.get("x", 0)),
                int(geom.get("y", 0)),
                int(geom.get("width", 50)),
                int(geom.get("height", 30)),
                active_color
            )
        elif obj.obj_type == ObjectType.CIRCLE:
            state, confidence = self.icon_recognizer.recognize_circle(
                image,
                int(geom.get("center_x", 0)),
                int(geom.get("center_y", 0)),
                int(geom.get("radius", 25)),
                active_color
            )
        elif obj.obj_type == ObjectType.ELLIPSE:
            state, confidence = self.icon_recognizer.recognize_ellipse(
                image,
                int(geom.get("center_x", 0)),
                int(geom.get("center_y", 0)),
                int(geom.get("radius_x", 30)),
                int(geom.get("radius_y", 20)),
                active_color
            )
        elif obj.obj_type == ObjectType.POLYGON:
            # For polygons, use bounding box
            x, y, w, h = obj.get_bounding_rect()
            state, confidence = self.icon_recognizer.recognize_rectangle(
                image, int(x), int(y), int(w), int(h), active_color
            )
        else:
            return None

        return IconResult(
            id=obj.id,
            label=obj.annotation,
            state=state,
            confidence=confidence
        )

    def _recognize_segment(self, image: np.ndarray,
                          obj: DisplayObject) -> Optional[SegmentResult]:
        """
        Recognize a segment display's value.

        Args:
            image: Panel image
            obj: Display object definition

        Returns:
            SegmentResult or None
        """
        # Get bounding rectangle
        x, y, w, h = obj.get_bounding_rect()

        # Recognize digits
        value, confidence = self.segment_recognizer.recognize_multi_digit(
            image, int(x), int(y), int(w), int(h)
        )

        return SegmentResult(
            id=obj.id,
            label=obj.annotation,
            value=value,
            confidence=confidence
        )
