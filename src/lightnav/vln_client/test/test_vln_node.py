from vln_client.vln_client import CameraFrame, InferenceResult
from vln_client.vln_node import result_response


def test_standard_response_carries_client_round_trip_latency():
    result = InferenceResult(
        episode=2,
        sequence=3,
        frame=CameraFrame(
            stamp_sec=5,
            stamp_nanosec=10,
            width=2,
            height=1,
            step=6,
            rgb=b"\x00" * 6,
        ),
        waypoints=[(1.0, 0.0, 0.1)],
        stop=False,
        visible=True,
        apos_state="forward",
        opos_state="visible",
        apos_px=None,
        opos_px=(10.0, 20.0),
        latency_ms=37.5,
    )

    response = result_response(result)

    assert response["capture_stamp_ns"] == 5_000_000_010
    assert response["latency_ms"] == 37.5
