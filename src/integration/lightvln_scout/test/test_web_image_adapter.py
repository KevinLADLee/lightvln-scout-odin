import asyncio
import queue
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np
from sensor_msgs.msg import CompressedImage

from lightvln_scout import vln_web_adapter


class Logger:
    def info(self, message):
        pass


def test_web_preview_keeps_submitted_jpeg_and_exact_capture_stamp(monkeypatch):
    monkeypatch.setattr(vln_web_adapter, "get_package_share_directory",
                        lambda name: str(Path(__file__).parents[1]))
    server = vln_web_adapter.ScoutWebServer(
        host="127.0.0.1", port=8088, image_topic="camera/image",
        manual_linear_limit=1.0, manual_angular_limit=1.0,
        manual_linear_accel=1.0, manual_angular_accel=1.0,
        commands=queue.Queue(), logger=Logger(),
    )
    success, encoded = cv2.imencode(".jpg", np.zeros((256, 448, 3), np.uint8))
    assert success
    message = CompressedImage()
    message.header.stamp.sec = 1788850000
    message.header.stamp.nanosec = 123456789
    message.data = encoded.tobytes()
    node = SimpleNamespace(web_server=server)
    vln_web_adapter.ScoutVlnWebNode._on_input_image(node, message)
    response = asyncio.run(server._camera_handler(None))
    assert response.body == encoded.tobytes()
    assert response.headers["X-Capture-Stamp"] == "1788850000123456789"
    assert response.headers["X-Frame-Source"] == "vln_input"
    assert server._snapshot()["camera"]["width"] == 448
    assert server._snapshot()["camera"]["height"] == 256
    server.response_metadata = {"capture_stamp": "1788850000123456789"}
    server.update_vln_response({}, {"body_waypoints": []}, 1.0)
    assert server._snapshot()["vln"]["capture_stamp"] == "1788850000123456789"
