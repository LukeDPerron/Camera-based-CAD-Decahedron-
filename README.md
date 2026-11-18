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

Click a Cube, Sphere, or Pyramid icon at the bottom of the live camera feed, or hold your index fingertip over it for one second. Shapes appear directly over the video. Their positions are relative to the camera view, so they stay in the same part of the frame when you move the camera.

Aim at a shape and pinch to select it. The selected shape gets an amber outline.

- **Updated** is the default. Hold the pinch and move your hand across the image or toward and away from the lens. Release to drop the shape. Depth is estimated from apparent palm size, so keeping your hand at a steady angle helps.
- **Legacy** keeps the selection when you release the pinch. Pinch again to deselect. Extend your thumb from a fist and move left or right for X. Point your index finger up and move vertically for Y. With an open palm, sweep up to move the shape farther away or down to bring it closer on Z.

Hold up only your middle finger for about a second to close the app.

In either mode, twist your pinched hand clockwise or counterclockwise to rotate the shape around the grab point.

## 3D scene

Run the standalone Pyglet scene demo with:

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
