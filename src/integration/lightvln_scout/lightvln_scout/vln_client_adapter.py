"""Scout-owned image adaptation around the original VLN client node."""

from __future__ import annotations

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage

from vln_client.vln_client import VlnClient
from vln_client.vln_node import VlnClientNode

from .image_processing import (
    DEFAULT_FIT,
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    ImagePreprocessor,
    ScoutFrameEncoder,
)


class ScoutVlnClientNode(VlnClientNode):
    def __init__(self) -> None:
        # The inherited node owns ROS status, instruction handling and transport.
        # Its worker is idle until the ROS executor processes an instruction.
        super().__init__(client_factory=self._make_client)
        self.declare_parameter("image_width", DEFAULT_WIDTH)
        self.declare_parameter("image_height", DEFAULT_HEIGHT)
        self.declare_parameter("image_fit", DEFAULT_FIT)
        self.declare_parameter("input_image_topic", "vln/input_image/compressed")
        self._scout_encoder = ScoutFrameEncoder(ImagePreprocessor(
            int(self.get_parameter("image_width").value),
            int(self.get_parameter("image_height").value),
            str(self.get_parameter("image_fit").value),
        ))
        self._input_image_pub = self.create_publisher(
            CompressedImage, str(self.get_parameter("input_image_topic").value),
            qos_profile_sensor_data,
        )

    def _make_client(self, **kwargs):
        return VlnClient(**kwargs, frame_encoder=self._encode_frame)

    def _encode_frame(self, frame) -> str:
        return self._scout_encoder(frame)

    def _publish_result(self, result) -> None:
        encoded = self._scout_encoder.take_jpeg(result.frame)
        if encoded is not None:
            image = CompressedImage()
            image.header.stamp.sec = result.frame.stamp_sec
            image.header.stamp.nanosec = result.frame.stamp_nanosec
            image.header.frame_id = "vln_input"
            image.format = "jpeg"
            image.data = encoded
            self._input_image_pub.publish(image)
        super()._publish_result(result)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = ScoutVlnClientNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
