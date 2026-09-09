"""Exercise deployment with local stand-ins, never a real SSH connection."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "deploy_robot.bash"


@pytest.mark.parametrize("destination", [".", "./", "/", "//", "/./", "a/..", "a/./b", "a//b"])
def test_non_workspace_destinations_are_rejected(tmp_path, destination):
    ssh = tmp_path / "ssh"
    ssh.write_text("#!/bin/sh\nexit 99\n")
    ssh.chmod(0o755)
    result = subprocess.run(["bash", str(SCRIPT)], capture_output=True, env={
        **os.environ, "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "LIGHTNAV_DEPLOY_HOST": "robot.example", "LIGHTNAV_DEPLOY_ROOT": destination,
    })
    assert result.returncode == 2
    assert b"Invalid LIGHTNAV_DEPLOY_ROOT" in result.stderr


def test_real_rsync_never_dereferences_external_links_or_copies_private_env(tmp_path):
    real_rsync = shutil.which("rsync")
    if real_rsync is None:
        pytest.skip("rsync is required for the local deployment transfer test")
    workspace = tmp_path / "workspace"
    (workspace / "scripts").mkdir(parents=True)
    shutil.copy2(SCRIPT, workspace / "scripts" / SCRIPT.name)
    (workspace / "public.txt").write_text("public source")
    private = tmp_path / "private.txt"
    private.write_text("private fixture")
    (workspace / "external-link").symlink_to(private)
    (workspace / "relative-external").symlink_to("../private.txt")
    (workspace / "public-link").symlink_to("public.txt")
    (workspace / ".env.production").write_text("private fixture")
    local = workspace / ".local"
    local.mkdir()
    (local / "calibration.yaml").write_text("private calibration fixture")
    destination = tmp_path / "copy"
    destination.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    # Consume the script's rsync arguments but map the remote destination locally.
    (bin_dir / "ssh").write_text("#!/bin/sh\nexit 0\n")
    (bin_dir / "rsync").write_text(
        '#!/bin/bash\nargs=("$@")\n'
        'args[${#args[@]}-1]="$DEPLOY_TEST_DEST/"\n'
        'exec "$DEPLOY_TEST_RSYNC" "${args[@]}"\n'
    )
    for executable in bin_dir.iterdir():
        executable.chmod(0o755)
    result = subprocess.run(
        ["bash", str(workspace / "scripts" / SCRIPT.name)], capture_output=True, env={
            **os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "LIGHTNAV_DEPLOY_HOST": "robot.example", "LIGHTNAV_DEPLOY_ROOT": "workspace",
            "DEPLOY_TEST_DEST": str(destination), "DEPLOY_TEST_RSYNC": real_rsync,
        },
    )
    assert result.returncode == 0, result.stderr
    assert (destination / "public.txt").read_text() == "public source"
    assert (destination / "public-link").is_symlink()
    assert not os.path.lexists(destination / "external-link")
    assert not os.path.lexists(destination / "relative-external")
    assert not (destination / ".env.production").exists()
    assert not (destination / ".local").exists()
