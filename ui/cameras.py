"""Named camera discovery without opening devices or probing arbitrary indices."""

from dataclasses import dataclass
import platform

import cv2


@dataclass(frozen=True)
class CameraDevice:
    index: int
    name: str
    backend: int
    device_id: str

    @property
    def label(self):
        # Distinguish two devices with the same manufacturer/model name.
        return f"{self.name} · {self.index + 1}"


def discover_cameras() -> list[CameraDevice]:
    try:
        from cv2_enumerate_cameras import enumerate_cameras
    except ImportError as exc:
        raise RuntimeError(
            "Camera discovery needs the updated dependencies. "
            "From the workspace root, run python -m pip install -r requirements.txt, "
            "then restart the app."
        ) from exc
    backend = {
        "Darwin": cv2.CAP_AVFOUNDATION,
        "Windows": cv2.CAP_DSHOW,
        "Linux": cv2.CAP_V4L2,
    }.get(platform.system())
    if backend is None:
        raise RuntimeError("Camera discovery is supported on macOS, Windows, and Linux.")
    cameras = []
    seen = set()
    # Use one native backend so the same camera is not listed multiple times
    # through different APIs. Indices belong to that backend, not list positions.
    for info in enumerate_cameras(backend):
        identity = str(info.path or f"{backend}:{info.index}")
        if identity in seen:
            continue
        seen.add(identity)
        cameras.append(CameraDevice(info.index, str(info.name or "Camera"), backend, identity))
    return cameras


def resolve_camera(camera: CameraDevice) -> CameraDevice:
    """Recheck the device ID before opening; unplugging can renumber indices."""
    for current in discover_cameras():
        if current.device_id == camera.device_id and current.backend == camera.backend:
            return current
    raise RuntimeError(
        f"{camera.name} is no longer connected. "
        "Press Refresh cameras and select an available camera."
    )
