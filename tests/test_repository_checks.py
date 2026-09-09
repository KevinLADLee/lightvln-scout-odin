"""Regression coverage for the release consistency checks."""

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).parents[1] / "scripts" / "check_repository.py"
SPEC = importlib.util.spec_from_file_location("repository_checks", SCRIPT)
CHECKS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECKS)


def test_document_links_accept_relative_files_and_reject_missing_headings(tmp_path):
    (tmp_path / "guide.md").write_text("# Quick start\n")
    readme = tmp_path / "README.md"
    readme.write_text("[guide](guide.md#quick-start)\n[site](https://example.org)\n")
    assert CHECKS.documentation_errors(readme, tmp_path) == []
    readme.write_text("[guide](guide.md#missing)\n[outside](../outside.md)\n")
    assert len(CHECKS.documentation_errors(readme, tmp_path)) == 2


def test_generated_and_private_files_are_rejected_without_reading_contents():
    paths = [".env.production", ".local/calibration.yaml", "build/cmake.log", "id_ed25519"]
    assert len(CHECKS.tracked_path_errors(paths)) == len(paths)
    assert CHECKS.tracked_path_errors([".env.example", "src/module.py"]) == []


def test_placeholder_maintainer_blocks_release_metadata(tmp_path):
    (tmp_path / "package.xml").write_text("""<package>
      <name>sample</name><version>0.1.0</version><description>Sample</description>
      <license>Apache-2.0</license><maintainer email="person@example.com">Person</maintainer>
    </package>""")
    assert any("placeholder" in error for error in CHECKS.package_errors(tmp_path))
    assert any("LICENSE" in error for error in CHECKS.package_errors(tmp_path))


def test_deployed_source_snapshot_does_not_require_git(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(CHECKS, "__file__", str(tmp_path / "scripts/check_repository.py"))
    for name in CHECKS.REQUIRED_FILES:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("")
    package = tmp_path / "src/integration/lightvln_scout"
    package.mkdir(parents=True)
    (package / "package.xml").write_text('''<package>
      <name>sample</name><version>0.1.0</version><description>Sample</description>
      <license>Apache-2.0</license>
      <maintainer email="kevinladlee@gmail.com">KevinLADLee</maintainer>
    </package>''')
    for name in ("LICENSE", "NOTICE"):
        (package / name).touch()
    assert CHECKS.main() == 0
    assert "without .git" in capsys.readouterr().out
