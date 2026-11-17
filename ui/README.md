# Camera Canvas

For the original project brief, implementation history, validation limits, and
next-session context, read [PROJECT_HANDOFF.md](PROJECT_HANDOFF.md).

A basic CustomTkinter desktop app where your **live webcam feed is the canvas**.
It tracks one hand, overlays its 21 landmarks, and follows your index fingertip
with a cursor. Pinching turns the cursor amber. There are no CAD tools yet.

The AI tracker uses the same MediaPipe Tasks API, model, and confidence settings
as `../tmp/collect_gestures.py`. That script collects labeled coordinates; it
does not include a trained custom gesture classifier. This prototype adds simple
geometric previews for **pinch, point, open palm, and fist**, with a short stability
filter. These are approximate pose indicators; the collector's `thumb_x`,
`index_y`, `palm_z`, and `cursor` classes are not trained or connected yet.

## Setup

Use **64-bit Python** with Tkinter. Supported configurations:

| Platform | Python versions |
| --- | --- |
| Apple Silicon Mac, native arm64 Python, macOS 12+ | 3.10–3.14 |
| Intel Mac, or Python running under Rosetta, macOS 12+ | 3.10–3.12 |
| Windows x64 | 3.10–3.14 |

The workspace root [`requirements.txt`](../requirements.txt) contains the UI
dependencies in labeled sections. It automatically selects the older MediaPipe/NumPy stack for
Python 3.10–3.12, and the newer MediaPipe Tasks / NumPy 2 stack for Python
3.13–3.14. The newer MediaPipe wheels support Apple Silicon but omit Intel Macs.
Windows ARM is not a native target for this dependency set.

From the repository folder:

### macOS

