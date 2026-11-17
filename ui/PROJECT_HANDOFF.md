# Camera Canvas project handoff

Snapshot: **2026-11-17**. This file preserves the project context for a new Codex
session. Inspect the current files and Git status before editing: the user plans
to make changes between sessions, so this report may describe an earlier state.

## 1. What the user wants

The project is inspired by [LeapShape](https://github.com/leapmotion/LeapShape),
but the user's environment should come from the camera instead of an empty 3D
workspace. The intended direction is camera-based interaction using tracked hand
movements and gestures, with room to develop CAD-like interactions later.

The initial request was deliberately small: **a basic functioning CustomTkinter
desktop UI where the live camera feed is the canvas**. The user wants to see it
working and guide subsequent development. Do not assume they have requested a
complete CAD engine, full augmented reality, or a rewrite of LeapShape yet.

Explicit user requirements and preferences:

- Use **CustomTkinter** for the desktop UI.
- Support **MacBooks and Windows**.
- Use `/workspace/tmp/collect_gestures.py` as the hand-tracking reference.
- Keep the UI application and related implementation under **`ui/`**.
- Let the user **select available cameras from a dropdown**, rather than entering
  a camera number.
- Keep **one `requirements.txt` and one `.gitignore`, both at the workspace
  root**, with labeled sections for UI and any future project components.
  Do not recreate UI-specific copies.
- Tell the user when environment or file-access problems block work; they have
  offered to help fix them.
- Develop incrementally; the user will specify additional features after trying
  the basic implementation.

## 2. What has been implemented

### Camera canvas and UI

- Dark CustomTkinter window, titled Camera Canvas, with a large live video area
  and a compact scrollable control panel.
- The video area is a standard Tk canvas embedded in the CustomTkinter layout.
- Aspect ratio is preserved during window resizing, without cropping the feed.
- Camera discovery runs at startup; the first listed device starts automatically
  when discovery succeeds.
- A camera dropdown displays device names and a numeric suffix to distinguish
  cameras with identical names.
- Selecting a different camera during a preview stops the current worker and
  starts the newly selected camera after the old worker exits.
- **Stop camera / Start camera** controls release and reopen the device.
- **Refresh cameras** is available while stopped, to rescan after devices are
  connected or disconnected.
- Refresh preserves the selected device by its identity when it is still present.
- Missing cameras, discovery failures, camera permissions/opening failures, and
  lost frames produce visible messages and usable retry controls.
- Mirror view, hand landmarks, and fingertip cursor can be toggled independently.
- The panel shows handedness, pose, processed FPS, and normalized index-fingertip
  X/Y coordinates.
- Closing the window or pressing Escape exits the app.

### Hand tracking and pose indicators

- MediaPipe **Hand Landmarker Tasks API**, using CPU inference and VIDEO mode.
- Tracks **one hand**, with 21 landmarks and hand connections overlaid on video.
- Confidence settings match the reference script: detection 0.6, presence 0.6,
  tracking 0.5.
- A cursor follows the index fingertip. A pinch changes its appearance to amber.
- Basic geometric pose indicators: **Pinch, Point, Open palm, Fist**, or Tracking
  for an unclassified pose. A short three-frame stability filter reduces changes
  in the displayed pose name.
- These pose indicators use landmark geometry; **they are not a trained custom
  gesture classifier**.

### Threading and camera identity

- Camera capture and MediaPipe inference run in a background worker.
- Discovery runs on a separate background thread. Neither background thread
  directly updates Tk widgets.
- The frame queue holds only the latest processed frame to avoid accumulated
  display latency.
- Worker cleanup releases the camera and closes the landmarker in `finally`.
- Shutdown polls rather than blocking the Tk event loop; after a short timeout,
  a hung daemon camera thread cannot prevent process exit.
- Discovery uses `cv2-enumerate-cameras`: AVFoundation on macOS, DirectShow on
  Windows, and V4L2 on Linux. macOS also needs the PyObjC AVFoundation bridge.
- Discovery lists devices through a native backend instead of probing a fixed
  range of camera numbers. Listed devices can still fail to open if permission
  is denied, another app holds them, or they are disconnected.
- The UI passes a `CameraDevice` containing its native backend and persistent
  device ID. The worker resolves the ID again before opening, because hot-plug
  events can renumber camera indices.
- An explicitly selected device must stay on its enumerated backend. Falling
  back to a different backend with the same index could open the wrong camera.
  The older integer-only capture path retains a default-backend fallback.

### Model assets and local processing

- Prefer `ui/models/hand_landmarker.task` if present; otherwise reuse the existing
  `tmp/hand_landmarker.task` reference asset.
- If neither exists, download the official MediaPipe hand model once into
  `ui/models/`, using a temporary file and an atomic rename.
- The model download is approximately 8 MB. With a local model, inference does
  not need an internet connection.
- The UI currently does not save or upload video, photos, or landmark data.
  The separate reference collector does save landmark coordinates to CSV.

## 3. Original gesture reference and data

The user supplied these existing resources, which have been left untouched:

```text
tmp/collect_gestures.py
tmp/README.md
tmp/hand_landmarker.task
tmp/dataset/
```

`collect_gestures.py` mirrors the camera, tracks one hand with the MediaPipe Tasks
API, and records 21 world-coordinate landmarks plus labels/handedness to CSV.
It is a **data collector**, not a classifier-training or prediction script.

The collector's labels and documented meanings are:

| Label | Reference pose |
| --- | --- |
| `thumb_x` | Thumb pointing sideways, other fingers curled |
| `index_y` | Index finger pointing up, other fingers curled |
| `palm_z` | Open palm facing the camera |
| `cursor` | Index finger pointing toward the camera/screen |
| `none` | Other poses, relaxed hands, transitions, or movement |

These labels have **not** been trained or connected to the UI. Existing CSVs have
not been evaluated for coverage, label quality, or classification accuracy.
Do not describe the UI's geometric Point/Palm/etc. indicators as predictions
from this dataset.

## 4. Files and configuration

Paths below are relative to `/workspace` (or the repository root on another
machine):

```text
requirements.txt                 All dependencies; labeled UI sections
.gitignore                       All ignore rules; labeled UI section
ui/
  app.py                         Window, controls, scan/switch lifecycle, display
  cameras.py                     Named discovery and device-ID resolution
  tracking.py                    Camera worker, MediaPipe, frame overlays/model
  gestures.py                    Basic geometric pose rules
  README.md                      Setup, usage, troubleshooting, implementation
  PROJECT_HANDOFF.md              This report
  tests/
    test_cameras.py              Discovery, identity, backend selection checks
    test_tracking.py             Poses, camera failures, worker/queue cleanup
    test_ui.py                   Optional real Tk window and dropdown checks
```

The last requested change consolidated `ui/requirements.txt` and `ui/.gitignore`
into the root files and removed those UI copies. Redundant generated ignore
files in the existing virtual environments were also removed. At that point a
workspace-wide scan confirmed exactly one file of each name.

Root UI ignore rules cover `/ui/.venv/`, `/ui/models/`, `/ui/__pycache__/`, and
`/ui/.test-runtime/`. Existing root ignore rules already cover other virtual
environments and Python caches. `tmp/` is ignored, so the reference/data/model
files should not be assumed present in a fresh clone.

Virtual environments are local artifacts; existing ones may contain paths from
another computer. Do not commit or copy them as a deployment strategy. Python's
venv creation can generate a new nested `.gitignore`; keep project configuration
centralized as the user requested.

At report creation, the implementation files and root requirements file were
still **untracked**, and the root `.gitignore` had local modifications. No commit
or push was performed in this conversation. There were also pre-existing
workspace files such as `Dockerfile` and `cdx.sh`; do not overwrite unrelated
work or assume it was part of the UI implementation.

## 5. Python compatibility and the Mac installation issue

The first implementation pinned MediaPipe 0.10.18 and allowed only Python
3.10–3.12. The user tried installing on their MacBook and saw:

```text
ERROR: No matching distribution found for mediapipe==0.10.18
Please use Python 3.10, 3.11, or 3.12 with ui/requirements.txt.
```

The environment was using a newer Python than that initial stack supported. The
exact Python version was requested but was not supplied in the conversation.
The dependency file and application guard were updated to accommodate both
Python 3.13 and 3.14 on supported architectures.

Current target configurations:

| Platform | Python |
| --- | --- |
| Native Apple Silicon Mac, macOS 12+ | 3.10–3.14 |
| Intel Mac, or Python running under Rosetta, macOS 12+ | 3.10–3.12 |
| Windows x64 | 3.10–3.14 |

Python 3.12 remains the common setup across all three. Windows ARM is not a
native target of the current dependency set. Linux is used for development
checks, but newer MediaPipe releases do not supply Linux ARM wheels matching all
the Mac/Windows configurations above.

The root requirements file uses Python-version markers:

- Shared: CustomTkinter 5.2.2, camera enumeration 1.4.0, and AVFoundation bridge
  12.0 on macOS.
- Python 3.10–3.12: MediaPipe 0.10.18, OpenCV contrib 4.9.0.80, NumPy 1.26.4,
  Pillow >=10.4/<12, JAX/JAXlib 0.4.35, SciPy 1.14.1.
- Python 3.13–3.14: MediaPipe 0.10.35, OpenCV contrib 4.10.0.84, Pillow 12.0.0;
  NumPy 2.2.6 for 3.13 and 2.3.5 for 3.14. This newer MediaPipe stack does not
  require the legacy JAX dependency pins.

Do not upgrade the entire stack indiscriminately: Intel Mac wheel availability,
minimum macOS versions, Python versions, and NumPy compatibility influenced the
pins. Newer MediaPipe wheels omit Intel Macs. The app explains that limitation
when launched with Intel/Rosetta Python 3.13+.

## 6. Running the current app

Install Python with **Tkinter**. From the repository root, with a suitable
virtual environment already activated:

```bash
python -m pip install -r requirements.txt
python ui/app.py
```

If already inside `ui/`, use:

```bash
python -m pip install -r ../requirements.txt
python app.py
```

Use the same environment's `python` for installing and running. Full virtual
environment creation commands for macOS and Windows are in `ui/README.md`.

Common local issues:

- macOS: allow the terminal/IDE under Privacy & Security → Camera. Confirm
  `platform.machine()` prints `arm64` when using newer Python on Apple Silicon.
- Windows: allow camera access for desktop apps; close applications holding the
  webcam. Import DLL failures may require the Visual C++ x64 Redistributable.
- `python -m tkinter` should open a test window; missing Tk needs a Python
  installation with Tcl/Tk support.
- Do not install `opencv-python` alongside `opencv-contrib-python`; both provide
  the `cv2` module.
- A missing camera-enumeration dependency requires reinstalling from the **root**
  requirements file, not creating a new one under `ui/`.

## 7. What was verified, and what was not

Last application test run: **20 tests passed**, including the optional real Tk
tests run under Xvfb. Coverage included pose examples, camera errors, bounded
frame queues, monotonic timestamps, cleanup, named dropdown values, empty/error
scan states, selection preservation after renumbering, and waiting for the old
worker before switching devices.

Also completed:

- Loaded the supplied MediaPipe model and processed three blank CPU video frames
  successfully on the legacy dependency stack.
- Launched the actual UI on a virtual display and checked its no-camera state.
- Checked dependency resolution/binary-wheel availability for Intel macOS,
  Apple Silicon macOS, and Windows x64, including newer Python configurations
  and the newly added discovery dependencies.
- Inspected the newer MediaPipe wheel for the APIs the app uses. This was an API
  compatibility check, not a native macOS runtime test.
- After root-file consolidation, confirmed dependency selections were unchanged,
  ignore rules still matched UI artifacts, and only one requirements file and
  one ignore file remained. No application tests were rerun for that path-only
  configuration/documentation change.

**Not verified:** real camera capture, permissions prompts, named device mapping,
hot-plugging, and actual hand/gesture behavior on the user's MacBook or a Windows
machine. Mocked device tests and dependency resolution are not substitutes for
those hardware checks. The user has not yet confirmed a successful local run
after the installation fix and dropdown changes.

Run ordinary tests from the repository root:

```bash
python -m unittest discover -s ui/tests -v
```

For the real Tk tests on a machine with a display, also set
`CAMERA_UI_TEST_GUI=1` in the environment. Without that variable, GUI tests skip.

The development container originally lacked Tkinter, display libraries, and a
camera. An isolated temporary runtime was used for verification and moved out
of `ui/` afterward. It is not part of the app or a portable environment.

## 8. Remaining work and next-session priorities

There is **no outstanding explicitly requested feature** at this checkpoint.
The latest completed request was centralizing dependencies and ignore rules.
Continue from the user's next instructions rather than beginning a large CAD
implementation automatically.

The most useful immediate follow-up is local validation:

1. Confirm the user's actual Python version, architecture, and macOS version if
   installation or launch still fails. Check that their local copies include
   the current root requirements and all updated UI modules.
2. Verify a real camera opens and tracks one hand on macOS and Windows.
3. Verify named dropdown choices open the correct devices; try the built-in
   camera, USB devices, and virtual/Continuity cameras where available.
4. Verify switching, Stop/Start, Refresh, disconnect/reconnect, permission-denied
   handling, and clean shutdown on actual hardware.
5. Gather the user's next requested interaction or UI change.

Potential later work, **not yet specified/approved as the next task**:

- Train and evaluate a custom classifier for the collector's labeled poses,
  including the `none` class, then connect it to application actions.
- Decide what gestures should actually do in the camera workspace.
- Add drawing, object creation/manipulation, or CAD operations incrementally if
  the user requests them.
- If true 3D/AR placement is needed, choose an appropriate scene/rendering and
  calibration/depth approach with the user. The current canvas is a **2D video
  preview with overlays**, not a registered 3D environment. MediaPipe hand-world
  landmarks alone do not implement room reconstruction or world-anchored CAD.

There is currently no model training pipeline, CAD kernel, object editing,
gesture-driven drawing, 3D scene, export, application installer, or native app
packaging. The project remains a camera/hand-tracking UI foundation.

## 9. Notes for the next Codex agent

- Read this report, `ui/README.md`, current source, applicable agent instructions,
  and Git status before editing. Preserve user changes made after this snapshot.
- Keep application code in `ui/`; keep dependency and ignore configuration only
  in the root files, grouped under their UI sections.
- Maintain Mac/Windows compatibility and keep UI operations on the main thread.
- Keep the distinction between AI landmark detection, heuristic pose previews,
  and a future trained custom gesture classifier clear.
- The earlier container's sandbox runner could not start because unprivileged
  user namespaces were disabled. Shell work used permission-approved commands.
  This was an environment limitation, not an app bug; do not assume it applies
  to a new session. Tell the user if a similar limitation blocks progress.
- Do not assume temporary test runtimes or existing virtual environments are
  portable or still present. Recreate development environments when necessary.
