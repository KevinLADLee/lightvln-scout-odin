#!/usr/bin/env python3
"""Validate the mixed ROS system-site + uv overlay Python environment."""

from __future__ import annotations

import importlib
import importlib.metadata
import sys
import warnings
from pathlib import Path

try:
    from packaging.requirements import Requirement
except ImportError as exc:
    print(f"packaging: {exc}", file=sys.stderr)
    raise SystemExit(1) from exc


IMPORT_NAMES = {
    "pyyaml": "yaml",
    "scikit-learn": "sklearn",
}


def requirements(path: Path):
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", maxsplit=1)[0].strip()
        if line and not line.startswith("-"):
            yield Requirement(line)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    requested = []
    for filename in ("requirements.txt", "requirements-dev.txt"):
        requested.extend(requirements(root / filename))
    failures = []
    for item in requested:
        distribution = item.name
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"{distribution}: distribution not installed")
            continue
        if item.specifier and not item.specifier.contains(version):
            failures.append(f"{distribution}: {version} does not satisfy {item.specifier}")
            continue
        module = IMPORT_NAMES.get(distribution.lower(), distribution.replace("-", "_"))
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                importlib.import_module(module)
        except Exception as exc:  # noqa: BLE001 - dependency imports raise arbitrary errors
            failures.append(f"{module}: {exc}")

    if failures:
        print("Python dependency validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"  {failure}", file=sys.stderr)
        return 1
    print("Python dependency versions and imports validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
