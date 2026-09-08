# Copyright 2026 Hive Matrix AI
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from math import pi

import pytest

from scout_base_tools.core import DeadmanController, TopicHealth, Velocity
from scout_base_tools.core import yaw_from_quaternion


def test_topic_health_reports_rate_age_and_timeout():
    health = TopicHealth()
    health.record(10.0)
    health.record(10.1)
    health.record(10.2)

    assert health.rate() == pytest.approx(10.0)
    assert health.age(10.25) == pytest.approx(0.05)
    assert health.online(timeout=0.1, now=10.25)
    assert not health.online(timeout=0.1, now=10.31)


def test_deadman_requires_arm_and_expires_to_zero():
    controller = DeadmanController(timeout=0.25)
    forward = Velocity(linear=0.15)

    assert not controller.pulse(forward, now=1.0)
    controller.arm()
    assert controller.pulse(forward, now=1.0)
    assert controller.command(now=1.24) == forward
    assert controller.command(now=1.25) == Velocity()


def test_disarm_stops_immediately():
    controller = DeadmanController()
    controller.arm()
    controller.pulse(Velocity(angular=0.3), now=1.0)
    controller.disarm()

    assert controller.command(now=1.01) == Velocity()


def test_yaw_from_quaternion():
    yaw = yaw_from_quaternion(0.0, 0.0, 2 ** -0.5, 2 ** -0.5)

    assert yaw == pytest.approx(pi / 2)
