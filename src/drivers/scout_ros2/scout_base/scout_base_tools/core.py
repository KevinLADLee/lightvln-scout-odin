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

"""State and safety helpers for the Scout validation console."""

from collections import deque
from dataclasses import dataclass
from math import atan2
from time import monotonic


class TopicHealth:
    """Track message freshness and an approximate receive rate."""

    def __init__(self, window_size=100):
        self._samples = deque(maxlen=window_size)

    def record(self, timestamp=None):
        self._samples.append(monotonic() if timestamp is None else timestamp)

    def age(self, now=None):
        if not self._samples:
            return None
        current = monotonic() if now is None else now
        return max(0.0, current - self._samples[-1])

    def rate(self):
        if len(self._samples) < 2:
            return 0.0
        elapsed = self._samples[-1] - self._samples[0]
        return (len(self._samples) - 1) / elapsed if elapsed > 0.0 else 0.0

    def online(self, timeout=1.0, now=None):
        age = self.age(now)
        return age is not None and age <= timeout


@dataclass(frozen=True)
class Velocity:
    """A platform-independent velocity command."""

    linear: float = 0.0
    lateral: float = 0.0
    angular: float = 0.0


class DeadmanController:
    """Allow bounded command pulses only while explicitly armed."""

    def __init__(self, timeout=0.25):
        if timeout <= 0.0:
            raise ValueError('deadman timeout must be positive')
        self.timeout = timeout
        self.armed = False
        self._deadline = 0.0
        self._command = Velocity()

    def arm(self):
        self.armed = True
        self.stop()

    def disarm(self):
        self.armed = False
        self.stop()

    def stop(self):
        self._command = Velocity()
        self._deadline = 0.0

    def pulse(self, command, now=None):
        if not self.armed:
            return False
        current = monotonic() if now is None else now
        self._command = command
        self._deadline = current + self.timeout
        return True

    def command(self, now=None):
        current = monotonic() if now is None else now
        if not self.armed or current >= self._deadline:
            return Velocity()
        return self._command


def yaw_from_quaternion(x, y, z, w):
    """Return planar yaw from a geometry_msgs quaternion."""
    sin_yaw = 2.0 * (w * z + x * y)
    cos_yaw = 1.0 - 2.0 * (y * y + z * z)
    return atan2(sin_yaw, cos_yaw)
