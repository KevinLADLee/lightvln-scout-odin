# Contributing

## Before making changes

- Keep ROS package names in `snake_case`; the repository name is `lightvln-scout`.
- Put machine-specific addresses, calibration notes, and local overrides in
  `.local/` or outside the checkout.
- Treat `src/drivers/` as vendored code. Preserve its license files and update
  the relevant `UPSTREAM_VERSION` record when refreshing a snapshot.
- Do not commit `build/`, `install/`, `log/`, virtual environments, caches, or
  Odin runtime data.

## Verify a change

From the repository root:

```bash
./scripts/build.bash
ROS_DOMAIN_ID=199 ROS_LOCALHOST_ONLY=1 ./scripts/test.bash
```

Use an unused ROS domain for tests. Hardware, calibration, and physical motion
must be validated separately with the safety procedure in `docs/hardware.md`.
