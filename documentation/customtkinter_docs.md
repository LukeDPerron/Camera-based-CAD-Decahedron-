# Camera Canvas UI

Camera Canvas is a CustomTkinter desktop app that uses live webcam video as a 2D workspace. It tracks one hand, draws its landmarks, and uses your index fingertip to aim at controls on the video. Camera processing runs locally. The app does not save or upload frames or landmark data.

## Get started

Use 64-bit Python with Tkinter and a desktop display. Python 3.12 is the common choice across the project's Mac and Windows targets.

| Platform | Python versions targeted by the project |
| --- | --- |
| Apple Silicon Mac with native arm64 Python, macOS 12+ | 3.10–3.14 |
| Intel Mac or Python running under Rosetta, macOS 12+ | 3.10–3.12 |
| Windows x64 | 3.10–3.14 |

Run the commands from the repository root. The root [requirements.txt](../requirements.txt) selects the appropriate MediaPipe, OpenCV, and NumPy versions. Keep UI dependencies there and local environments under `ui/.venv/`. Create the environment on your machine so its interpreter paths match your installation.

**macOS**

```bash
python3.12 -m venv ui/.venv
source ui/.venv/bin/activate
python -m pip install -r requirements.txt
python ui/app.py
```

**Windows PowerShell**

```powershell
py -3.12 -m venv ui/.venv
.\ui\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\ui\.venv\Scripts\python.exe ui\app.py
```

The app checks for the MediaPipe model in `ui/models/hand_landmarker.task` first and then in `tmp/hand_landmarker.task`. If both are missing, it downloads the model into `ui/models/` on the first camera start. You can place the model there manually for an offline setup. Both model locations are ignored by Git.

## Try the controls

1. Allow camera access if your OS prompts for it. The app scans for cameras at startup and opens the first one it finds.
2. Hold one hand in view. The sidebar shows handedness, pose, processed FPS, and normalized fingertip coordinates. The frame's top-left is `0, 0` and its bottom-right is `1, 1`. Pinching turns the cursor drawn on the video amber.
3. Hover your fingertip over **Cube**, **Sphere**, or **Pyramid** for one second. The progress ring fills and a confirmation appears for two seconds. Move off the icon to select it again. Each selection increments a counter and displays a message. Geometry creation would start at the selection hook described below.
4. Use **Camera** to switch devices during a preview. Use **Stop camera**, then **Refresh cameras**, after plugging in or unplugging a device. Use **Start camera** to reopen the selected device.

The sidebar icon collapses or restores the controls while keeping their settings. **Mirror camera**, **Hand landmarks**, and **Fingertip cursor** can be toggled independently. Hiding the cursor leaves fingertip selection active. Resizing fits the full video inside the canvas. Press **Escape** or close the window to exit.

## Find the code you need

The entry point is [ui/app.py](../ui/app.py). `CameraCanvasApp` is the CustomTkinter window, with a regular Tk canvas embedded in the layout for the video and toolbar.

| To change | Start here |
| --- | --- |
| Window layout, colors, sidebar, or controls | [app.py](../ui/app.py) · `_build_header()`, `_build_workspace()`, `_toggle_sidebar()`, and the color constants near the top |
| Video fitting, fingertip placement, or toolbar icons | [app.py](../ui/app.py) · `_render_image()` fits and centers the video. `_shape_layout()` maps the normalized tip to that fitted rectangle and returns icon bounds shared by drawing and hit testing. `_draw_shape_toolbar()` draws the icons and progress ring. |
| What happens when a shape is selected | [app.py](../ui/app.py) · `_update_shape_hover()` detects the target and calls `_select_shape(shape)` when the timer completes. Put selection behavior in `_select_shape()` so frame updates can continue to run independently. |
| Hover timing and reselect behavior | [dwell.py](../ui/dwell.py) · `DwellSelector.update(target, now)` accepts a target or `None` and monotonic time in seconds. It exposes `progress` from 0 to 1 and returns the selected target once per hover. The defaults are a 1-second dwell and a 0.35-second maximum gap between updates. It can be used without a camera or Tk. |
| Camera discovery or switching | [cameras.py](../ui/cameras.py) · `discover_cameras()` lists named devices using AVFoundation on macOS, DirectShow on Windows, and V4L2 on Linux. `resolve_camera()` finds the current index for the selected device ID and backend. In [app.py](../ui/app.py), `refresh_cameras()`, `_select_camera()`, and `start_camera()` manage the dropdown and worker lifecycle. |
| Capture, MediaPipe settings, or frame overlays | [tracking.py](../ui/tracking.py) · `CameraWorker.run()` owns capture and inference and releases both resources on exit. `open_camera()` opens a device, `ensure_model()` locates or downloads the model, and `draw_overlay()` draws landmarks and the fingertip into the RGB frame. |
| Pose labels and thresholds | [gestures.py](../ui/gestures.py) · `classify_pose()` uses the hand's world landmarks to recognize Pinch, Palm, Fist, and three index-only poses. A finger pointing upward shows **Point up**, a finger aimed at the lens shows **Cursor**, and other index-only directions show **Point**. The worker requires three consecutive matching frames before changing the displayed pose. These rules are geometric. The original gesture collector is a separate source of labeled data. |

Camera discovery and capture run on background threads. `CameraWorker` publishes a `Frame` with an RGB image, hand and pose labels, a normalized fingertip or `None`, and FPS. Its frame queue holds one item so the display can keep up with the latest frame. The Tk main thread uses `_poll()` to read frames and events, then `_display_frame()` updates the canvas and metrics. Keep widget updates on that thread. When switching cameras, the app waits for the previous worker to exit before opening the next one.

## Run checks

From the repository root, use the Python interpreter where you installed the requirements.

```bash
python -m unittest discover -s ui/tests -v
```

The tests cover camera discovery and identity, tracking and worker cleanup, dwell timing, and window behavior. The real Tk tests require a display and opt in through `CAMERA_UI_TEST_GUI=1`. On macOS, run `CAMERA_UI_TEST_GUI=1 python -m unittest discover -s ui/tests -v`. In PowerShell, set `$env:CAMERA_UI_TEST_GUI = "1"` before running the suite with the environment's Python.

For a hardware check, start the app with a real camera, try the mirror and overlay toggles, and dwell on a shape icon. Verify moving away or losing tracking clears progress. With a second camera, check switching and stop/refresh/start after disconnecting and reconnecting it. Close the app and confirm the camera is released. The automated tests use simulated camera input.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| Tkinter import fails or the window does not open | Run `python -m tkinter` with the same interpreter. It should open a test window on a desktop. Ensure your Python installation includes Tcl/Tk. |
| Pip cannot find a MediaPipe distribution | Check `python --version` and `python -c "import platform; print(platform.machine())"` with the environment's Python. Intel and Rosetta setups need Python 3.10–3.12. |
| No cameras appear or a camera will not open | Allow the terminal or IDE under **Privacy & Security → Camera** on macOS, or enable desktop app camera access under **Privacy & security → Camera** on Windows. Close other apps using the camera, then refresh and try again. |
| Camera discovery reports missing dependencies | Reinstall from the root requirements file with the same Python used to launch the app. This installs the camera enumerator and the AVFoundation bridge on macOS. |
| The hand model cannot download | Check connectivity or place `hand_landmarker.task` in `ui/models/`, then start the camera again. |

See the [project handoff](PROJECT_HANDOFF.md) for the original brief and implementation history, and the [earlier UI README](README.md) for additional installation notes.
