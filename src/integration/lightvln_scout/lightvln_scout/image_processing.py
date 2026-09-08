"""Shared image geometry for inference requests and idle camera previews."""

from __future__ import annotations

import base64
import math
import threading
from collections import OrderedDict
from dataclasses import dataclass

import cv2
import numpy as np

DEFAULT_WIDTH = 448
DEFAULT_HEIGHT = 256
DEFAULT_FIT = "center_crop"


@dataclass(frozen=True)
class ImagePreprocessor:
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fit: str = DEFAULT_FIT
    jpeg_quality: int = 80

    def __post_init__(self) -> None:
        for value in (self.width, self.height, self.jpeg_quality):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError("image dimensions and JPEG quality must be positive integers")
        if self.jpeg_quality > 100 or self.fit not in {"center_crop", "stretch"}:
            raise ValueError("invalid JPEG quality or image_fit")

    def crop_box(self, source_width: int, source_height: int) -> tuple[int, int, int, int]:
        """Largest centred integer ROI with the exact target aspect ratio: x,y,w,h."""
        if source_width <= 0 or source_height <= 0:
            raise ValueError("empty source image")
        if self.fit == "stretch":
            return 0, 0, source_width, source_height
        divisor = math.gcd(self.width, self.height)
        unit_w, unit_h = self.width // divisor, self.height // divisor
        scale = min(source_width // unit_w, source_height // unit_h)
        if scale < 1:
            raise ValueError("source image too small for the target aspect ratio")
        crop_w, crop_h = scale * unit_w, scale * unit_h
        return (source_width - crop_w) // 2, (source_height - crop_h) // 2, crop_w, crop_h

    def prepare(self, image: np.ndarray) -> np.ndarray:
        if image.ndim not in {2, 3} or image.dtype != np.uint8:
            raise ValueError("expected a uint8 image")
        height, width = image.shape[:2]
        x, y, crop_w, crop_h = self.crop_box(width, height)
        cropped = image[y:y + crop_h, x:x + crop_w]
        if (crop_w, crop_h) == (self.width, self.height):
            return np.ascontiguousarray(cropped)
        interpolation = (
            cv2.INTER_AREA if crop_w >= self.width and crop_h >= self.height
            else cv2.INTER_LINEAR
        )
        return cv2.resize(cropped, (self.width, self.height), interpolation=interpolation)

    def encode(self, image: np.ndarray) -> bytes:
        success, encoded = cv2.imencode(
            ".jpg", self.prepare(image), [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
        )
        if not success:
            raise RuntimeError("JPEG encoding failed")
        return encoded.tobytes()


class ScoutFrameEncoder:
    """Encode Scout input and retain a bounded cache of exact submitted JPEGs.

    The VLN worker calls this object; the ROS node consumes the matching JPEG
    only once the original client reports a completed inference.
    """

    def __init__(self, preprocessor: ImagePreprocessor) -> None:
        self.preprocessor = preprocessor
        self._lock = threading.Lock()
        self._frames: OrderedDict[int, bytes] = OrderedDict()

    def __call__(self, frame) -> str:
        if frame.jpeg:
            image = cv2.imdecode(np.frombuffer(frame.jpeg, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("invalid compressed camera frame")
        else:
            row_bytes = frame.width * 3
            if (frame.width <= 0 or frame.height <= 0 or frame.step < row_bytes
                    or len(frame.rgb) < frame.height * frame.step):
                raise ValueError("invalid RGB camera frame")
            rows = np.frombuffer(frame.rgb, dtype=np.uint8, count=frame.height * frame.step)
            rgb = rows.reshape(frame.height, frame.step)[:, :row_bytes]
            rgb = rgb.reshape(frame.height, frame.width, 3)
            image = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
        encoded = self.preprocessor.encode(image)
        with self._lock:
            self._frames[id(frame)] = encoded
            while len(self._frames) > 8:
                self._frames.popitem(last=False)
        return base64.b64encode(encoded).decode("ascii")

    def take_jpeg(self, frame) -> bytes | None:
        with self._lock:
            return self._frames.pop(id(frame), None)
