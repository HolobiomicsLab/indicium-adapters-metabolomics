"""Unit tests for MetaboKGAdapter (MetaboKG-flavored claims)."""
from __future__ import annotations

import copy

import rdflib
from indicium_adapters import DomainAdapter, SHACLProvider

from indicium_adapters_metabolomics.metabokg import MetaboKGAdapter


def test_satisfies_protocols():
    a = MetaboKGAdapter()
    assert isinstance(a, DomainAdapter)
    assert isinstance(a, SHACLProvider)


def test_domain_id():
    assert MetaboKGAdapter().domain_id == "metabokg"


def test_api_version():
    assert MetaboKGAdapter().api_version == 1


def test_qualifiers_metabokg_specific():
    qs = MetaboKGAdapter().qualifiers
    assert qs == frozenset({
        "spectral_match", "has_annotation_level", "classified_as",
        "annotated_in", "has_feature", "structurally_related_to",
        "shares_fragment_with",
    })


def test_ontology_prefixes_mbs_present():
    keys = MetaboKGAdapter().ontology_prefixes.keys()
    for k in ("MBS", "MBD", "NPC", "MS", "SIO", "PROV", "USI", "NCIT"):
        assert k in keys


def test_extraction_context_mentions_metabokg():
    ctx = MetaboKGAdapter().extraction_context()
    assert "metabokg" in ctx.lower() or "MetaboKG" in ctx


def test_enrich_classified_as_with_known_npc_pathway():
    claim = {
        "subject": "feature_42",
        "qualifier": "classified_as",
        "object": "terpenoids",
        "ontology_terms": {},
        "evidence_id": "x",
    }
    out = MetaboKGAdapter().enrich_claim(claim)
    assert out["ontology_terms"]["object"].startswith("NPC:")


def test_enrich_has_annotation_level_valid():
    claim = {
        "subject": "feature_42", "qualifier": "has_annotation_level",
        "object": "level_2", "ontology_terms": {}, "evidence_id": "x",
    }
    out = MetaboKGAdapter().enrich_claim(claim)
    assert out.get("enum_valid") is True


def test_enrich_has_annotation_level_invalid():
    claim = {
        "subject": "feature_42", "qualifier": "has_annotation_level",
        "object": "level_99", "ontology_terms": {}, "evidence_id": "x",
    }
    out = MetaboKGAdapter().enrich_claim(claim)
    assert out.get("enum_valid") is False


def test_enrich_spectral_match_with_usi(metabokg_claim):
    out = MetaboKGAdapter().enrich_claim(metabokg_claim)
    # USI in object slot should get tagged with USI: CURIE
    assert out["ontology_terms"]["object"].startswith("USI:")


def test_enrich_does_not_mutate_input(metabokg_claim):
    snap = copy.deepcopy(metabokg_claim)
    MetaboKGAdapter().enrich_claim(metabokg_claim)
    assert metabokg_claim == snap


def test_shacl_shapes_returns_graph():
    g = MetaboKGAdapter().shacl_shapes()
    assert isinstance(g, rdflib.Graph)
    assert len(g) > 0