Use the Python installer from [python.org](https://www.python.org/downloads/),
which includes Tkinter. Then:

```bash
cd ui
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r ../requirements.txt
python app.py
```

On an **Apple Silicon Mac**, `python3.13` or `python3.14` can be used instead of
`python3.12`. Run `python -c "import platform; print(platform.machine())"` in your
environment to confirm it prints `arm64`. Intel Macs should keep using 3.12.

### Updating an existing environment after the original install error

First update the root `requirements.txt` and your local `ui/` app files. In the
activated environment, from inside `ui/`, run:

```bash
python -m pip install --upgrade pip
python -m pip install -r ../requirements.txt
python app.py
```

Use `python` for both installing and launching so both commands use the same
virtual environment. If your environment has packages from unrelated projects,
create a fresh environment first. Do not reuse an Intel/Rosetta environment with
native Apple Silicon Python.

### Windows (PowerShell)

Install Python 3.12 from [python.org](https://www.python.org/downloads/windows/)
with the **Tcl/Tk and IDLE** component enabled. Then:

```powershell
cd ui
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r ..\requirements.txt
.\.venv\Scripts\python.exe app.py
```

Calling the virtual environment's Python directly avoids PowerShell activation
policy issues. Use a new `ui/.venv`; the repository's existing root `.venv` may
contain paths from another computer.

## Use

- The default camera starts automatically. Allow the operating system's camera
  permission prompt. Raise one hand with your whole palm in view.
- Use the **sidebar icon** at the top of the sidebar to collapse the controls and
  expand the camera canvas. Click it again on the collapsed rail to restore your
  controls with settings preserved.
- Toggle **Mirror camera**, **Hand landmarks**, and **Fingertip cursor** independently.
- The side panel shows handedness, pose, processed FPS, and normalized fingertip
  coordinates (top left is `0 / 0`, bottom right is `1 / 1`).
- Hover your index fingertip over **Cube**, **Sphere**, or **Pyramid** at the
  bottom of the video for **1 second**. The progress bar fills as you hover.
  Selection briefly shows plain text above the buttons with the shape and action
  count, which disappears after two seconds;
  move off a button before selecting it again. Losing tracking resets the timer.
  These are placeholder actions; geometry creation can be added in
  `CameraCanvasApp._select_shape()` in `app.py`.
- Pick a device by name in the **Camera** dropdown. Changing the selection during
  a live preview stops the old camera and starts the selected one automatically.
- Press **Stop camera** to release the device. While stopped, **Refresh cameras**
  updates the dropdown after connecting or disconnecting a camera. The selected
  device is kept when it is still present, even if its camera index changes.
- Camera discovery lists devices reported by AVFoundation on macOS and
  DirectShow on Windows, including supported USB and virtual cameras. It does
  not open every camera to probe a fixed range of numbers. Camera permission and
  another app using a device can still prevent a listed camera from opening.
- Resize the window freely; the video keeps its aspect ratio without cropping.
- Close the window or press **Escape** to exit.

The app reuses `../tmp/hand_landmarker.task` if present. Otherwise it downloads
the official model once (about 8 MB) into `ui/models/`. Subsequent runs work
offline. You can also place `hand_landmarker.task` there manually. Inference runs
locally; no camera frames, images, or landmark data are uploaded or saved.

## Troubleshooting

- **macOS:** System Settings → Privacy & Security → Camera. Allow the terminal
  or IDE running Python; fully quit and reopen it after changing permissions.
  For model download certificate errors with python.org Python, run the bundled
  **Install Certificates.command** in the Python application folder.
- **Windows:** Settings → Privacy & security → Camera. Enable camera access
  and **Let desktop apps access your camera**. Close Teams, Zoom, or other apps
  holding the camera. If imports report a DLL failure, install Microsoft's
  Visual C++ 2015–2022 Redistributable (x64).
- **No matching MediaPipe distribution:** check `python --version` and
  `python -c "import platform; print(platform.machine())"` against the table above.
  Update the root `requirements.txt` if it still unconditionally pins `mediapipe==0.10.18`.
  Intel/Rosetta Python 3.13+ needs a new Python 3.12 environment, or native arm64
  Python on Apple Silicon. Do not install `opencv-python` alongside this project's
  `opencv-contrib-python`; both provide the same `cv2` module.
- **Missing Tkinter:** `python -m tkinter` should open a test window. Reinstall
  Python with Tk support if it does not.
- **Camera list unavailable:** install the updated root `requirements.txt` in your
  activated environment. Discovery uses `cv2-enumerate-cameras` and, on macOS,
  the PyObjC AVFoundation bridge. When no cameras are found, check OS camera
  permissions, connect a camera, then press **Refresh cameras**.

## Implementation

- `app.py`: CustomTkinter controls and a Tk canvas for aspect-correct live video.
- `tracking.py`: background camera capture, MediaPipe inference, and overlays;
  native AVFoundation on macOS, DirectShow on Windows, default-backend fallback.
- `dwell.py`: one-second hover selection and reset logic, independent of Tk.
- `gestures.py`: palm-relative pose rules, separate from the AI tracker so a
  trained classifier can be added later.
- `cameras.py`: native camera enumeration, device names, and device IDs to resolve
  the selected device again before opening it after a hot-plug.

Only the latest processed frame is passed to Tk, so frames cannot accumulate
into a delayed video queue. Tk calls stay on the main thread. Camera and tracker
resources are released in the worker's `finally` block on normal stop or error.

## Checks

From this folder:

```bash
python -m unittest discover -s tests -v
```

By default, hardware-independent tests run. Set the environment variable
`CAMERA_UI_TEST_GUI=1` to also run the real Tk window tests; these require a
desktop display (or Xvfb). Tests use simulated camera input.

Real webcam capture and OS permission prompts need a local macOS / Windows test;
a headless development container cannot validate those hardware interactions.

References: [LeapShape](https://github.com/leapmotion/LeapShape) (interaction
inspiration), [MediaPipe Hand Landmarker](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python),
[MediaPipe 0.10.18 platform wheels](https://pypi.org/project/mediapipe/0.10.18/#files),
[MediaPipe 0.10.35 platform wheels](https://pypi.org/project/mediapipe/0.10.35/#files).
Camera discovery: [cv2-enumerate-cameras](https://github.com/lukehugh/cv2_enumerate_cameras).
