from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

Point = Tuple[float, float]
Vector3 = Tuple[float, float, float]


class GestureType(str, Enum):
    CREATE_SHAPE = "CREATE_SHAPE"
    CURSOR_SELECT = "CURSOR_SELECT"
    X_AXIS = "X_AXIS"
    Y_AXIS = "Y_AXIS"
    Z_AXIS = "Z_AXIS"
    NONE = "NONE"


class ShapeType(str, Enum):
    CUBE = "CUBE"
    SPHERE = "SPHERE"
    CYLINDER = "CYLINDER"
    PYRAMID = "PYRAMID"


# Groupmate labels from data_collection/collect_gestures.py
LABEL_TO_GESTURE = {
    "thumb_x": GestureType.X_AXIS,
    "index_y": GestureType.Y_AXIS,
    "palm_z": GestureType.Z_AXIS,
    "cursor": GestureType.CURSOR_SELECT,
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
