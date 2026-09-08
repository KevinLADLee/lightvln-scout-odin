import asyncio
import queue
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from vln_web.web_server import WebServer


class Logger:
    def info(self, message):
        pass


class Socket:
    closed = False

    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


@pytest.fixture
def server():
    return WebServer(
        host="127.0.0.1", port=0,
        web_dir=Path(__file__).parents[1] / "web", image_topic="camera",
        manual_linear_limit=0.3, manual_angular_limit=0.6,
        manual_linear_accel=0.5, manual_angular_accel=1.0,
        commands=queue.Queue(), logger=Logger(),
    )


def diagnostics(server, **extra):
    server.update_robot_diagnostics({
        "available": True, "connected": True, "mode": "WALK",
        "supported_actions": ["emergency_stop", "reset_emergency_stop"],
        **extra,
    }, "disabled")


def drain(server):
    commands = []
    while not server._commands.empty():
        commands.append(server._commands.get_nowait())
    return commands


def test_expired_adapter_stops_controls_and_rejects_reacquisition(server):
    diagnostics(server)
    server._robot_received_s -= 4.0
    socket = Socket()
    asyncio.run(server._handle_browser_message(socket, "one", {"type": "acquire_control"}))
    assert not server._snapshot()["robot"]["connected"]
    assert [item[0] for item in drain(server)] == ["set_mpc", "stop"]
    assert socket.messages[-1]["ok"] is False
    server.broadcast_runtime()
    assert drain(server) == []  # timeout cleanup is emitted only once
    diagnostics(server)
    assert server._snapshot()["robot"]["connected"]


def test_emergency_is_available_to_observer_and_clears_ownership(server):
    owner, observer = Socket(), Socket()
    diagnostics(server)
    server._controller = owner
    server._websockets = {owner: "owner", observer: "observer"}
    asyncio.run(server._handle_browser_message(
        observer, "observer", {"type": "robot_action", "action": "emergency_stop"},
    ))
    commands = drain(server)
    assert commands[0] == ("mode", "emergency_stop", "observer")
    assert ("set_mpc", False, "observer") in commands
    assert server._controller is None


def test_reset_requires_released_control_and_emergency_rejects_motion(server):
    socket = Socket()
    diagnostics(server, emergency_stopped=True)
    server._controller = socket
    asyncio.run(server._handle_browser_message(
        socket, "one", {"type": "robot_action", "action": "reset_emergency_stop"},
    ))
    assert "release" in socket.messages[-1]["message"]
    server._controller = None
    asyncio.run(server._handle_browser_message(socket, "one", {"type": "acquire_control"}))
    assert "latched" in socket.messages[-1]["message"]
    assert drain(server) == []
    asyncio.run(server._handle_browser_message(
        socket, "one", {"type": "robot_action", "action": "reset_emergency_stop"},
    ))
    assert drain(server) == [("mode", "reset_emergency_stop", "one")]


@pytest.mark.parametrize("kind", ["set_vln", "set_mpc"])
def test_string_false_cannot_enable_motion(server, kind):
    socket = Socket()
    asyncio.run(server._handle_browser_message(socket, "one", {"type": kind, "enabled": "false"}))
    assert "boolean" in socket.messages[-1]["message"]
    assert drain(server) == []


def test_odom_pushes_are_throttled_but_snapshot_keeps_latest(server, monkeypatch):
    messages = []
    monkeypatch.setattr(server, "broadcast", messages.append)
    monkeypatch.setattr("vln_web.web_server.time.monotonic", lambda: 10.0)
    for sequence in range(200):
        server.update_odom({"sequence": sequence})
    assert len(messages) == 1
    assert server._snapshot()["odom"]["sequence"] == 199


def test_real_http_and_websocket_scout_contract(server):
    async def scenario():
        diagnostics(server, battery_voltage=25.4, hardware_output_enabled=False)
        async with TestClient(TestServer(server._create_app())) as client:
            response = await client.get("/")
            assert response.status == 200
            assert "Software emergency stop" in await response.text()
            async with client.ws_connect("/ws") as socket:
                snapshot = await socket.receive_json(timeout=2)
                assert snapshot["data"]["robot"]["battery_voltage"] == 25.4
                await socket.receive_json(timeout=2)  # ownership state
                await socket.send_json({"type": "robot_action", "action": "emergency_stop"})
                state = await socket.receive_json(timeout=2)
                assert state["type"] == "control_state"
                assert drain(server)[0][0:2] == ("mode", "emergency_stop")
    asyncio.run(scenario())
