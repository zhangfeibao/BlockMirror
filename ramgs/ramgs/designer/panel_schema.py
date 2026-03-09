"""
Panel Schema - Design file format definitions for panel designer

Defines the JSON schema for .panel.json files used by the panel designer
and display renderer.
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import json


# Current schema version
SCHEMA_VERSION = "1.0"


class ObjectType(Enum):
    """Types of display objects"""
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    ELLIPSE = "ellipse"
    POLYGON = "polygon"
    TEXT = "text"


class BindingLogic(Enum):
    """Logic for combining multiple bit bindings"""
    OR = "or"
    AND = "and"


@dataclass
class BitBinding:
    """A single bit binding (byte index + bit index)"""
    byte_index: int
    bit_index: int

    def to_dict(self) -> dict:
        return {
            "byte_index": self.byte_index,
            "bit_index": self.bit_index
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'BitBinding':
        return cls(
            byte_index=data.get("byte_index", 0),
            bit_index=data.get("bit_index", 0)
        )


@dataclass
class DataBinding:
    """Data binding configuration for a display object"""
    logic: BindingLogic = BindingLogic.OR
    bits: List[BitBinding] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "logic": self.logic.value,
            "bits": [b.to_dict() for b in self.bits]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'DataBinding':
        logic = BindingLogic(data.get("logic", "or"))
        bits = [BitBinding.from_dict(b) for b in data.get("bits", [])]
        return cls(logic=logic, bits=bits)

    def evaluate(self, buffer_data: bytes) -> bool:
        """
        Evaluate binding against buffer data.

        Returns True if object should be in active state.
        """
        if not self.bits:
            # No binding = always active
            return True

        results = []
        for bit in self.bits:
            if bit.byte_index < len(buffer_data):
                byte_val = buffer_data[bit.byte_index]
                bit_set = bool(byte_val & (1 << bit.bit_index))
                results.append(bit_set)
            else:
                # Out of range = treat as 0
                results.append(False)

        if not results:
            return True

        if self.logic == BindingLogic.OR:
            return any(results)
        else:  # AND
            return all(results)


@dataclass
class ObjectStyle:
    """Style configuration for a display object"""
    active_border_color: str = "#00FF00"
    active_fill_color: str = "#00FF00"
    inactive_border_color: str = "#333333"
    inactive_fill_color: str = "#111111"
    border_width: int = 2
    # Text-specific
    font_size: int = 12
    font_family: str = "Arial"

    def to_dict(self) -> dict:
        return {
            "active_border_color": self.active_border_color,
            "active_fill_color": self.active_fill_color,
            "inactive_border_color": self.inactive_border_color,
            "inactive_fill_color": self.inactive_fill_color,
            "border_width": self.border_width,
            "font_size": self.font_size,
            "font_family": self.font_family
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'ObjectStyle':
        return cls(
            active_border_color=data.get("active_border_color", "#00FF00"),
            active_fill_color=data.get("active_fill_color", "#00FF00"),
            inactive_border_color=data.get("inactive_border_color", "#333333"),
            inactive_fill_color=data.get("inactive_fill_color", "#111111"),
            border_width=data.get("border_width", 2),
            font_size=data.get("font_size", 12),
            font_family=data.get("font_family", "Arial")
        )


@dataclass
class DisplayObject:
    """Base class for all display objects"""
    id: str
    obj_type: ObjectType
    layer: str  # "background" or "design"
    geometry: Dict[str, Any]
    style: ObjectStyle = field(default_factory=ObjectStyle)
    binding: DataBinding = field(default_factory=DataBinding)
    # For text objects
    text: str = ""
    # Annotation for documentation (not rendered)
    annotation: str = ""

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "type": self.obj_type.value,
            "layer": self.layer,
            "geometry": self.geometry,
            "style": self.style.to_dict(),
            "binding": self.binding.to_dict()
        }
        if self.obj_type == ObjectType.TEXT:
            result["text"] = self.text
        if self.annotation:
            result["annotation"] = self.annotation
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'DisplayObject':
        return cls(
            id=data.get("id", ""),
            obj_type=ObjectType(data.get("type", "rectangle")),
            layer=data.get("layer", "design"),
            geometry=data.get("geometry", {}),
            style=ObjectStyle.from_dict(data.get("style", {})),
            binding=DataBinding.from_dict(data.get("binding", {})),
            text=data.get("text", ""),
            annotation=data.get("annotation", "")
        )

    def get_bounding_rect(self) -> Tuple[float, float, float, float]:
        """Get bounding rectangle (x, y, width, height)"""
        geom = self.geometry
        if self.obj_type == ObjectType.RECTANGLE:
            return (geom.get("x", 0), geom.get("y", 0),
                    geom.get("width", 50), geom.get("height", 30))
        elif self.obj_type == ObjectType.CIRCLE:
            r = geom.get("radius", 25)
            cx, cy = geom.get("center_x", 0), geom.get("center_y", 0)
            return (cx - r, cy - r, r * 2, r * 2)
        elif self.obj_type == ObjectType.ELLIPSE:
            rx = geom.get("radius_x", 30)
            ry = geom.get("radius_y", 20)
            cx, cy = geom.get("center_x", 0), geom.get("center_y", 0)
            return (cx - rx, cy - ry, rx * 2, ry * 2)
        elif self.obj_type == ObjectType.POLYGON:
            points = geom.get("points", [[0, 0]])
            if not points:
                return (0, 0, 0, 0)
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)
            return (min_x, min_y, max_x - min_x, max_y - min_y)
        elif self.obj_type == ObjectType.TEXT:
            # Approximate text bounds
            return (geom.get("x", 0), geom.get("y", 0), 100, 20)
        return (0, 0, 50, 30)


@dataclass
class LayerConfig:
    """Configuration for a single layer"""
    visible: bool = True
    locked: bool = False
    opacity: float = 1.0
    image_path: Optional[str] = None  # For reference layer

    def to_dict(self) -> dict:
        result = {
            "visible": self.visible,
            "locked": self.locked,
            "opacity": self.opacity
        }
        if self.image_path is not None:
            result["image_path"] = self.image_path
        return result

    @classmethod
    def from_dict(cls, data: dict) -> 'LayerConfig':
        return cls(
            visible=data.get("visible", True),
            locked=data.get("locked", False),
            opacity=data.get("opacity", 1.0),
            image_path=data.get("image_path")
        )


@dataclass
class CanvasConfig:
    """Canvas configuration"""
    width: int = 800
    height: int = 480
    background_color: str = "#000000"

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "height": self.height,
            "background_color": self.background_color
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CanvasConfig':
        return cls(
            width=data.get("width", 800),
            height=data.get("height", 480),
            background_color=data.get("background_color", "#000000")
        )


@dataclass
class PanelDesign:
    """Complete panel design document"""
    version: str = SCHEMA_VERSION
    canvas: CanvasConfig = field(default_factory=CanvasConfig)
    layers: Dict[str, LayerConfig] = field(default_factory=lambda: {
        "reference": LayerConfig(visible=False, locked=True, opacity=0.5),
        "background": LayerConfig(visible=True, locked=False, opacity=1.0),
        "design": LayerConfig(visible=True, locked=False, opacity=1.0)
    })
    objects: List[DisplayObject] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "canvas": self.canvas.to_dict(),
            "layers": {k: v.to_dict() for k, v in self.layers.items()},
            "objects": [obj.to_dict() for obj in self.objects]
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'PanelDesign':
        version = data.get("version", SCHEMA_VERSION)
        canvas = CanvasConfig.from_dict(data.get("canvas", {}))

        layers_data = data.get("layers", {})
        layers = {
            "reference": LayerConfig.from_dict(layers_data.get("reference", {"visible": False, "locked": True, "opacity": 0.5})),
            "background": LayerConfig.from_dict(layers_data.get("background", {})),
            "design": LayerConfig.from_dict(layers_data.get("design", {}))
        }

        objects = [DisplayObject.from_dict(obj) for obj in data.get("objects", [])]

        return cls(
            version=version,
            canvas=canvas,
            layers=layers,
            objects=objects
        )

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string"""
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> 'PanelDesign':
        """Deserialize from JSON string"""
        data = json.loads(json_str)
        return cls.from_dict(data)

    def get_objects_by_layer(self, layer: str) -> List[DisplayObject]:
        """Get all objects in a specific layer"""
        return [obj for obj in self.objects if obj.layer == layer]

    def add_object(self, obj: DisplayObject):
        """Add an object to the design"""
        self.objects.append(obj)

    def remove_object(self, obj_id: str):
        """Remove an object by ID"""
        self.objects = [obj for obj in self.objects if obj.id != obj_id]

    def get_object(self, obj_id: str) -> Optional[DisplayObject]:
        """Get an object by ID"""
        for obj in self.objects:
            if obj.id == obj_id:
                return obj
        return None

    def generate_object_id(self) -> str:
        """Generate a unique object ID"""
        existing_ids = {obj.id for obj in self.objects}
        counter = 1
        while True:
            new_id = f"obj_{counter:03d}"
            if new_id not in existing_ids:
                return new_id
            counter += 1
