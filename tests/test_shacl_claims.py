"""End-to-end SHACL tests: validate synthetic asb:Claim graphs against each
adapter's bundled shapes.

Pyshacl 0.31.0 quirks documented here for future maintainers:
- sh:Warning results make conforms=False by default; pass allow_warnings=True
  to make warnings non-fatal — BUT this flag is currently INEFFECTIVE for
  sh:Warning results that come from a sh:sparql constraint (MetaboKG and EMI
  conditional shapes use sh:sparql). For those, conforms will be False whenever
  the warning fires, regardless of allow_warnings. The shape's severity in the
  results graph is still correctly sh:Warning, just the conformance flag isn't
  suppressed. Adjust expectations in tests accordingly.
- advanced=True and sparql_mode=True are required for sh:sparql constraints
  to evaluate; without them pyshacl silently skips them.
- sh:condition is parsed by pyshacl only for SHACL rules (sh:rule), not for
  NodeShape constraint filtering; sh:sparql is the correct portable pattern.
"""
from __future__ import annotations

import pyshacl
import rdflib

from indicium_adapters_metabolomics import (
    EMIAdapter,
    MetaboKGAdapter,
    MetabolomicsAdapter,
)

ASB = "https://asb.holobiomics.org/ns/asb#"


def _claim_graph(triples: list[tuple[str, str, str]]) -> rdflib.Graph:
    """Build a tiny graph of asb:Claim assertions from (s,p,o) tuples (all CURIE-strings or literals)."""
    g = rdflib.Graph()
    g.bind("asb", ASB)
    for s, p, o in triples:
        s_node = rdflib.URIRef(s if s.startswith("http") else f"{ASB}{s}")
        p_node = rdflib.URIRef(p if p.startswith("http") else f"{ASB}{p}")
        if o.startswith(("http", "asb:")):
            o_node = rdflib.URIRef(o.replace("asb:", ASB) if o.startswith("asb:") else o)
        else:
            o_node = rdflib.Literal(o)
        g.add((s_node, p_node, o_node))
    # Type the subject as asb:Claim
    if triples:
        s0 = rdflib.URIRef(triples[0][0] if triples[0][0].startswith("http") else f"{ASB}{triples[0][0]}")
        g.add((s0, rdflib.RDF.type, rdflib.URIRef(f"{ASB}Claim")))
    return g


def test_metabolomics_conforming_claim_passes():
    data = _claim_graph([
        ("claim/1", "subject_ontology_term", "CHEBI:17234"),
        ("claim/1", "object_ontology_term", "ENVO:00002005"),
    ])
    shapes = MetabolomicsAdapter().shacl_shapes()
    conforms, _, _ = pyshacl.validate(data_graph=data, shacl_graph=shapes,
                                       inference="none", advanced=False)
    assert conforms is True


def test_metabolomics_malformed_curie_warns():
    """An unrecognised prefix triggers the sh:Warning shape; with allow_warnings=True
    conforms stays True but the report names the unrecognised value."""
    data = _claim_graph([
        ("claim/2", "subject_ontology_term", "WEIRD:12345"),
    ])
    shapes = MetabolomicsAdapter().shacl_shapes()
    # allow_warnings=True: sh:Warning results do not flip conforms to False
    conforms, _, report = pyshacl.validate(data_graph=data, shacl_graph=shapes,
                                            inference="none", advanced=False,
                                            allow_warnings=True)
    assert conforms is True
    assert "MetabolomicsClaimCurieShape" in report or "WEIRD" in report


def test_metabokg_annotation_level_valid_passes():
    data = _claim_graph([
        ("claim/3", "qualifier", "has_annotation_level"),
        ("claim/3", "object", "level_2"),
    ])
    shapes = MetaboKGAdapter().shacl_shapes()
    conforms, _, _ = pyshacl.validate(data_graph=data, shacl_graph=shapes,
                                       inference="none", advanced=True,
                                       sparql_mode=True)
    assert conforms is True


