"""HTTP and WebSocket server for the VLN control page."""

from __future__ import annotations

import asyncio
import json
import math
import queue
import socket
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

from aiohttp import WSMsgType, web

WILDCARD_HOSTS = {"", "0.0.0.0", "::"}
VALID_ROBOT_ACTIONS = {
    "stand", "walk", "sit", "toggle_policy",
    "emergency_stop", "reset_emergency_stop",
}
VALID_VLN_MODES = {"objnav", "track"}
DEFAULT_VLN_MODE = "track"
DEFAULT_INSTRUCTION = "follow the white t-shirt person"
MPC_CONFIG_NAMES = (
    "track_v_max",
    "objnav_v_max",
    "w_max",
    "a_max_v",
    "a_max_w",
    "q_x",
    "q_y",
    "q_yaw",
    "r_v",
    "r_w",
    "v_output_scale",
    "w_output_scale",
)
POSITIVE_MPC_CONFIG_NAMES = {
    "track_v_max",
    "objnav_v_max",
    "w_max",
    "a_max_v",
    "a_max_w",
}
MANUAL_LIMIT_NAMES = (
    "linear",
    "angular",
    "linear_accel",
    "angular_accel",
)
Command = tuple[str, Any, str]


class Logger(Protocol):
    def info(self, message: str) -> None: ...


def display_host(bind_host: str) -> str:
    """Return a useful LAN address when the server binds every interface."""
    if bind_host not in WILDCARD_HOSTS:
        return bind_host
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("1.1.1.1", 80))
            address = str(probe.getsockname()[0])
            if address and not address.startswith("127."):
                return address
    except OSError:
        pass
    try:
        for item in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            address = str(item[4][0])
            if address and not address.startswith("127."):
                return address
    except OSError:
        pass
    return "127.0.0.1"


