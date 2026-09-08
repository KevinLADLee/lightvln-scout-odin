# vln_client

VLN client node.

## Interface

| Name | Type | Direction | Description |
| --- | --- | --- | --- |
| `camera/color/image_raw` | `sensor_msgs/Image` | subscribe | `rgb8` or `bgr8` camera image by default; a parameter switches it to `sensor_msgs/CompressedImage` |
| `vln/instruction` | `std_msgs/String` | subscribe | A non-empty string starts or replaces the task; an empty string stops it |
| `vln/response` | `std_msgs/String` | publish | JSON inference result with episode, seq, image timestamp, waypoints, stop, visible, plus the apos/opos states and pixel coordinates |
| `vln/path_body` | `nav_msgs/Path` | publish | Visualization only; waypoints in `base_link`, Best Effort |
| `vln/status` | `std_msgs/String` | publish | `IDLE` (empty instruction), `RUNNING` (active task), or `ERROR` (communication or inference failure); published immediately on change and re-sent at 1 Hz |
| `vln/server_url` | `std_msgs/String` | subscribe | Switches the VLN WebSocket URL; `ws://` is added when the scheme is omitted, and an active task reconnects automatically |
| `vln/server_url_status` | `std_msgs/String` | publish | The VLN WebSocket URL currently in effect, Transient Local |

## Layout

- `vln_node.py`: ROS interface and message conversion.
- `vln_client.py`: image encoding, WebSocket, and request lifecycle; only one
  request is in flight at a time — after inference completes, the next camera
  frame triggers a new request.

`apos_state` and `opos_state` are semantic strings provided by the server; the
client does not interpret their values. The corresponding `apos_px` and
`opos_px` are `[x, y]` or `null`.

The VLN server URL is empty by default and must be configured on the web page
before starting a task.

The camera is configured through the `image_topic` and `image_transport`
parameters; `image_transport` accepts `raw` or `compressed`.
