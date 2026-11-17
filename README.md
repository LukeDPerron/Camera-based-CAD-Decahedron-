# Decahedron Shape and Gesture Logic

This branch combines the CustomTkinter UI with the non-UI logic for creating and editing 3D shapes.

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

## UI

The CustomTkinter UI is located in `ui/`. Run it with:

```text
python ui/app.py
```

The UI branch provides the camera canvas, tracking helpers, gesture dwell handling, and UI tests. The backend event contract remains independent of the UI implementation.

## 3D scene

Open the Pyglet 3D scene from the CustomTkinter UI with **Open 3D scene**, or run it directly:

```text
python -m src.pyglet_viewer
```

The 3D scene includes cubes, spheres, pyramids/triangles, and orbiting camera controls.

| Control | Action |
|---|---|
| `1` | Create a cube |
| `2` | Create a sphere |
| `3` | Create a pyramid |
| Left mouse drag | Orbit the camera |
| Mouse wheel | Zoom |

## Tests

Run the backend tests with:

```text
python -m unittest discover -s tests -v
```
