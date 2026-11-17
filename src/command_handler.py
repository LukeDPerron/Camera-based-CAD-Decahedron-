from .gesture_event import GestureEvent, GestureType, ShapeType
from .scene import Scene
from .shape_factory import ShapeFactory


class CommandHandler:
    def __init__(self, scene: Scene):
        self.scene = scene
        self.next_shape = ShapeType.CUBE

    def set_next_shape(self, shape_type: ShapeType) -> None:
        self.next_shape = shape_type

    def handle(self, event: GestureEvent, spawn_position=None, projected_centers=None) -> None:
        if event.type is GestureType.NONE:
            return

        if event.type is GestureType.CREATE_SHAPE:
            shape = event.shape_type or self.next_shape
            obj = ShapeFactory.create(shape, position=spawn_position)
            self.scene.add(obj)
            return
