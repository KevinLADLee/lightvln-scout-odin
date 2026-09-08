import base64

import cv2
import numpy as np
import pytest

from lightvln_scout.image_processing import ImagePreprocessor, ScoutFrameEncoder
from vln_client.vln_client import CameraFrame


def test_odin_crop_preserves_geometry_before_downsampling():
    processing = ImagePreprocessor()
    assert processing.crop_box(1600, 1296) == (2, 192, 1596, 912)
    # The scale on each axis is exactly equal; no horizontal stretching.
    assert 448 / 1596 == 256 / 912


@pytest.mark.parametrize("width,height", [(640, 480), (1920, 1080), (480, 640), (448, 256)])
def test_crop_is_centered_and_has_exact_target_ratio(width, height):
    x, y, crop_w, crop_h = ImagePreprocessor().crop_box(width, height)
    assert crop_w * 256 == crop_h * 448
    assert abs(x - (width - x - crop_w)) <= 1
    assert abs(y - (height - y - crop_h)) <= 1
    assert 0 <= x < x + crop_w <= width
    assert 0 <= y < y + crop_h <= height


def test_crop_removes_borders_without_distorting_square():
    image = np.zeros((160, 140, 3), dtype=np.uint8)
    image[:40, :, 2] = 255
    image[120:, :, 0] = 255
    image[60:100, 50:90] = 255
    result = ImagePreprocessor(70, 40).prepare(image)
    ys, xs = np.nonzero(result[:, :, 0])
    assert result.shape == (40, 70, 3)
    assert xs.max() - xs.min() == ys.max() - ys.min() == 19
    assert np.all(result[0] == 0) and np.all(result[-1] == 0)


def test_lossless_compressed_and_raw_input_produce_identical_request_jpeg():
    rng = np.random.default_rng(4)
    bgr = rng.integers(0, 256, (160, 140, 3), dtype=np.uint8)
    success, png = cv2.imencode(".png", bgr)
    assert success
    raw = CameraFrame(1, 2, 140, 160, 420, bgr[:, :, ::-1].copy().tobytes())
    compressed = CameraFrame(1, 2, 0, 0, 0, b"", jpeg=png.tobytes())
    processing = ImagePreprocessor()
    sent_jpeg = base64.b64decode(ScoutFrameEncoder(processing)(raw))
    assert sent_jpeg == base64.b64decode(ScoutFrameEncoder(processing)(compressed))
    # The idle webpage uses this same encoder, rather than another resize path.
    assert sent_jpeg == processing.encode(bgr)


def test_legacy_stretch_is_an_explicit_option():
    assert ImagePreprocessor(fit="stretch").crop_box(1600, 1296) == (0, 0, 1600, 1296)


@pytest.mark.parametrize(
    "options", [{"width": 0}, {"height": -1}, {"fit": "unknown"}, {"jpeg_quality": 101}]
)
def test_invalid_preprocessing_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        ImagePreprocessor(**options)
