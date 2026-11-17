from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

Point = Tuple[float, float]
Vector3 = Tuple[float, float, float]


class GestureType(str, Enum):
    CREATE_SHAPE = "CREATE_SHAPE"
    NONE = "NONE"


class ShapeType(str, Enum):
    CUBE = "CUBE"
    SPHERE = "SPHERE"
    CYLINDER = "CYLINDER"
    PYRAMID = "PYRAMID"


# Groupmate labels from data_collection/collect_gestures.py
LABEL_TO_GESTURE = {
    "none": GestureType.NONE,
}


@dataclass
class GestureEvent:
    type: GestureType
    confidence: float
    delta: Vector3 = (0.0, 0.0, 0.0)
    cursor_pos: Optional[Point] = None
    shape_type: Optional[ShapeType] = None
    label: str = "none"
