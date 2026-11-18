import sys

import cv2
import numpy as np


class CameraManager:
    def __init__(self, camera_index: int = 0):
        self.capture = cv2.VideoCapture(camera_index)
        if not self.capture.isOpened():
            sys.exit("Could not open the webcam. Close other apps using the camera and try again.")

    def read_frame(self) -> np.ndarray | None:
        ok, frame = self.capture.read()
        if not ok:
            return None
        return cv2.flip(frame, 1)

    def release(self) -> None:
        self.capture.release()
