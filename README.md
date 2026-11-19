# Decahedron 3D Scene

This project includes a CustomTkinter camera UI and a Pyglet-based 3D scene.

## UI

Install dependencies and run the UI from the repository root:

```text
python -m pip install -r requirements.txt
python ui/app.py
```

Start the camera, then choose **Open 3D scene** to launch the 3D viewer.

## 3D scene

Run the viewer on its own with:

```text
python -m src.pyglet_viewer
```

The viewer draws a reference grid and supports creating cubes, spheres, and pyramids. You can orbit the camera and zoom.

**Object manipulation is not implemented.** The viewer does not currently select, move, rotate, scale, or delete objects, and it has no physics simulation.

| Control | Action |
|---|---|
| `1` | Create a cube |
| `2` | Create a sphere |
| `3` | Create a pyramid |
| Left mouse drag | Orbit the camera |
| Mouse wheel | Zoom |

## Tests

Run the shape and viewer tests with:

```text
python -m unittest discover -s tests -v
```
