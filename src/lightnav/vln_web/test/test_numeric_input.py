"""Malformed numeric input must leave the control connection usable."""

import asyncio
import logging
import queue
from pathlib import Path

import pytest
from aiohttp.test_utils import TestClient, TestServer

from vln_web.web_server import (
    MANUAL_LIMIT_NAMES,
    MPC_CONFIG_NAMES,
    WebServer,
    parse_manual_limits,
    parse_mpc_config,
)


@pytest.mark.parametrize("parser,names", [
    (parse_mpc_config, MPC_CONFIG_NAMES),
    (parse_manual_limits, MANUAL_LIMIT_NAMES),
])
def test_numeric_overflow_is_a_validation_error(parser, names):
    config = dict.fromkeys(names, 1.0)
    config[names[0]] = 10**400
    with pytest.raises(ValueError, match="numeric"):
        parser(config)


@pytest.mark.parametrize("payload", [
    {"type": "twist", "x": 10**400},
    {"type": "twist", "x": True},
    {"type": "twist", "y": False},
    {"type": "twist", "z": True},
    {"type": "set_manual_limits", "config": dict.fromkeys(MANUAL_LIMIT_NAMES, 10**400)},
    {"type": "set_mpc_config", "config": dict.fromkeys(MPC_CONFIG_NAMES, 10**400)},
])
def test_bad_numeric_command_keeps_websocket_open_and_never_queues_motion(payload):
    async def scenario():
        commands = queue.Queue()
        server = WebServer(
            host="127.0.0.1", port=0,
            web_dir=Path(__file__).parents[1] / "web", image_topic="camera",
            manual_linear_limit=1.0, manual_angular_limit=1.0,
            manual_linear_accel=0.5, manual_angular_accel=1.0,
            commands=commands, logger=logging.getLogger(__name__),
        )
        server.update_robot_diagnostics({"connected": True, "mode": "WALK"}, "disabled")
        async with TestClient(TestServer(server._create_app())) as client:
            async with client.ws_connect("/ws") as socket:
                await socket.receive_json(timeout=2)
                await socket.receive_json(timeout=2)
                if payload["type"] == "twist":
                    await socket.send_json({"type": "acquire_control"})
                    await socket.receive_json(timeout=2)
                    assert commands.get_nowait()[0] == "manual_control"
                await socket.send_json(payload)
                error = await socket.receive_json(timeout=2)
                assert error["type"] == "command_result"
                assert error["ok"] is False
                assert commands.empty()
                await socket.send_json({"type": "stop"})
                assert (await socket.receive_json(timeout=2))["type"] == "control_state"
                assert any(item[0] == "stop" for item in list(commands.queue))
    asyncio.run(scenario())
