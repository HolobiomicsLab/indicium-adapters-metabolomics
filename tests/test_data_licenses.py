"""The bundled data files carry a licence notice that ships in the wheel, and
the documentation names only the sources the data is actually built from."""
from __future__ import annotations

import re
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_PKG = _ROOT / "src" / "indicium_adapters_metabolomics"
_DATA = _PKG / "data"
_NOTICE = _ROOT / "DATA_LICENSES.md"
_WHEEL_PATH = "indicium_adapters_metabolomics/data/DATA_LICENSES.md"


def _bundled_data_files() -> list[str]:
    return sorted(
        p.name for p in _DATA.iterdir()
        if p.is_file() and p.suffix in {".json", ".tsv"} and not p.name.startswith(".")
    )


def test_data_licenses_notice_exists():
    assert _NOTICE.is_file()


def test_every_bundled_data_file_is_listed():
    text = _NOTICE.read_text(encoding="utf-8")
    missing = [name for name in _bundled_data_files() if f"`{name}`" not in text]
    assert not missing, f"DATA_LICENSES.md does not list {missing}"


def test_notice_states_the_required_licences():
    text = _NOTICE.read_text(encoding="utf-8")
    for needle in (
        "CC BY 4.0",  # Plant Ontology
        "Copyright (c) 2026 The Earth Metabolome Initiative",  # NPClassifier labels
        "CC0 1.0",  # Wikidata and RO
        "Metabolomics Workbench",  # RefMet
        "CC BY 3.0",  # UBERON
    ):
        assert needle in text, f"DATA_LICENSES.md lacks {needle!r}"


def test_wheel_force_includes_the_notice():
    with (_ROOT / "pyproject.toml").open("rb") as fh:
        wheel = tomllib.load(fh)["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel.get("force-include", {}).get("DATA_LICENSES.md") == _WHEEL_PATH


def test_no_bridgedb_data_claim_in_docs_or_docstrings():
    # BridgeDb is not a source of any bundled file. The software registry may
    # still list "BridgeDb" as a database name that papers mention.
    paths = [_ROOT / "README.md", _ROOT / "CLAUDE.md", *sorted(_PKG.rglob("*.py"))]
    hits = [
        f"{p.relative_to(_ROOT)}:{i}"
        for p in paths
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
        if re.search(r"bridgedb", line, re.IGNORECASE)
    ]
    assert not hits, f"BridgeDb named as a data source in {hits}"
