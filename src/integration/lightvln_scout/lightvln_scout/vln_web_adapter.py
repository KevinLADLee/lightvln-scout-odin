"""Scout-owned web image handling; original VLN web controls are inherited."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import cv2
import numpy as np
import rclpy
from aiohttp import web
from ament_index_python.packages import get_package_share_directory
from rclpy.executors import ExternalShutdownException, SingleThreadedExecutor
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

from vln_web.web_node import VlnWebNode
from vln_web.web_server import WebServer

from .image_processing import DEFAULT_FIT, ImagePreprocessor


class ScoutWebServer(WebServer):
    def __init__(self, **kwargs) -> None:
        kwargs["web_dir"] = Path(get_package_share_directory("lightvln_scout")) / "web"
        super().__init__(**kwargs)
        self._frame_info = {}
        self.response_metadata = {}

    def update_frame(
        self, frame: bytes, received_s: float, *, width=None, height=None,
        source="camera_preview", capture_stamp="",
    ) -> None:
        with self._state_lock:
            self._frame = frame
            self._frame_received_s = received_s
            self._frame_info = {
                "width": width, "height": height, "source": source,
                "capture_stamp": capture_stamp,
            }
            self._append_sample(self._camera_samples, received_s)

    def update_vln_response(self, data, path, received_s) -> None:
        super().update_vln_response({**data, **self.response_metadata}, path, received_s)

    def _snapshot(self):
        snapshot = super()._snapshot()
        with self._state_lock:
            snapshot["camera"].update(self._frame_info)
        return snapshot

    async def _camera_handler(self, _request):
        with self._state_lock:
            frame, info = self._frame, dict(self._frame_info)
        if frame is None:
            raise web.HTTPServiceUnavailable(text="camera frame unavailable")
        return web.Response(
            body=frame, content_type="image/jpeg",
            headers={
                "Cache-Control": "no-store",
                "X-Capture-Stamp": info.get("capture_stamp", ""),
                "X-Frame-Source": info.get("source", "camera_preview"),
            },
        )


class ScoutVlnWebNode(VlnWebNode):
    def __init__(self) -> None:
        super().__init__(server_factory=ScoutWebServer)
        self.declare_parameter("image_fit", DEFAULT_FIT)
        self.declare_parameter("input_image_topic", "vln/input_image/compressed")
        self._scout_preprocessor = ImagePreprocessor(
            self.image_width, self.image_height,
            str(self.get_parameter("image_fit").value), self.jpeg_quality,
        )
        self.create_subscription(
            CompressedImage, str(self.get_parameter("input_image_topic").value),
            self._on_input_image, qos_profile_sensor_data,
        )

    def _on_image(self, message) -> None:
        if not self.web_server.vln_running():
            super()._on_image(message)

    def _on_compressed_image(self, message) -> None:
        if not self.web_server.vln_running():
            super()._on_compressed_image(message)

    def _update_image(self, image, now) -> None:
        try:
            encoded = self._scout_preprocessor.encode(image)
        except (ValueError, RuntimeError) as exc:
            self.get_logger().warning(f"invalid preview image: {exc}")
            return
        self._last_encode_s = now
        self.web_server.update_frame(
            encoded, now, width=self.image_width, height=self.image_height,
        )

    def _on_input_image(self, message) -> None:
        if not message.data:
            return
        decoded = cv2.imdecode(np.frombuffer(message.data, np.uint8), cv2.IMREAD_COLOR)
        if decoded is None:
            return
        height, width = decoded.shape[:2]
        self.web_server.update_frame(
            bytes(message.data), time.monotonic(), width=width, height=height,
            source="vln_input", capture_stamp=str(
                message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec
            ),
        )

    def _on_vln_response(self, message) -> None:
        # Original VLN response validation/control logic remains in the base node.
        # Pointing pixels are defined in the submitted image's coordinate space.
        self.web_server.response_metadata = {}
        try:
            data = json.loads(message.data)
            if isinstance(data, dict) and type(data.get("capture_stamp_ns")) is int:
                self.web_server.response_metadata = {
                    "capture_stamp": str(data["capture_stamp_ns"]),
                }
        except (ValueError, TypeError):
            pass
        super()._on_vln_response(message)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScoutVlnWebNode()
    executor = SingleThreadedExecutor()
    executor.add_node(node)

    def spin_ros() -> None:
        try:
            executor.spin()
        except ExternalShutdownException:
            pass
        except Exception:
            if rclpy.ok():
                raise

    ros_thread = threading.Thread(
        target=spin_ros, name="vln-web-ros", daemon=True
    )
    ros_thread.start()
    try:
        node.web_server.run()
    except KeyboardInterrupt:
        pass
    finally:
        node.close()
        executor.shutdown(timeout_sec=2.0)
        ros_thread.join(timeout=2.0)
        executor.remove_node(node)
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
