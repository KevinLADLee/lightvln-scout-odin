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

"""Curses-based hardware test console bundled with scout_base."""

import argparse
import curses
import sys
from time import monotonic

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from rclpy.utilities import remove_ros_args
from scout_msgs.msg import ScoutLightCmd, ScoutRCState, ScoutStatus

from .core import DeadmanController, TopicHealth, Velocity, yaw_from_quaternion


MOTOR_NAMES = ('front-right', 'front-left', 'rear-right', 'rear-left')
LIGHT_OFF = ScoutLightCmd.LIGHT_CONST_OFF
LIGHT_ON = ScoutLightCmd.LIGHT_CONST_ON


class ScoutTestNode(Node):
    """ROS-facing portion of the test console."""

    def __init__(self, args):
        super().__init__('scout_test_tui')
        self.status = None
        self.odometry = None
        self.remote = None
        self.health = {
            'status': TopicHealth(),
            'odom': TopicHealth(),
            'remote': TopicHealth(),
        }
        self.command_publisher = self.create_publisher(
            Twist, args.cmd_topic, 5
        )
        self.light_publisher = self.create_publisher(
            ScoutLightCmd, args.light_topic, 5
        )
        self.create_subscription(
            ScoutStatus, args.status_topic, self._on_status, 10
        )
        self.create_subscription(Odometry, args.odom_topic, self._on_odom, 10)
        self.create_subscription(
            ScoutRCState, args.rc_topic, self._on_remote, 10
        )

    def _on_status(self, message):
        self.status = message
        self.health['status'].record()

    def _on_odom(self, message):
        self.odometry = message
        self.health['odom'].record()

    def _on_remote(self, message):
        self.remote = message
        self.health['remote'].record()

    def publish_velocity(self, velocity):
        message = Twist()
        message.linear.x = velocity.linear
        message.linear.y = velocity.lateral
        message.angular.z = velocity.angular
        self.command_publisher.publish(message)

    def publish_lights(self, front_on, rear_on):
        message = ScoutLightCmd()
        message.cmd_ctrl_allowed = True
        message.front_mode = LIGHT_ON if front_on else LIGHT_OFF
        message.front_custom_value = 0
        message.rear_mode = LIGHT_ON if rear_on else LIGHT_OFF
        message.rear_custom_value = 0
        self.light_publisher.publish(message)


