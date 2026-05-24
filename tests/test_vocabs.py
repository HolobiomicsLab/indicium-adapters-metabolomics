"""Smoke tests for the bundled vocab JSON files."""
from __future__ import annotations

import json
from importlib.resources import files


def _load(name: str) -> dict:
    return json.loads(
        files("indicium_adapters_metabolomics.data").joinpath(name).read_text()
    )


def test_npc_terms_has_known_entries():
    npc = _load("_npc_terms.json")
    assert len(npc) >= 50, f"NPC terms count too small: {len(npc)}"
    keys_lower = {k.lower() for k in npc}
    assert any(k in keys_lower for k in ("terpenoids", "alkaloids", "flavonoids"))


def test_po_terms_has_common_plant_parts():
    po = _load("_po_terms.json")
    assert len(po) >= 30, f"PO terms count too small: {len(po)}"
    keys_lower = {k.lower() for k in po}
    assert "leaf" in keys_lower
    assert any("root" in k for k in keys_lower)


def test_ro_terms_has_interaction_relations():
    ro = _load("_ro_terms.json")
    assert len(ro) >= 5, f"RO terms count too small: {len(ro)}"
    keys_lower = {k.lower() for k in ro}
    assert "pollinates" in keys_lower or "parasite of" in keys_lower


def test_wd_organisms_has_substantial_entries():
    wd = _load("_wd_organisms.json")
    assert len(wd) >= 100, f"WD organisms count too small: {len(wd)}"
    # Each entry should have qid + label
    for _label, info in wd.items():
        assert info["qid"].startswith("Q")
        assert "label" in info


def test_wd_organisms_has_canonical_species():
    """v0.3.0: curated P225 taxon-name lookup ensures key metabolomics-relevant species."""
    wd = _load("_wd_organisms.json")
    # Well-known species from the curated list — should always be present.
    required = ["homo sapiens", "apis mellifera", "arabidopsis thaliana",
                "coffea arabica", "danio rerio"]
    missing = [s for s in required if s not in wd]
    assert not missing, f"Missing expected species in _wd_organisms.json: {missing}"
