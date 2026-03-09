"""
Recognition Result - Data classes for panel recognition results

Defines the result structures for icon and segment display recognition.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum
import json


class IconState(Enum):
    """State of an icon (on/off/unknown)"""
    ON = "on"
    OFF = "off"
    UNKNOWN = "unknown"


@dataclass
class IconResult:
    """Recognition result for a single icon"""
    id: str
    label: str
    state: IconState
    confidence: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "state": self.state.value,
            "confidence": round(self.confidence, 3)
        }


@dataclass
class SegmentResult:
    """Recognition result for a segment display"""
    id: str
    label: str
    value: str
    confidence: float

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "value": self.value,
            "confidence": round(self.confidence, 3)
        }


@dataclass
class RecognitionResult:
    """Complete recognition result for a panel"""
    success: bool = True
    error: Optional[str] = None
    icons: List[IconResult] = field(default_factory=list)
    segment_displays: List[SegmentResult] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "error": self.error,
            "icons": [icon.to_dict() for icon in self.icons],
            "segment_displays": [seg.to_dict() for seg in self.segment_displays]
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def format_cli_output(self) -> str:
        """Format result for CLI text output"""
        lines = []

        if not self.success:
            return f"Error: {self.error}"

        if self.icons:
            lines.append("Icons:")
            for icon in self.icons:
                state_str = "ON" if icon.state == IconState.ON else "OFF"
                if icon.state == IconState.UNKNOWN:
                    state_str = "UNKNOWN"
                lines.append(f"  {icon.label}: {state_str} ({icon.confidence * 100:.1f}%)")

        if self.segment_displays:
            if lines:
                lines.append("")
            lines.append("Segment Displays:")
            for seg in self.segment_displays:
                lines.append(f"  {seg.label}: {seg.value} ({seg.confidence * 100:.1f}%)")

        if not lines:
            lines.append("No elements recognized.")

        return "\n".join(lines)
