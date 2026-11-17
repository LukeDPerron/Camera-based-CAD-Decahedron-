# Decahedron Shape and Gesture Logic

This branch combines the CustomTkinter UI with the non-UI logic for creating and editing 3D shapes.

## Getting started

You need Python 3.10–3.14 (Intel Macs: 3.10–3.12), a webcam, and git.

1. Get the branch:

   ```text
   git clone https://github.com/LukeDPerron/Camera-based-CAD-Decahedron-.git
   cd Camera-based-CAD-Decahedron-
   git checkout gestures-plus-models
   ```

   If you already have the repo, run `git fetch` and then `git checkout gestures-plus-models`.

2. Create a virtual environment and install the dependencies:

   ```text
   python -m venv .venv
   .venv\Scripts\activate          (Windows)
   source .venv/bin/activate       (macOS / Linux)
   pip install -r requirements.txt
   ```

3. Start the app from the repo root:

   ```text
   python ui/app.py
   ```

   The first run downloads the hand-tracking model (about 8 MB). The camera starts automatically; allow camera access if your system asks.

4. Click **Open 3D scene** in the sidebar, then use the gestures listed under "Hand gestures and the 3D scene" below.

## Backend

- `src/scene_objects.py` defines cube, sphere, and cylinder objects and their transforms.
- `src/shape_factory.py` creates validated shapes with unique names.
- `src/scene.py` stores objects and manages selection and movement.
- `src/gesture_event.py` defines gesture and shape event types.
- `src/gesture_recognizer.py` maps hand landmarks to gesture events.
- `src/command_handler.py` applies create events to a scene.

## Hand gestures and the 3D scene

The camera UI and the 3D viewer share one `Scene`. With the camera running and the 3D scene open:

| Gesture | Action |
|---|---|
| Hold the fingertip on a shape button for 1 s | Create that shape in the next free slot and select it |
| Pinch and drag | Move the selected shape left/right and up/down |
| Make a fist | Select the next shape (the selected shape is drawn brighter) |

The poses come from the basic rules in `ui/gestures.py`, not a trained classifier. Pinch-drag moves along world X/Y, so it matches the hand direction only while the viewer camera faces the scene head-on (its starting view).

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
| `Tab` | Select the next shape |
| Left mouse drag | Orbit the camera |
| Mouse wheel | Zoom |

## Tests

Run the backend tests with:

```text
python -m unittest discover -s tests -v
```