def normalize_server_url(value: str) -> str:
    """Validate a VLN WebSocket URL and add ws:// when omitted."""
    url = str(value).strip()
    if not url:
        return ""
    if len(url) > 2048 or any(char.isspace() for char in url):
        raise ValueError("invalid VLN server URL")
    if "://" not in url:
        url = f"ws://{url}"
    parsed = urlparse(url)
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("invalid VLN server URL port") from exc
    if (
        parsed.scheme not in {"ws", "wss"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or (port is not None and not 1 <= port <= 65535)
    ):
        raise ValueError("VLN server URL must use ws:// or wss://")
    return url


def parse_mpc_config(value: Any) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != set(MPC_CONFIG_NAMES):
        raise ValueError("MPC configuration fields are incomplete")
    config = {}
    for name in MPC_CONFIG_NAMES:
        raw = value[name]
        if isinstance(raw, bool):
            raise ValueError(f"{name} must be numeric")
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not math.isfinite(number):
            raise ValueError(f"{name} must be finite")
        if name in POSITIVE_MPC_CONFIG_NAMES and number <= 0.0:
            raise ValueError(f"{name} must be positive")
        if name not in POSITIVE_MPC_CONFIG_NAMES and number < 0.0:
            raise ValueError(f"{name} must be nonnegative")
        config[name] = number
    if not any(config[name] > 0.0 for name in ("q_x", "q_y", "q_yaw")):
        raise ValueError("at least one MPC state weight must be positive")
    return config


def parse_manual_limits(value: Any) -> dict[str, float]:
    if not isinstance(value, dict) or set(value) != set(MANUAL_LIMIT_NAMES):
        raise ValueError("WASD parameter fields are incomplete")
    config = {}
    for name in MANUAL_LIMIT_NAMES:
        raw = value[name]
        if isinstance(raw, bool):
            raise ValueError(f"{name} must be numeric")
        try:
            number = float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be numeric") from exc
        if not math.isfinite(number) or number <= 0.0:
            raise ValueError(f"{name} must be positive and finite")
        config[name] = number
    return config


class WebServer:
    def __init__(
        self,
        *,
        host: str,
        port: int,
        web_dir: Path,
        image_topic: str,
        manual_linear_limit: float,
        manual_angular_limit: float,
        manual_linear_accel: float,
        manual_angular_accel: float,
        commands: queue.Queue[Command],
        logger: Logger,
        mpc_config_supported: bool = True,
        robot_timeout_s: float = 3.0,
    ) -> None:
        if not math.isfinite(robot_timeout_s) or robot_timeout_s <= 0.0:
            raise ValueError("robot_timeout_s must be positive and finite")
        self._robot_timeout_s = robot_timeout_s
        self._robot_received_s = -math.inf
        self.host = host
        self.port = port
        self.image_topic = image_topic
        self.manual_linear_limit = manual_linear_limit
        self.manual_angular_limit = manual_angular_limit
        self.manual_linear_accel = manual_linear_accel
        self.manual_angular_accel = manual_angular_accel
        self._commands = commands
        self._logger = logger
        self._mpc_config_supported = bool(mpc_config_supported)

        index = (web_dir / "index.html").read_text(encoding="utf-8")
        styles = (web_dir / "styles.css").read_text(encoding="utf-8")
        script = (web_dir / "app.js").read_text(encoding="utf-8")
        self._index_page = index.replace(
            '<link rel="stylesheet" href="/styles.css">',
            f"<style>{styles}</style>",
        ).replace(
            '<script src="/app.js" defer></script>',
            f"<script>{script}</script>",
        )

        self._state_lock = threading.Lock()
        self._frame: bytes | None = None
        self._frame_received_s = 0.0
        self._camera_samples: deque[float] = deque()
        self._response_samples: deque[float] = deque()
        self._path: dict[str, Any] = {
            "frame_id": "",
            "stamp_s": None,
            "body_waypoints": [],
        }
        self._vln: dict[str, Any] = {
            "available": False,
            "level": 1,
            "message": "waiting for vln_client",
            "state": "",
            "enabled": False,
            "connected": False,
            "instruction": DEFAULT_INSTRUCTION,
            "mode": DEFAULT_VLN_MODE,
            "server_url": "",
            "last_latency_ms": None,
            "last_sequence": 0,
            "waypoint_count": 0,
            "visible": None,
            "stop": None,
            "apos_state": None,
            "opos_state": None,
            "apos_px": None,
            "opos_px": None,
        }
        self._robot: dict[str, Any] = {
            "available": False,
            "level": 1,
            "message": "waiting for robot adapter",
            "adapter": "",
            "connected": False,
            "robot_id": "",
            "mode": "UNKNOWN",
            "battery": None,
            "imu": "UNKNOWN",
            "motor": "UNKNOWN",
            "policy": "",
            "vln_policy": "",
            "supported_actions": None,
        }
        self._mpc: dict[str, Any] = {
            "available": False,
            "message": "waiting for motion controller",
            "state": "",
            "enabled": False,
            "active": False,
            "reason": "idle",
            "error": "",
        }
        self._mpc_config: dict[str, Any] = {
            "available": False,
            "supported": self._mpc_config_supported,
            "error": "waiting for motion controller parameter service",
        }
        self._odom: dict[str, Any] = {}
        self._last_odom_broadcast_s = -math.inf
        self._sent_command = {"linear": 0.0, "angular": 0.0}
        self._control_source = "disabled"
        self._wifi: dict[str, Any] = {
            "available": False,
            "interface": "",
            "current_ssid": "",
            "networks": [],
            "scanning": False,
            "connecting": False,
            "error": "",
        }

        self._web_loop: asyncio.AbstractEventLoop | None = None
        self._websockets: dict[web.WebSocketResponse, str] = {}
        self._controller: web.WebSocketResponse | None = None
        self._auto_controller: web.WebSocketResponse | None = None
        self._closed = False

    def run(self) -> None:
        web.run_app(
            self._create_app(),
            host=self.host,
            port=self.port,
            handle_signals=True,
            print=None,
        )

    def close(self) -> None:
        self._closed = True

    def vln_running(self) -> bool:
        with self._state_lock:
            return self._vln.get("state") == "RUNNING"

    def vln_mode(self) -> str:
        with self._state_lock:
            return str(self._vln["mode"])

    def update_frame(self, frame: bytes, received_s: float) -> None:
        with self._state_lock:
            self._frame = frame
            self._frame_received_s = received_s
            self._append_sample(self._camera_samples, received_s)

    def update_vln_status(self, state: str) -> None:
        data = {
            "available": True,
            "level": 2 if state == "ERROR" else 0,
            "message": state,
            "state": state,
            "enabled": state != "IDLE",
            "connected": state == "RUNNING",
        }
        with self._state_lock:
            self._vln.update(data)
            if state == "IDLE":
                self._vln.update(
                    {
                        "instruction": "",
                        "last_latency_ms": None,
                        "last_sequence": 0,
                        "waypoint_count": 0,
                        "visible": None,
                        "stop": None,
                        "apos_state": None,
                        "opos_state": None,
                        "apos_px": None,
                        "opos_px": None,
                    }
                )
            if state != "RUNNING":
                self._vln["waypoint_count"] = 0
                self._path = {
                    "frame_id": "",
                    "stamp_s": None,
                    "body_waypoints": [],
                }
            snapshot = dict(self._vln)
        self.broadcast({"type": "vln_status", "data": snapshot})
        if state != "RUNNING":
            self.broadcast({"type": "path", "data": {"body_waypoints": []}})

    def update_server_url(self, server_url: str) -> None:
        normalized = normalize_server_url(server_url)
        with self._state_lock:
            self._vln["server_url"] = normalized
            snapshot = dict(self._vln)
        self.broadcast({"type": "vln_status", "data": snapshot})

    def update_vln_response(
        self,
        data: dict[str, Any],
        path: dict[str, Any],
        received_s: float,
    ) -> None:
        with self._state_lock:
            self._vln.update(data)
            self._path = path
            self._append_sample(self._response_samples, received_s)
            snapshot = dict(self._vln)
        self.broadcast({"type": "vln_status", "data": snapshot})
        self.broadcast({"type": "path", "data": path})

    def reset_vln(self, instruction: str, mode: str) -> None:
        with self._state_lock:
            self._vln.update(
                {
                    "instruction": instruction,
                    "mode": mode,
                    "last_latency_ms": None,
                    "last_sequence": 0,
                    "waypoint_count": 0,
                    "visible": None,
                    "stop": None,
                    "apos_state": None,
                    "opos_state": None,
                    "apos_px": None,
                    "opos_px": None,
                }
            )
            self._response_samples.clear()
            self._path = {
                "frame_id": "",
                "stamp_s": None,
                "body_waypoints": [],
            }
        self.broadcast({"type": "path", "data": {"body_waypoints": []}})

    def update_robot_diagnostics(
        self,
        data: dict[str, Any],
        control_source: str,
    ) -> None:
        with self._state_lock:
            was_ready = bool(self._robot.get("connected")) and not bool(
                self._robot.get("emergency_stopped")
            )
            self._robot = dict(data)
            self._robot_received_s = time.monotonic()
            if control_source:
                self._control_source = control_source
        self.broadcast({"type": "robot_diagnostics", "data": data})
        if not data["connected"] or data.get("emergency_stopped"):
            reason = data.get("message") or "robot unavailable"
            if was_ready:
                self._queue_command("set_mpc", False, "")
                self._queue_command("stop", None, "")
            self.revoke_controller(reason)
            self.clear_auto_controller(reason)

    def update_mpc_status(self, state: str) -> None:
        data = {
            "available": True,
            "message": state,
            "state": state,
            "enabled": state != "IDLE",
            "active": state == "RUNNING",
            "reason": state.lower(),
            "error": "MPC error; see logs" if state == "ERROR" else "",
        }
        with self._state_lock:
            self._mpc = data
        self.broadcast({"type": "mpc_status", "data": data})

    def update_mpc_config(self, config: dict[str, float]) -> None:
        data = {
            "available": True,
            "supported": self._mpc_config_supported,
            "error": "",
            **config,
        }
        with self._state_lock:
            if data == self._mpc_config:
                return
            self._mpc_config = data
        self.broadcast({"type": "mpc_config", "data": data})

    def update_manual_limits(self, config: dict[str, float]) -> None:
        with self._state_lock:
            self.manual_linear_limit = config["linear"]
            self.manual_angular_limit = config["angular"]
            self.manual_linear_accel = config["linear_accel"]
            self.manual_angular_accel = config["angular_accel"]
        self.broadcast({"type": "manual_limits", "data": dict(config)})

    def set_mpc_config_error(self, error: str) -> None:
        data = {
            "available": False,
            "supported": self._mpc_config_supported,
            "error": error,
        }
        with self._state_lock:
            if data == self._mpc_config:
                return
            self._mpc_config = data
        self.broadcast({"type": "mpc_config", "data": data})

    def update_odom(self, data: dict[str, Any]) -> None:
        with self._state_lock:
            self._odom = data
            now = time.monotonic()
            if now - self._last_odom_broadcast_s < 0.1:
                return
            self._last_odom_broadcast_s = now
        self.broadcast({"type": "odom", "data": data})

    def update_sent_command(self, data: dict[str, Any]) -> None:
        with self._state_lock:
            self._sent_command = data
        self.broadcast({"type": "sent_command", "data": data})

    def update_control_source(self, source: str) -> None:
        with self._state_lock:
            self._control_source = source
        self.broadcast({"type": "control_source", "source": source})

    def set_wifi_busy(self, operation: str) -> None:
        with self._state_lock:
            self._wifi["scanning"] = operation == "scan"
            self._wifi["connecting"] = operation == "connect"
            self._wifi["error"] = ""
            data = dict(self._wifi)
        self.broadcast({"type": "wifi_status", "data": data})

    def set_wifi_error(self, message: str) -> None:
        with self._state_lock:
            self._wifi["scanning"] = False
            self._wifi["connecting"] = False
            self._wifi["error"] = message
            data = dict(self._wifi)
        self.broadcast({"type": "wifi_status", "data": data})

    def update_wifi(self, data: dict[str, Any]) -> None:
        with self._state_lock:
            self._wifi.update(data)
            self._wifi["scanning"] = False
            self._wifi["connecting"] = False
            self._wifi["error"] = ""
            snapshot = {
                **self._wifi,
                "networks": list(self._wifi["networks"]),
            }
        self.broadcast({"type": "wifi_status", "data": snapshot})

    def _expire_robot_diagnostics(self) -> None:
        with self._state_lock:
            if (
                not self._robot.get("available")
                or time.monotonic() - self._robot_received_s <= self._robot_timeout_s
            ):
                return
            self._robot = {
                **self._robot, "available": False, "connected": False,
                "level": 2, "message": "robot adapter diagnostics timed out",
                "battery": None, "battery_voltage": None,
                "telemetry_fresh": False, "motor": "UNKNOWN", "imu": "UNKNOWN",
                "vehicle_state": "", "control_mode": "", "error_code": "",
            }
            self._control_source = "disabled"
        self._queue_command("set_mpc", False, "")
        self._queue_command("stop", None, "")
        self.revoke_controller("robot adapter diagnostics timed out")
        self.clear_auto_controller("robot adapter diagnostics timed out")

    def broadcast_runtime(self) -> None:
        self._expire_robot_diagnostics()
        self.broadcast({"type": "runtime", "data": self._snapshot()})

    def send_client(self, client_id: str, payload: dict[str, Any]) -> None:
        loop = self._web_loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._send_client(client_id, payload), loop
            )

    def revoke_controller(self, reason: str) -> None:
        loop = self._web_loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._revoke_controller(reason), loop
            )

    def clear_auto_controller(self, reason: str) -> None:
        loop = self._web_loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(
                self._clear_auto_controller(reason), loop
            )

    def broadcast(self, payload: dict[str, Any]) -> None:
        loop = self._web_loop
        if loop is not None and loop.is_running():
            asyncio.run_coroutine_threadsafe(self._broadcast(payload), loop)

    @staticmethod
    def _append_sample(samples: deque[float], now: float) -> None:
        samples.append(now)
        while samples and samples[0] < now - 5.0:
            samples.popleft()

    @staticmethod
    def _sample_rate(samples: deque[float], now: float) -> float:
        while samples and samples[0] < now - 5.0:
            samples.popleft()
        if len(samples) < 2:
            return 0.0
        elapsed = samples[-1] - samples[0]
        return (len(samples) - 1) / elapsed if elapsed > 0.0 else 0.0

    def _queue_command(self, kind: str, payload: Any, client_id: str) -> None:
        command = (kind, payload, client_id)
        try:
            self._commands.put_nowait(command)
        except queue.Full:
            try:
                self._commands.get_nowait()
            except queue.Empty:
                pass
            self._commands.put_nowait(command)

    def _snapshot(self) -> dict[str, Any]:
        now = time.monotonic()
        with self._state_lock:
            return {
                "vln": dict(self._vln),
                "mpc": dict(self._mpc),
                "mpc_config": dict(self._mpc_config),
                "robot": dict(self._robot),
                "path": {
                    **self._path,
                    "body_waypoints": list(self._path["body_waypoints"]),
                },
                "odom": dict(self._odom),
                "sent_command": dict(self._sent_command),
                "control_source": self._control_source,
                "wifi": {
                    **self._wifi,
                    "networks": list(self._wifi["networks"]),
                },
                "manual_limits": {
                    "linear": self.manual_linear_limit,
                    "angular": self.manual_angular_limit,
                    "linear_accel": self.manual_linear_accel,
                    "angular_accel": self.manual_angular_accel,
                },
                "camera": {
                    "topic": self.image_topic,
                    "received": self._frame is not None,
                    "age_ms": (
                        (now - self._frame_received_s) * 1000.0
                        if self._frame_received_s > 0.0
                        else None
                    ),
                    "fps": self._sample_rate(self._camera_samples, now),
                },
                "response_hz": self._sample_rate(
                    self._response_samples,
                    now,
                ),
            }

    def _create_app(self) -> web.Application:
        app = web.Application()
        app.router.add_get("/", self._index_handler)
        app.router.add_get("/ws", self._websocket_handler)
        app.router.add_get("/api/health", self._health_handler)
        app.router.add_get("/api/camera.jpg", self._camera_handler)
        app.on_startup.append(self._on_startup)
        app.on_shutdown.append(self._on_shutdown)
        return app

    async def _on_startup(self, _app: web.Application) -> None:
        self._web_loop = asyncio.get_running_loop()
        self._logger.info(
            f"VLN web: http://{display_host(self.host)}:{self.port}/"
        )

    async def _on_shutdown(self, _app: web.Application) -> None:
        self._closed = True
        if self._controller is not None:
            await self._release_controller("vln_web shutdown")
            await asyncio.sleep(0.05)
        client_id = (
            self._websockets.get(self._auto_controller, "")
            if self._auto_controller is not None
            else ""
        )
        self._auto_controller = None
        self._queue_command("set_mpc", False, client_id)
        await asyncio.sleep(0.05)
        for websocket in list(self._websockets):
            await websocket.close(code=1001, message=b"vln_web shutdown")
        self._websockets.clear()
        self._web_loop = None

    async def _index_handler(self, _request: web.Request) -> web.Response:
        return web.Response(text=self._index_page, content_type="text/html")

    async def _health_handler(self, _request: web.Request) -> web.Response:
        return web.json_response({"ok": True, **self._snapshot()})

    async def _camera_handler(self, _request: web.Request) -> web.Response:
        with self._state_lock:
            frame = self._frame
        if frame is None:
            raise web.HTTPServiceUnavailable(text="camera frame unavailable")
        return web.Response(
            body=frame,
            content_type="image/jpeg",
            headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
        )

    async def _websocket_handler(self, request: web.Request) -> web.WebSocketResponse:
        origin = request.headers.get("Origin")
        if origin and urlparse(origin).netloc != request.host:
            raise web.HTTPForbidden(text="invalid WebSocket origin")
        websocket = web.WebSocketResponse(heartbeat=10.0, max_msg_size=16384)
        await websocket.prepare(request)
        client_id = uuid.uuid4().hex
        self._websockets[websocket] = client_id
        await websocket.send_json({"type": "snapshot", "data": self._snapshot()})
        await self._broadcast_control_state("browser connected")
        try:
            async for message in websocket:
                if message.type != WSMsgType.TEXT:
                    continue
                try:
                    payload = json.loads(message.data)
                except (json.JSONDecodeError, TypeError):
                    await websocket.send_json(
                        {
                            "type": "command_result",
                            "ok": False,
                            "message": "invalid JSON",
                        }
                    )
                    continue
                if not isinstance(payload, dict):
                    continue
                await self._handle_browser_message(websocket, client_id, payload)
        finally:
            if self._controller is websocket:
                await self._release_controller("controller disconnected")
            released_auto = self._auto_controller is websocket
            if self._auto_controller is websocket:
                self._auto_controller = None
                self._queue_command("set_mpc", False, client_id)
                self._queue_command(
                    "set_vln", (False, "", self.vln_mode()), client_id
                )
            self._websockets.pop(websocket, None)
            if released_auto:
                await self._broadcast_control_state(
                    "MPC controller disconnected"
                )
        return websocket

    async def _handle_browser_message(
        self,
        websocket: web.WebSocketResponse,
        client_id: str,
        payload: dict[str, Any],
    ) -> None:
        self._expire_robot_diagnostics()
        kind = str(payload.get("type", ""))
        if kind in {"set_vln", "set_mpc"} and not isinstance(
            payload.get("enabled"), bool
        ):
            await self._input_error(websocket, "enabled must be a boolean")
            return
        with self._state_lock:
            emergency = bool(self._robot.get("emergency_stopped"))
        if emergency and (
            kind in {"acquire_control", "twist"}
            or (kind in {"set_vln", "set_mpc"} and payload.get("enabled"))
        ):
            await self._input_error(websocket, "emergency stop is latched")
            return
        if kind == "set_vln":
            enabled = bool(payload.get("enabled"))
            instruction = str(payload.get("instruction", "")).strip()
            mode = str(payload.get("mode", "")).strip().lower()
            if len(instruction) > 500:
                await self._input_error(
                    websocket, "instruction must not exceed 500 characters"
                )
                return
            if mode not in VALID_VLN_MODES:
                await self._input_error(
                    websocket, "VLN mode must be objnav or track"
                )
                return
            if enabled and not instruction:
                await self._input_error(
                    websocket, "enter an instruction before enabling VLN"
                )
                return
            if enabled:
                with self._state_lock:
                    robot = dict(self._robot)
                    mpc = dict(self._mpc)
                    server_url = str(self._vln.get("server_url", ""))
                if not server_url:
                    await self._input_error(
                        websocket, "configure the VLN server URL first"
                    )
                    return
                if not robot.get("connected"):
                    await self._input_error(websocket, "robot is disconnected")
                    return
                if robot.get("mode") != "WALK":
                    await self._input_error(
                        websocket,
                        "robot mode is "
                        f"{robot.get('mode', 'UNKNOWN')}; enter WALK first",
                    )
                    return
                if not mpc.get("available"):
                    await self._input_error(
                        websocket, "motion controller is unavailable"
                    )
                    return
                if (
                    self._auto_controller is not None
                    and self._auto_controller is not websocket
                ):
                    await self._input_error(
                        websocket, "another browser owns MPC control"
                    )
                    return
                if (
                    self._controller is not None
                    and self._controller is not websocket
                ):
                    await self._input_error(
                        websocket, "another browser owns manual control"
                    )
                    return
                if self._controller is websocket:
                    await self._release_controller("switching to VLN control")
                self._auto_controller = websocket
                self._queue_command(
                    "set_vln", (True, instruction, mode), client_id
                )
                self._queue_command("set_mpc", True, client_id)
                await self._broadcast_control_state("VLN control acquired")
                return
            with self._state_lock:
                mpc_enabled = bool(self._mpc.get("enabled"))
            if (
                self._auto_controller is not None or mpc_enabled
            ):
                self._auto_controller = None
                self._queue_command("set_mpc", False, client_id)
                await self._broadcast_control_state("VLN stopped")
            self._queue_command(
                "set_vln", (False, instruction, mode), client_id
            )
            return
        if kind == "set_server_url":
            try:
                server_url = normalize_server_url(
                    str(payload.get("server_url", ""))
                )
            except ValueError as exc:
                await self._input_error(websocket, str(exc))
                return
            self._queue_command("set_server_url", server_url, client_id)
            return
        if kind == "set_mpc_config":
            try:
                config = parse_mpc_config(payload.get("config"))
            except ValueError as exc:
                await self._input_error(websocket, str(exc), "mpc_config")
                return
            self._queue_command("set_mpc_config", config, client_id)
            return
        if kind == "set_manual_limits":
            if self._controller is not None or self._auto_controller is not None:
                await self._input_error(
                    websocket,
                    "release robot control before updating WASD parameters",
                    "manual_limits",
                )
                return
            try:
                config = parse_manual_limits(payload.get("config"))
            except ValueError as exc:
                await self._input_error(websocket, str(exc), "manual_limits")
                return
            self._queue_command("set_manual_limits", config, client_id)
            return
        if kind == "wifi_scan":
            self._queue_command("wifi_scan", None, client_id)
            return
        if kind == "wifi_connect":
            if self._controller is not None or self._auto_controller is not None:
                await self._input_error(
                    websocket,
                    "release robot control before switching Wi-Fi",
                )
                return
            ssid = str(payload.get("ssid", "")).strip()
            password = str(payload.get("password", ""))
            if not ssid or len(ssid.encode("utf-8")) > 32:
                await self._input_error(websocket, "invalid Wi-Fi SSID")
                return
            if "\n" in password or "\r" in password or len(password) > 128:
                await self._input_error(websocket, "invalid Wi-Fi password")
                return
            self._queue_command(
                "wifi_connect",
                {"ssid": ssid, "password": password},
                client_id,
            )
            await websocket.send_json(
                {
                    "type": "command_result",
                    "command": "wifi_connect",
                    "ok": True,
                    "message": f"Switching Wi-Fi to {ssid}",
                }
            )
            return
        if kind == "set_mpc":
            enabled = bool(payload.get("enabled"))
            if not enabled:
                self._auto_controller = None
                self._queue_command("set_mpc", False, client_id)
                await self._broadcast_control_state("MPC control released")
                return
            if (
                self._auto_controller is not None
                and self._auto_controller is not websocket
            ):
                await self._input_error(
                    websocket, "another browser owns MPC control"
                )
                return
            with self._state_lock:
                robot = dict(self._robot)
                vln = dict(self._vln)
                mpc = dict(self._mpc)
                waypoint_count = len(self._path["body_waypoints"])
            if not robot.get("connected"):
                await self._input_error(websocket, "robot is disconnected")
                return
            if robot.get("mode") != "WALK":
                await self._input_error(
                    websocket,
                    f"robot mode is {robot.get('mode', 'UNKNOWN')}; enter WALK first",
                )
                return
            if not mpc.get("available"):
                await self._input_error(
                    websocket, "motion controller is unavailable"
                )
                return
            if not vln.get("enabled") or waypoint_count == 0:
                await self._input_error(
                    websocket, "enable VLN and wait for waypoints first"
                )
                return
            if self._controller is not None and self._controller is not websocket:
                await self._input_error(
                    websocket, "another browser owns manual control"
                )
                return
            if self._controller is websocket:
                await self._release_controller("switching to MPC control")
            self._auto_controller = websocket
            self._queue_command("set_mpc", True, client_id)
            await self._broadcast_control_state("MPC control acquired")
            return
        if kind == "acquire_control":
            with self._state_lock:
                robot_connected = bool(self._robot.get("connected"))
            if not robot_connected:
                await self._input_error(websocket, "robot is disconnected")
                return
            if self._auto_controller is not None:
                await self._input_error(websocket, "MPC auto control is active")
                return
            if self._controller is not None and self._controller is not websocket:
                await self._input_error(
                    websocket, "another browser owns manual control"
                )
                return
            self._controller = websocket
            self._queue_command("manual_control", True, client_id)
            await self._broadcast_control_state("manual control acquired")
            return
        if kind == "release_control":
            if self._controller is websocket:
                await self._release_controller("manual control released")
            return
        if kind == "stop":
            if self._controller is not None:
                await self._release_controller("STOP pressed")
            self._auto_controller = None
            self._queue_command("set_mpc", False, client_id)
            self._queue_command("stop", None, client_id)
            await self._broadcast_control_state("STOP pressed")
            return
        if kind == "twist":
            if self._controller is not websocket:
                await self._input_error(websocket, "control is not acquired")
                return
            try:
                linear = float(payload.get("x", 0.0))
                lateral = float(payload.get("y", 0.0))
                angular = float(payload.get("z", 0.0))
            except (TypeError, ValueError):
                await self._input_error(websocket, "twist must be numeric")
                return
            if not all(
                math.isfinite(value) for value in (linear, lateral, angular)
            ):
                await self._input_error(websocket, "twist must be finite")
                return
            if abs(lateral) > 1e-9:
                await self._input_error(websocket, "lateral speed must be zero")
                return
            with self._state_lock:
                linear_limit = self.manual_linear_limit
                angular_limit = self.manual_angular_limit
            if abs(linear) > linear_limit or abs(angular) > angular_limit:
                await self._input_error(
                    websocket, "manual speed exceeds configured limit"
                )
                return
            self._queue_command("twist", (linear, angular), client_id)
            return
        if kind == "robot_action":
            action = str(payload.get("action", "")).strip().lower()
            if (
                action not in {
                    "toggle_policy", "emergency_stop", "reset_emergency_stop"
                }
                and self._controller is not websocket
            ):
                await self._input_error(websocket, "control is not acquired")
                return
            if action not in VALID_ROBOT_ACTIONS:
                await self._input_error(websocket, "unknown robot action")
                return
            with self._state_lock:
                supported_actions = self._robot.get("supported_actions")
            if (
                isinstance(supported_actions, list)
                and action not in supported_actions
            ):
                await self._input_error(
                    websocket, f"robot action {action} is unsupported"
                )
                return
            if action in {"emergency_stop", "reset_emergency_stop"}:
                if not isinstance(supported_actions, list):
                    await self._input_error(websocket, "safety action is unsupported")
                    return
                if action == "reset_emergency_stop":
                    if self._controller is not None or self._auto_controller is not None:
                        await self._input_error(websocket, "release control before reset")
                        return
                else:
                    # Queue the latch before slower controller cleanup requests.
                    self._queue_command("mode", action, client_id)
                    if self._controller is not None:
                        await self._release_controller("software emergency stop")
                    self._auto_controller = None
                    self._queue_command("set_mpc", False, client_id)
                    await self._broadcast_control_state("software emergency stop")
                    return
            self._queue_command("mode", action, client_id)
            return
        await self._input_error(websocket, "unknown command")

    @staticmethod
    async def _input_error(
        websocket: web.WebSocketResponse,
        message: str,
        command: str = "",
    ) -> None:
        payload = {"type": "command_result", "ok": False, "message": message}
        if command:
            payload["command"] = command
        await websocket.send_json(payload)

    async def _release_controller(self, reason: str) -> None:
        client_id = (
            self._websockets.get(self._controller, "")
            if self._controller is not None
            else ""
        )
        self._controller = None
        self._queue_command("twist", (0.0, 0.0), client_id)
        self._queue_command("manual_control", False, client_id)
        await self._broadcast_control_state(reason)

    async def _broadcast_control_state(self, reason: str) -> None:
        for websocket in list(self._websockets):
            if websocket.closed:
                continue
            try:
                await websocket.send_json(
                    {
                        "type": "control_state",
                        "owner": self._controller is websocket,
                        "auto_owner": self._auto_controller is websocket,
                        "locked": (
                            self._controller is not None
                            or self._auto_controller is not None
                        ),
                        "reason": reason,
                    }
                )
            except Exception:
                pass

    async def _revoke_controller(self, reason: str) -> None:
        if self._controller is not None:
            await self._release_controller(reason)

    async def _clear_auto_controller(self, reason: str) -> None:
        if self._auto_controller is None:
            return
        self._auto_controller = None
        await self._broadcast_control_state(reason)

    async def _broadcast(self, payload: dict[str, Any]) -> None:
        for websocket in list(self._websockets):
            if websocket.closed:
                continue
            try:
                await websocket.send_json(payload)
            except Exception:
                pass

    async def _send_client(self, client_id: str, payload: dict[str, Any]) -> None:
        for websocket, current_id in list(self._websockets.items()):
            if current_id == client_id and not websocket.closed:
                await websocket.send_json(payload)
                return