def test_metabokg_annotation_level_invalid_violates():
    data = _claim_graph([
        ("claim/4", "qualifier", "has_annotation_level"),
        ("claim/4", "object", "level_99"),
    ])
    shapes = MetaboKGAdapter().shacl_shapes()
    conforms, _, report = pyshacl.validate(data_graph=data, shacl_graph=shapes,
                                            inference="none", advanced=True,
                                            sparql_mode=True)
    assert conforms is False
    assert "AnnotationLevelShape" in report or "level_1" in report


def test_emi_mediates_interaction_with_qid_passes():
    data = _claim_graph([
        ("claim/5", "qualifier", "mediates_interaction"),
        ("claim/5", "subject_ontology_term", "WD:Q132298"),
        ("claim/5", "object_ontology_term", "WD:Q156495"),
    ])
    shapes = EMIAdapter().shacl_shapes()
    conforms, _, _ = pyshacl.validate(data_graph=data, shacl_graph=shapes,
                                       inference="none", advanced=True,
                                       sparql_mode=True)
    assert conforms is True


def test_metabokg_spectral_match_bad_object_warns():
    """spectral_match with non-USI/InChIKey/CHEBI object should warn."""
    data = _claim_graph([
        ("claim/6", "qualifier", "spectral_match"),
        ("claim/6", "object_ontology_term", "WEIRD:not-a-spectrum"),
    ])
    shapes = MetaboKGAdapter().shacl_shapes()
    conforms, _, report = pyshacl.validate(
        data_graph=data, shacl_graph=shapes,
        inference="none", advanced=True, sparql_mode=True,
    )
    # sh:sparql warning makes conforms=False in pyshacl 0.31.0 even with allow_warnings
    assert conforms is False
    assert "SpectralMatch" in report or "WEIRD" in report


def test_metabokg_classified_as_bad_prefix_warns():
    """classified_as with non-NPC/ClassyFire object_ontology_term should warn."""
    data = _claim_graph([
        ("claim/7", "qualifier", "classified_as"),
        ("claim/7", "object_ontology_term", "CHEBI:17234"),
    ])
    shapes = MetaboKGAdapter().shacl_shapes()
    conforms, _, report = pyshacl.validate(
        data_graph=data, shacl_graph=shapes,
        inference="none", advanced=True, sparql_mode=True,
    )
    assert conforms is False
    assert "ClassifiedAs" in report or "NPC" in report or "ClassyFire" in report


def test_metabokg_classified_as_npc_prefix_passes():
    """classified_as with NPC: prefix should pass."""
    data = _claim_graph([
        ("claim/8", "qualifier", "classified_as"),
        ("claim/8", "object_ontology_term", "NPC:0000001"),
    ])
    shapes = MetaboKGAdapter().shacl_shapes()
    conforms, _, _ = pyshacl.validate(
        data_graph=data, shacl_graph=shapes,
        inference="none", advanced=True, sparql_mode=True,
    )
    assert conforms is True


def test_emi_mediates_interaction_without_qid_warns():
    """mediates_interaction with neither subj nor obj as WD:Q should warn."""
    data = _claim_graph([
        ("claim/9", "qualifier", "mediates_interaction"),
        ("claim/9", "subject_ontology_term", "CHEBI:17234"),
        ("claim/9", "object_ontology_term", "ENVO:00002005"),
    ])
    shapes = EMIAdapter().shacl_shapes()
    conforms, _, report = pyshacl.validate(
        data_graph=data, shacl_graph=shapes,
        inference="none", advanced=True, sparql_mode=True,
    )
    assert conforms is False
    assert "MediatesInteraction" in report or "Wikidata" in report


def test_emi_found_in_species_with_ncbi_taxon_passes():
    """found_in_species with NCBITaxon: prefix should pass."""
    data = _claim_graph([
        ("claim/10", "qualifier", "found_in_species"),
        ("claim/10", "object_ontology_term", "NCBITaxon:9606"),
    ])
    shapes = EMIAdapter().shacl_shapes()
    conforms, _, _ = pyshacl.validate(
        data_graph=data, shacl_graph=shapes,
        inference="none", advanced=True, sparql_mode=True,
    )
    assert conforms is True