class ScoutConsole:
    """Terminal UI and keyboard control loop."""

    def __init__(self, screen, node, args):
        self.screen = screen
        self.node = node
        self.args = args
        self.deadman = DeadmanController(args.deadman_timeout)
        self.front_light = False
        self.rear_light = False
        self.notice = 'Monitor mode: press uppercase E to arm motion'
        self.running = True
        self._last_publish = 0.0
        self._configure_screen()

    def _configure_screen(self):
        curses.curs_set(0)
        self.screen.nodelay(True)
        self.screen.timeout(20)
        self.screen.keypad(True)
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_GREEN, -1)
            curses.init_pair(2, curses.COLOR_YELLOW, -1)
            curses.init_pair(3, curses.COLOR_RED, -1)
            curses.init_pair(4, curses.COLOR_CYAN, -1)

    def run(self):
        try:
            while rclpy.ok() and self.running:
                rclpy.spin_once(self.node, timeout_sec=0.0)
                self._handle_key(self.screen.getch())
                self._publish_command()
                self._draw()
        finally:
            self.deadman.disarm()
            for _ in range(5):
                self.node.publish_velocity(Velocity())

    def _handle_key(self, key):
        if key == -1:
            return
        if key == ord('E'):
            if self.deadman.armed:
                self.deadman.disarm()
                self.node.publish_velocity(Velocity())
                self.notice = 'Motion locked; zero command sent'
            else:
                self.deadman.arm()
                self.notice = 'Motion ARMED; keep tapping/holding a drive key'
            return
        if key in (27, ord(' ')):
            self.deadman.disarm()
            self.node.publish_velocity(Velocity())
            self.notice = 'EMERGENCY STOP: motion locked'
            return
        if key in (ord('q'), ord('Q')):
            self.deadman.disarm()
            self.node.publish_velocity(Velocity())
            self.running = False
            return
        if key == ord('1'):
            self.front_light = not self.front_light
            self.node.publish_lights(self.front_light, self.rear_light)
            self.notice = 'Front light toggled'
            return
        if key == ord('2'):
            self.rear_light = not self.rear_light
            self.node.publish_lights(self.front_light, self.rear_light)
            self.notice = 'Rear light toggled'
            return

        commands = {
            ord('w'): Velocity(linear=self.args.linear_speed),
            ord('s'): Velocity(linear=-self.args.linear_speed),
            ord('a'): Velocity(angular=self.args.angular_speed),
            ord('d'): Velocity(angular=-self.args.angular_speed),
        }
        if self.args.omni:
            commands.update(
                {
                    ord('j'): Velocity(lateral=self.args.lateral_speed),
                    ord('l'): Velocity(lateral=-self.args.lateral_speed),
                }
            )
        command = commands.get(key)
        if command is not None:
            if not self.deadman.pulse(command):
                self.notice = 'Motion is locked; press uppercase E first'

    def _publish_command(self):
        current = monotonic()
        if self.deadman.armed and current - self._last_publish >= 0.05:
            self.node.publish_velocity(self.deadman.command(current))
            self._last_publish = current

    def _safe_add(self, row, column, text, style=0):
        height, width = self.screen.getmaxyx()
        if row < 0 or row >= height or column >= width:
            return
        try:
            available = max(0, width - column - 1)
            self.screen.addnstr(row, column, str(text), available, style)
        except curses.error:
            pass

    def _draw(self):
        self.screen.erase()
        status_online = self.node.health['status'].online()
        connection = 'ONLINE' if status_online else 'NO DATA'
        connection_style = curses.color_pair(1 if status_online else 3)
        armed_style = curses.color_pair(2 if self.deadman.armed else 1)
        self._safe_add(
            0, 0, 'SCOUT MINI · Hardware Test Console', curses.A_BOLD
        )
        self._safe_add(0, 37, connection, connection_style | curses.A_BOLD)
        self._safe_add(
            1,
            0,
            'Motion: ' + ('ARMED' if self.deadman.armed else 'LOCKED'),
            armed_style | curses.A_BOLD,
        )
        self._safe_add(
            1,
            22,
            'cmd_vel subscribers: '
            f'{self.node.command_publisher.get_subscription_count()}',
        )
        self._safe_add(2, 0, self._can_summary())

        self._safe_add(4, 0, 'TOPICS', curses.A_BOLD | curses.color_pair(4))
        for index, (label, key) in enumerate(
            (
                ('scout_status', 'status'),
                ('odom', 'odom'),
                ('rc_status', 'remote'),
            )
        ):
            health = self.node.health[key]
            age = health.age()
            age_text = '--' if age is None else f'{age:5.2f}s'
            self._safe_add(
                5 + index,
                0,
                f'{label:<14} {health.rate():6.1f} Hz   age {age_text}',
            )

        self._draw_base(4, 42)
        self._draw_motors(10, 0)
        self._draw_odometry(10, 66)
        self._draw_remote(16, 66)

        height, _ = self.screen.getmaxyx()
        controls = (
            'W/S drive  A/D turn  Space/Esc STOP  '
            'E arm/lock  1/2 lights  Q quit'
        )
        if self.args.omni:
            controls = (
                'W/S drive  A/D turn  J/L strafe  '
                'Space/Esc STOP  E arm  Q quit'
            )
        self._safe_add(height - 3, 0, controls, curses.A_BOLD)
        self._safe_add(height - 2, 0, self.notice, curses.color_pair(2))
        self._safe_add(
            height - 1,
            0,
            'Drive keys are deadman pulses; release stops within '
            f'{self.args.deadman_timeout:.2f}s.',
        )
        self.screen.refresh()

    def _can_summary(self):
        path = f'/sys/class/net/{self.args.can_interface}/operstate'
        try:
            with open(path, encoding='utf-8') as stream:
                state = stream.read().strip()
            return f'CAN: {self.args.can_interface} ({state})'
        except OSError:
            return f'CAN: {self.args.can_interface} (not found)'

    def _draw_base(self, row, column):
        heading_style = curses.A_BOLD | curses.color_pair(4)
        self._safe_add(row, column, 'BASE', heading_style)
        status = self.node.status
        if status is None:
            self._safe_add(row + 1, column, 'Waiting for scout_status...')
            return
        color = 3 if status.error_code else 1
        error_style = curses.color_pair(color)
        self._safe_add(
            row + 1, column,
            f'Battery       {status.battery_voltage:6.2f} V'
        )
        self._safe_add(
            row + 2, column,
            f'Linear        {status.linear_velocity:6.3f} m/s'
        )
        self._safe_add(
            row + 3, column,
            f'Angular       {status.angular_velocity:6.3f} rad/s'
        )
        self._safe_add(
            row + 4, column,
            f'Vehicle/mode  {status.vehicle_state}/{status.control_mode}'
        )
        self._safe_add(
            row + 5, column,
            f'Error flags   0x{status.error_code:04x}', error_style
        )
        self._safe_add(
            row + 6,
            column,
            'Lights        front '
            f'{status.front_light_state.mode} / rear '
            f'{status.rear_light_state.mode}',
        )

    def _draw_motors(self, row, column):
        heading_style = curses.A_BOLD | curses.color_pair(4)
        self._safe_add(row, column, 'MOTORS', heading_style)
        self._safe_add(
            row + 1,
            column,
            'position        rpm    current   voltage   driver °C  motor °C',
        )
        status = self.node.status
        for index, name in enumerate(MOTOR_NAMES):
            if status is None:
                values = (
                    f'{name:<13}     --         --        --'
                    '          --        --'
                )
            else:
                motor = status.actuator_states[index]
                values = (
                    f'{name:<13} {motor.rpm:6d}  {motor.current:8.2f} A'
                    f'  {motor.driver_voltage:6.1f} V'
                    f'  {motor.driver_temperature:7.1f}'
                    f'  {motor.motor_temperature:8d}'
                )
            self._safe_add(row + 2 + index, column, values)

    def _draw_odometry(self, row, column):
        heading_style = curses.A_BOLD | curses.color_pair(4)
        self._safe_add(row, column, 'ODOMETRY', heading_style)
        odometry = self.node.odometry
        if odometry is None:
            self._safe_add(row + 1, column, 'Waiting for odom...')
            return
        pose = odometry.pose.pose
        yaw = yaw_from_quaternion(
            pose.orientation.x,
            pose.orientation.y,
            pose.orientation.z,
            pose.orientation.w,
        )
        self._safe_add(row + 1, column, f'x    {pose.position.x:8.3f} m')
        self._safe_add(row + 2, column, f'y    {pose.position.y:8.3f} m')
        self._safe_add(row + 3, column, f'yaw  {yaw:8.3f} rad')

    def _draw_remote(self, row, column):
        heading_style = curses.A_BOLD | curses.color_pair(4)
        self._safe_add(row, column, 'REMOTE', heading_style)
        remote = self.node.remote
        if remote is None:
            self._safe_add(row + 1, column, 'Waiting for rc_status...')
            return
        self._safe_add(
            row + 1,
            column,
            f'switches  {remote.swa} {remote.swb} '
            f'{remote.swc} {remote.swd}',
        )
        self._safe_add(
            row + 2,
            column,
            f'sticks R  {remote.stick_right_h:4d} '
            f'{remote.stick_right_v:4d}',
        )
        self._safe_add(
            row + 3,
            column,
            f'sticks L  {remote.stick_left_h:4d} '
            f'{remote.stick_left_v:4d}',
        )


