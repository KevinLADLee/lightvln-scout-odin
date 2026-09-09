# Contributing

This project integrates LightNav-0 with Scout Mini and Odin1. Follow the
[README](README.md) for installation. Keep hardware-specific behavior in
`src/integration/lightvln_scout/` and changes to upstream-derived code small.

## Changes and upstream updates

- Preserve upstream interfaces, licenses, notices, and original authorship.
- Compare against a pinned upstream revision before refreshing a snapshot.
  Record the new revision and required local patches in its `UPSTREAM_VERSION`.
  LightNav's baseline and patches are in [this record](src/lightnav/UPSTREAM_VERSION).
- Avoid unrelated formatting changes to vendored code. Keep the English and
  Chinese README commands aligned.
- Store credentials, calibration, logs and machine settings in `.local/` or
  outside the checkout; do not commit generated files.
- Project-owned contributions use Apache-2.0; see [the license map](LICENSES.md).

## Build and test

From the repository root after installation:

```bash
./scripts/build.bash
./scripts/test.bash
source scripts/env.bash
ctest --test-dir build/agilex_ugv_sdk --output-on-failure
.venv/bin/python -m pytest -q src/drivers/scout_ros2/scout_base/test
```

The main test script runs Ruff, repository checks and Python tests. It defaults
to localhost-only ROS domain 199; select another unused domain if necessary.
Tests require local sockets; install `rsync` for the source-transfer regression.
For documentation-only changes, run `python3 scripts/check_repository.py`.
GitHub CI uses the same build and test commands. Record any skipped checks;
physical motion requires separate [hardware validation](docs/hardware.md#enable-motion-after-validation).

## Sync source to a robot

From the development computer, set the SSH destination and copy the source:

```bash
LIGHTNAV_DEPLOY_HOST='<user>@<robot-host>' ./scripts/deploy_robot.bash
```

The default destination is `~/lightvln-scout-odin` on the robot. Set
`LIGHTNAV_DEPLOY_ROOT` to use another workspace directory. The script excludes
`.local/`, backups, and build outputs; it does not delete remote files.
Keep robot calibration and machine settings in a [local preset](docs/hardware.md#parameter-presets)
so source synchronization does not overwrite them. After syncing, run
`./scripts/bootstrap.bash --rosdep` in the destination on the robot.
Authentication options are listed by `./scripts/deploy_robot.bash --help`.

## Report a problem

Include the commit, OS/ROS versions, reproduction steps and sanitized logs in
an issue or pull request. Describe the behavior change and checks performed.
Report vulnerabilities privately using [SECURITY.md](SECURITY.md).
