# Licensing and third-party code

This repository contains components under different licenses. Project-owned
integration code, root documentation, scripts, and repository tooling use
**Apache-2.0**, as selected by the project maintainer;
see [LICENSE](LICENSE) and [NOTICE](NOTICE). This default does not replace the
licenses of upstream-derived components or files carrying their own notices.

| Scope | License or notice |
| --- | --- |
| Root documentation, scripts, tests and repository tooling | Apache-2.0 |
| `src/integration/lightvln_scout/` | Apache-2.0; package `LICENSE`, `NOTICE`, and `web/NOTICE` retain the upstream Web UI attribution |
| `src/lightnav/` | Apache-2.0; each ROS package includes `LICENSE` and `NOTICE`; baseline in `UPSTREAM_VERSION` |
| `src/drivers/odin_ros_driver/` | Upstream declares Apache-2.0; see its `LICENSE` and `UPSTREAM_VERSION`; precompiled SDK boundary below |
| `src/drivers/scout_ros2/` | Apache-2.0 except the wheel Xacro files below; see `LICENSE`, `NOTICE`, and `UPSTREAM_VERSION` |
| `src/drivers/scout_ros2/scout_description/urdf/scout_wheel_type1.xacro` and `scout_wheel_type2.xacro` | BSD-3-Clause; full terms and Clearpath Robotics / Weston Robot attribution are embedded in each file |
| `src/drivers/scout_ros2/third_party/agilex_ugv_sdk/` | Apache-2.0; see its `LICENSE` |

The complete standard text is also available in
[Apache-2.0](LICENSES/Apache-2.0.txt).
When redistributing a subset, preserve the applicable license headers, notices,
version records and license texts. Python ROS packages install these into
`share/<package>/` along with their manifests.

## Odin precompiled SDK

The [Odin upstream repository](https://github.com/manifoldsdk/odin_ros_driver)
ships two precompiled archives and declares
[Apache-2.0](https://github.com/manifoldsdk/odin_ros_driver/blob/a592cf2cc08bc8bfb0dceae44ef31f3a6bd77822/LICENSE).
This integration preserves that declaration, the original copyright notices,
and the snapshot record. No separate SDK license or exception was found in the
vendored snapshot. Its upstream repository license is the recorded licensing
basis for these components.

On 2026-09-09, the bundled license and both archives were fetched from the
official repository at `a592cf2cc08bc8bfb0dceae44ef31f3a6bd77822` and compared
with this checkout. All three files were byte-identical.

This checkout does not include the archives' implementation source, so the
complete hardware stack cannot be rebuilt entirely from this source tree.
Keep this build limitation distinct from the upstream license declaration.

| Archive in `src/drivers/odin_ros_driver/lib/` | SHA-256 |
| --- | --- |
| `liblydHostApi_amd.a` | `7b9a29096a00335cdb99eb7899e77f8e994c476a3b6b55421bbf885abadfb7f9` |
| `liblydHostApi_arm.a` | `837dd62b9ceb8475c8cc4ac69df4dcd6183496727884ee56c2b1baf7ab6508c2` |

These hashes identify the bundled bytes. Keep the upstream license and notices
with the archives when redistributing them.

## External dependencies

ROS, CasADi and its solver libraries, Python dependencies, GPU inference
software, and model weights retain their respective upstream licenses. They
are installed separately, not relicensed by this repository. Record resolved
versions and preserve their notices when preparing environments or containers
for redistribution. The model service and weights come from
[LightNav-0](https://github.com/lightorigins/LightNav-0).
