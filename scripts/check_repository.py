#!/usr/bin/env python3
"""Check repository hygiene, local documentation links, and package metadata.

This is an offline consistency check, not a license or secret-scanning audit.
"""

from __future__ import annotations

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED_FILES = (
    "README.md",
    "README.zh-CN.md",
    "LICENSE",
    "NOTICE",
    "LICENSES.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "docs/hardware.md",
    "docs/web-adapter.md",
    ".github/workflows/ci.yml",
    "src/lightnav/UPSTREAM_VERSION",
)
PRIVATE_PARTS = {".venv", ".local", ".backups", ".gitnexus", "__pycache__"}


def heading_ids(markdown: str) -> set[str]:
    """Handle the plain Markdown headings used by the project documentation."""
    counts: dict[str, int] = {}
    anchors = set()
    for heading in re.findall(r"^#{1,6}\s+(.+?)\s*#*\s*$", markdown, re.MULTILINE):
        slug = re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")
        count = counts.get(slug, 0)
        anchors.add(f"{slug}-{count}" if count else slug)
        counts[slug] = count + 1
    return anchors


def documentation_errors(path: Path, root: Path) -> list[str]:
    content = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
    errors = []
    for raw in re.findall(r"\]\(<?([^\s)>]+)>?(?:\s+\"[^\"]*\")?\)", content):
        link = urlsplit(raw)
        if link.scheme or link.netloc:
            continue
        target = (path.parent / unquote(link.path)).resolve() if link.path else path.resolve()
        if not target.is_relative_to(root.resolve()) or not target.exists():
            errors.append(f"{path.relative_to(root)}: missing or external local link {raw}")
        elif target.suffix == ".md" and link.fragment:
            if unquote(link.fragment) not in heading_ids(target.read_text(encoding="utf-8")):
                errors.append(f"{path.relative_to(root)}: missing heading {raw}")
    return errors


def package_errors(package: Path) -> list[str]:
    errors = []
    try:
        manifest = ET.parse(package / "package.xml").getroot()
    except (ET.ParseError, OSError) as exc:
        return [f"{package.name}: invalid package.xml: {exc}"]
    for field in ("name", "version", "description", "license"):
        if not manifest.findtext(field, "").strip():
            errors.append(f"{package.name}: missing {field}")
    maintainers = manifest.findall("maintainer")
    if not maintainers or any(
        not item.get("email") or "@example." in item.get("email", "") for item in maintainers
    ):
        errors.append(f"{package.name}: missing or placeholder maintainer email")
    for name in ("LICENSE", "NOTICE"):
        if not (package / name).is_file():
            errors.append(f"{package.name}: missing {name}")
    return errors


def tracked_path_errors(paths: list[str]) -> list[str]:
    errors = []
    for name in paths:
        path = Path(name)
        if (
            PRIVATE_PARTS.intersection(path.parts)
            or path.parts[0] in {"build", "install", "log"}
            or (path.name.startswith(".env") and path.name != ".env.example")
            or path.name in {"id_rsa", "id_ed25519"}
        ):
            errors.append(f"private or generated file tracked by Git: {name}")
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    errors = [
        f"missing required file: {name}" for name in REQUIRED_FILES if not (root / name).is_file()
    ]
    docs = [
        root / name
        for name in (
            "README.md",
            "README.zh-CN.md",
            "LICENSES.md",
            "CONTRIBUTING.md",
            "SECURITY.md",
        )
    ]
    docs += sorted((root / "docs").glob("*.md"))
    for path in docs:
        if path.is_file():
            errors.extend(documentation_errors(path, root))
    for package in [
        root / "src/integration/lightvln_scout",
        *sorted((root / "src/lightnav").glob("vln_*")),
    ]:
        errors.extend(package_errors(package))
    if (root / ".git").exists():
        tracked = (
            subprocess.run(
                ["git", "ls-files", "-z"],
                cwd=root,
                capture_output=True,
                check=True,
            )
            .stdout.decode()
            .split("\0")
        )
        errors.extend(tracked_path_errors([name for name in tracked if name]))
    else:
        print("Source snapshot without .git: skipping the tracked-file check")
    if errors:
        print(
            "Repository checks failed:\n" + "\n".join(f"  {error}" for error in errors),
            file=sys.stderr,
        )
        return 1
    print("Repository consistency checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
