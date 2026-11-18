from .scene_objects import SceneObject


class Scene:
    def __init__(self):
        self.objects: list[SceneObject] = []

    def add(self, obj: SceneObject) -> None:
        self.objects.append(obj)
