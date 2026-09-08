"""Deployment must never select a developer's machine implicitly."""

import os
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "deploy_robot.bash"


@pytest.fixture
def deployment_env(tmp_path):
    calls = tmp_path / "calls"
    for name in ("ssh", "rsync"):
        executable = tmp_path / name
        executable.write_text(
            '#!/bin/sh\nprintf "%s\\n" "$0" "$@" >> "$DEPLOY_TEST_CALLS"\n'
        )
        executable.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "DEPLOY_TEST_CALLS": str(calls),
    }
    env.pop("LIGHTNAV_DEPLOY_HOST", None)
    env.pop("LIGHTNAV_DEPLOY_ROOT", None)
    return env, calls


def test_no_destination_never_attempts_a_connection(deployment_env):
    env, calls = deployment_env
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True)
    assert result.returncode == 2
    assert b"LIGHTNAV_DEPLOY_HOST" in result.stderr
    assert not calls.exists()


def test_help_works_without_destination_or_connection(deployment_env):
    env, calls = deployment_env
    result = subprocess.run(
        ["bash", str(SCRIPT), "--help"], env=env, capture_output=True
    )
    assert result.returncode == 0
    assert not calls.exists()


@pytest.mark.parametrize("variable,value", [
    ("LIGHTNAV_DEPLOY_HOST", "-oProxyCommand=unexpected"),
    ("LIGHTNAV_DEPLOY_ROOT", "workspace'; touch unexpected; '"),
    ("LIGHTNAV_DEPLOY_ROOT", "../outside"),
])
def test_invalid_destination_is_rejected_before_ssh(deployment_env, variable, value):
    env, calls = deployment_env
    env["LIGHTNAV_DEPLOY_HOST"] = "robot-user@robot.example"
    env[variable] = value
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True)
    assert result.returncode == 2
    assert not calls.exists()


def test_explicit_host_uses_remote_home_and_excludes_private_data(deployment_env):
    env, calls = deployment_env
    env["LIGHTNAV_DEPLOY_HOST"] = "robot-user@robot.example"
    result = subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True)
    assert result.returncode == 0, result.stderr
    arguments = calls.read_text().splitlines()
    assert "robot-user@robot.example:lightvln-scout/" in arguments
    assert "--exclude=.local/" in arguments
    assert "--exclude=.backups/" in arguments
    assert "--exclude=image/" in arguments
    assert "--exclude=src/odin_ros_driver/" in arguments
