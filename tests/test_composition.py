"""Tests for composing the three adapters via compose_adapters()."""
from __future__ import annotations

import copy

import rdflib
from indicium_adapters import DomainAdapter, SHACLProvider, compose_adapters

from indicium_adapters_metabolomics import (
    EMIAdapter,
    MetaboKGAdapter,
    MetabolomicsAdapter,
)


def _three_adapters() -> list[DomainAdapter]:
    return [MetabolomicsAdapter(), MetaboKGAdapter(), EMIAdapter()]


def test_compose_three_yields_composite():
    composite = compose_adapters(_three_adapters())
    assert composite.domain_id == "metabolomics+metabokg+emi"


def test_compose_satisfies_protocols():
    composite = compose_adapters(_three_adapters())
    assert isinstance(composite, DomainAdapter)
    assert isinstance(composite, SHACLProvider)


def test_qualifiers_are_disjoint_across_adapters():
    """Sum of sizes must equal union size — no overlap."""
    m, mk, e = _three_adapters()
    total = len(m.qualifiers) + len(mk.qualifiers) + len(e.qualifiers)
    union = m.qualifiers | mk.qualifiers | e.qualifiers
    assert total == len(union), (
        f"Qualifier overlap detected. Per-adapter sum={total}, union size={len(union)}. "
        f"Overlaps: {(m.qualifiers & mk.qualifiers) | (m.qualifiers & e.qualifiers) | (mk.qualifiers & e.qualifiers)}"
    )


def test_compose_qualifier_union():
    composite = compose_adapters(_three_adapters())
    expected_total = 8 + 7 + 13
    assert len(composite.qualifiers) == expected_total


def test_compose_prefixes_no_value_conflict():
    """Where multiple adapters define the same prefix key, they must agree on the URI."""
    m, mk, e = _three_adapters()
    all_prefixes = (m.ontology_prefixes, mk.ontology_prefixes, e.ontology_prefixes)
    seen: dict[str, str] = {}
    for d in all_prefixes:
        for k, v in d.items():
            if k in seen:
                assert seen[k] == v, f"Prefix {k!r} maps to multiple URIs: {seen[k]!r} vs {v!r}"
            seen[k] = v


def test_compose_enrich_chain_order_calls_all_three():
    """enrich_claim() must be applied by all three adapters in order."""
    composite = compose_adapters(_three_adapters())
    claim = {
        "subject": "glucose",
        "qualifier": "identifies",
        "object": "Q132298",
        "ontology_terms": {},
        "evidence_id": "x",
    }
    out = composite.enrich_claim(claim)
    # MetabolomicsAdapter recognized "glucose" → CHEBI
    assert out["ontology_terms"]["subject"] == "CHEBI:17234"
    # EMIAdapter recognized Wikidata QID in object
    assert out["ontology_terms"]["object"] == "WD:Q132298"


def test_compose_enrich_does_not_mutate_input():
    composite = compose_adapters(_three_adapters())
    claim = {
        "subject": "glucose", "qualifier": "identifies", "object": "",
        "ontology_terms": {}, "evidence_id": "x",
    }
    snap = copy.deepcopy(claim)
    composite.enrich_claim(claim)
    assert claim == snap


def test_compose_shacl_merge_non_empty():
    composite = compose_adapters(_three_adapters())
    g = composite.shacl_shapes()
    assert isinstance(g, rdflib.Graph)
    # Merged graph should be at least as large as any single adapter's graph
    base = MetabolomicsAdapter().shacl_shapes()
    mk = MetaboKGAdapter().shacl_shapes()
    e = EMIAdapter().shacl_shapes()
    assert len(g) >= max(len(base), len(mk), len(e))


def test_compose_extraction_context_includes_all_three():
    composite = compose_adapters(_three_adapters())
    ctx = composite.extraction_context()
    assert "metabolomics" in ctx.lower()
    assert "metabokg" in ctx.lower()
    assert "emi" in ctx.lower()
