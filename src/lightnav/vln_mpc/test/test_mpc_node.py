import json

import pytest
from vln_mpc.mpc_node import (
    MPC_CONFIG_NAMES,
    OBJNAV_MODE,
    TRACK_MODE,
    parse_vln_response,
    scale_command,
    should_complete_task,
    validate_mpc_config,
)


def response(*, stop):
    return json.dumps(
        {
            "episode": 3,
            "seq": 17,
            "capture_stamp_ns": 123456789,
            "frame_id": "base_link",
            "waypoints": [[1.0, 0.2, -0.1]],
            "stop": stop,
            "visible": True,
        }
    )


def test_parse_vln_response_keeps_stop():
    episode, sequence, stamp_ns, stop, waypoints = parse_vln_response(
        response(stop=True), "base_link"
    )
    assert (episode, sequence, stamp_ns) == (3, 17, 123456789)
    assert stop is True
    assert waypoints == [(1.0, 0.2, -0.1)]


@pytest.mark.parametrize("stop", [False, None])
def test_objnav_continues_without_true_stop(stop):
    assert not should_complete_task(OBJNAV_MODE, stop)


def test_objnav_completes_on_true_stop():
    assert should_complete_task(OBJNAV_MODE, True)


def test_track_ignores_true_stop():
    assert not should_complete_task(TRACK_MODE, True)


def test_mpc_config_validation_and_output_scaling():
    config = {name: 1.0 for name in MPC_CONFIG_NAMES}
    assert validate_mpc_config(config) == ""
    assert scale_command((0.8, -0.4), 1.5, 0.5) == pytest.approx((1.2, -0.2))

    config["q_yaw"] = 0.0
    assert validate_mpc_config(config) == ""
    config["w_max"] = 0.0
    assert "limits" in validate_mpc_config(config)
