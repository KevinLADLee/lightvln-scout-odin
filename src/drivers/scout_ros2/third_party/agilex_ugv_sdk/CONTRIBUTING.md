# Contributing

## Report a problem

Open an [issue](https://github.com/Hive-Matrix-AI/agilex_ugv_sdk/issues) with the
SDK revision, compiler, operating system, robot model, and steps to reproduce.
Include the expected result and relevant error codes or CAN frames. Remove
credentials, personal data, and private network details before posting logs.
Never repeat an unsafe motion to collect diagnostic data.

## Submit a change

Target the `main` branch. Keep changes focused and preserve existing license and
attribution notices. Add tests for behavior changes and update the public API
documentation when interfaces change.

Keep the shared core, protocol interfaces, and transport layer independent of
individual model families. Place model-specific APIs and codecs under
`models/<family>/`, with corresponding tests, examples, and protocol references.
ROS integrations belong in each model family's ROS repository, not in this SDK.

Build and test without hardware:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_TESTING=ON -DBUILD_EXAMPLES=ON
cmake --build build --parallel
ctest --test-dir build --output-on-failure
```

Use an injectable `CanTransport` for regression tests. Keep public headers
self-contained and preserve the exported `agilex_ugv_sdk::agilex_ugv_sdk` CMake
target. Format C++ changes using the repository's `.clang-format` configuration.

For a new model, include the protocol source, units and limits, capability
description, and encoding/decoding tests. State which model and firmware were
used for any hardware verification; distinguish those results from offline tests.
