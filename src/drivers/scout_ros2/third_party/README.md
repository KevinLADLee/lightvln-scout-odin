# SDK dependency

[`agilex_ugv_sdk`](agilex_ugv_sdk/README.md) is a general-purpose SDK for new
AgileX mobile robot models, currently implementing SCOUT MINI and SCOUT MINI OMNI.
It is included here as a Git submodule for this driver's SCOUT integration.
Initialize the revision recorded by this repository from the repository root:

```bash
git submodule update --init --recursive
```

The driver links the exported `agilex_ugv_sdk::agilex_ugv_sdk` CMake target.
Colcon discovers the SDK as a standard CMake package in this directory.
SCOUT ROS nodes and diagnostics are provided by `scout_base`.
For a separately installed or sibling SDK package, omit the nested checkout to
avoid duplicate packages.

The SDK is licensed under [Apache-2.0](agilex_ugv_sdk/LICENSE).