def parse_args(arguments=None):
    parser = argparse.ArgumentParser(
        description='SCOUT MINI ROS 2 test console'
    )
    parser.add_argument('--status-topic', default='scout_status')
    parser.add_argument('--odom-topic', default='odom')
    parser.add_argument('--rc-topic', default='rc_status')
    parser.add_argument('--cmd-topic', default='cmd_vel')
    parser.add_argument('--light-topic', default='light_control')
    parser.add_argument('--can-interface', default='can0')
    parser.add_argument('--linear-speed', type=float, default=0.15)
    parser.add_argument('--angular-speed', type=float, default=0.35)
    parser.add_argument('--lateral-speed', type=float, default=0.15)
    parser.add_argument('--deadman-timeout', type=float, default=0.25)
    parser.add_argument('--omni', action='store_true')
    return parser.parse_args(arguments)


def main(arguments=None):
    raw_arguments = (
        sys.argv if arguments is None else [sys.argv[0], *arguments]
    )
    args = parse_args(remove_ros_args(raw_arguments)[1:])
    speeds = (args.linear_speed, args.angular_speed, args.lateral_speed)
    if min(speeds) <= 0.0:
        raise SystemExit('speed values must be positive')
    if args.deadman_timeout <= 0.0:
        raise SystemExit('--deadman-timeout must be positive')
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise SystemExit(
            'scout-test-tui requires an interactive terminal'
        )

    rclpy.init(args=raw_arguments)
    node = None
    try:
        node = ScoutTestNode(args)
        curses.wrapper(
            lambda screen: ScoutConsole(screen, node, args).run()
        )
    finally:
        if node is not None:
            node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
