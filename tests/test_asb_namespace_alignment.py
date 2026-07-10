"""Guard: the SHACL shapes must bind ``asb:`` to the base indicium targets.

The three shape files hardcode the ``asb:`` base as a literal ``@prefix``. If a
future base move updates indicium but misses a shapes file, that shape stops
matching the graph, pyshacl reports ``conforms=True`` against zero constraints,
and every invalid claim passes — a silent fail-open. ``test_shacl_claims`` only
pins the synthetic *data* graph, not the shapes, so this is the tripwire.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from indicium import ASB_BASE

_PKG = Path(__file__).resolve().parents[1] / "src" / "indicium_adapters_metabolomics"
SHAPES_DIR = _PKG / "shapes"
SHAPE_FILES = ("metabolomics.shapes.ttl", "metabokg.shapes.ttl", "emi.shapes.ttl")
PREFIX_RE = re.compile(r"(?:@prefix|PREFIX)\s+asb:\s+<([^>]+)>")


@pytest.mark.parametrize("shape_file", SHAPE_FILES)
def test_shape_binds_asb_to_indicium_base(shape_file: str) -> None:
    text = (SHAPES_DIR / shape_file).read_text()
    bases = PREFIX_RE.findall(text)
    assert bases, f"no asb: prefix declared in {shape_file}"
    for base in bases:
        assert base == ASB_BASE, f"{shape_file}: asb: bound to {base}, not {ASB_BASE}"


def test_no_shape_references_a_dead_base() -> None:
    """The base moved off two hosts nobody registered — neither may reappear."""
    # split so this guard scans itself without matching
    dead = ("asb.holobiomics" + ".org", "holobiomicslab" + ".eu/ns/asb")
    offenders = [
        f.name
        for f in SHAPES_DIR.glob("*.ttl")
        if any(host in f.read_text() for host in dead)
    ]
    assert offenders == []


if __name__ == "__main__":
    print("indicium ASB_BASE =", ASB_BASE)
    for name in SHAPE_FILES:
        print(f"  {name:26s} {PREFIX_RE.findall((SHAPES_DIR / name).read_text())}")
