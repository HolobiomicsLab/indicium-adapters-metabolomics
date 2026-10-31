"""One version per package: pyproject, __version__, CITATION.cff, the top
CHANGELOG heading and the SECURITY.md support table must agree."""
from __future__ import annotations

import re
import tomllib
from importlib.metadata import version
from pathlib import Path

import indicium_adapters_metabolomics

_ROOT = Path(__file__).resolve().parents[1]
_DIST = "indicium-adapters-metabolomics"


def _pyproject_version() -> str:
    with (_ROOT / "pyproject.toml").open("rb") as fh:
        return tomllib.load(fh)["project"]["version"]


def test_dunder_version_comes_from_installed_metadata():
    assert indicium_adapters_metabolomics.__version__ == version(_DIST)


def test_dunder_version_equals_pyproject():
    assert indicium_adapters_metabolomics.__version__ == _pyproject_version()


def test_citation_version_equals_pyproject():
    text = (_ROOT / "CITATION.cff").read_text(encoding="utf-8")
    match = re.search(r"^version:\s*\"?([^\"\s]+)\"?\s*$", text, re.MULTILINE)
    assert match, "CITATION.cff has no top-level version: line"
    assert match.group(1) == _pyproject_version()


def test_top_changelog_release_heading_equals_pyproject():
    text = (_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## \[(\d+\.\d+\.\d+)\]", text, re.MULTILINE)
    assert headings, "CHANGELOG.md has no released version heading"
    assert headings[0] == _pyproject_version()


def test_security_table_supports_the_current_minor():
    major, minor, _ = _pyproject_version().split(".")
    text = (_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    row = re.search(
        rf"^\|\s*{major}\.{minor}\.x\s*\|\s*yes\s*\|", text, re.MULTILINE
    )
    assert row, f"SECURITY.md does not list {major}.{minor}.x as supported"
