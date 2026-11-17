# Decahedron Shape and Gesture Logic

This branch contains the non-UI logic for creating and editing 3D shapes.

## Backend

- `src/scene_objects.py` defines cube, sphere, and cylinder objects and their transforms.
- `src/shape_factory.py` creates validated shapes with unique names.
- `src/scene.py` stores objects and manages selection and movement.
- `src/gesture_event.py` defines gesture and shape event types.
- `src/gesture_recognizer.py` maps hand landmarks to gesture events.
- `src/command_handler.py` applies create, select, and axis-movement events to a scene.

The existing gesture labels map to axis translation and cursor selection:

| Label | Action |
|---|---|
| `thumb_x` | Move the selected shape on X |
| `index_y` | Move the selected shape on Y |
| `palm_z` | Move the selected shape on Z |
| `cursor` | Select the shape nearest the cursor |
| `none` | No action |

Shape creation is available through a `CREATE_SHAPE` event. The UI can choose a shape type and provide its position; no create gesture is assumed.

## Tests

Run the backend tests with:

```text
python -m unittest discover -s tests -v
```
