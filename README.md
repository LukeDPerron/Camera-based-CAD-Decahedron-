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

- **Updated** is the default. Pinch once to grab, then open your fingers and move or turn your hand. The shape follows your index finger until you pinch again to drop it. Depth is estimated from apparent palm size.
- **Legacy** keeps the selection when you release the pinch. Pinch again to deselect. Extend your thumb from a fist and move left or right for X. Point your index finger up and move vertically for Y. With an open palm, sweep up to move the shape farther away or down to bring it closer on Z.

Hold up only your middle finger for about a second to close the app.

Twist your hand clockwise or counterclockwise to rotate around the grab point. In Updated mode, point your index finger up and turn your wrist for side-to-side rotation. Tip your whole hand so your fingertips lean toward or away from the lens to roll the shape forward or backward. In Legacy mode, hold the pinch while twisting.

Pinch with your pinky extended to add or remove the shape you are pointing at. In Updated mode, keep your pinky up while building a selection, then lower it to move the group. Multiple selected shapes move together and orbit their shared center when rotated. In Legacy mode, twisting an open palm also rotates the selection. To delete the selection in either mode, show an open palm and then make a fist within one second.

Show both hands and bounce them in opposite directions, one up while the other goes down. After two reversals, **6** and **7** follow your hands while the motion continues. Touch your thumb, middle finger, and ring finger together while extending your index finger and pinky to show the cat. Deleting a shape plays a fading explosion at its position.

Turn on **Snap to faces** and move a cube or pyramid close to another one with two faces facing each other. The moving face aligns and resizes to the target face, then the app releases the selection. A triangle and a square match in width and height while keeping their outlines. Pinch the object again to move it. Turn on **Track one hand** to restart tracking with a single-hand limit.

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
