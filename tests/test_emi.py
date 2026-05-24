"""Unit tests for EMIAdapter (ENPKG + METRIN-KG)."""
from __future__ import annotations

import copy

import rdflib
from indicium_adapters import DomainAdapter, SHACLProvider

from indicium_adapters_metabolomics.emi import EMIAdapter


def test_satisfies_protocols():
    a = EMIAdapter()
    assert isinstance(a, DomainAdapter)
    assert isinstance(a, SHACLProvider)


def test_domain_id():
    assert EMIAdapter().domain_id == "emi"


def test_api_version():
    assert EMIAdapter().api_version == 1


def test_qualifiers_cover_enpkg_and_metrin():
    qs = EMIAdapter().qualifiers
    enpkg = {"annotates_spectrum", "has_chemical_class", "found_in_species",
             "cosine_similarity", "in_extract_sample"}
    metrin = {"mediates_interaction", "interacts_with", "parasitizes",
              "pollinates", "associated_with_trait", "found_in_plant_part",
              "has_developmental_stage", "has_phenotype"}
    assert enpkg.issubset(qs)
    assert metrin.issubset(qs)


def test_ontology_prefixes_emi_present():
    keys = EMIAdapter().ontology_prefixes.keys()
    for k in ("emi", "emiBox", "emiUnit", "NPC", "sosa", "WD",
              "qudt", "qudtUnit", "RO", "UBERON", "PATO", "PO",
              "ENVO", "USI", "InChIKey"):
        assert k in keys


def test_extraction_context_mentions_emi():
    ctx = EMIAdapter().extraction_context()
    assert "emi" in ctx.lower() or "Earth Metabolome" in ctx


def test_enrich_wikidata_qid_in_subject(emi_interaction_claim):
    out = EMIAdapter().enrich_claim(emi_interaction_claim)
    assert out["ontology_terms"]["subject"] == "WD:Q132298"
    assert out["ontology_terms"]["object"] == "WD:Q156495"


def test_enrich_found_in_plant_part_known():
    claim = {
        "subject": "compound_x",
        "qualifier": "found_in_plant_part",
        "object": "leaf",
        "ontology_terms": {},
        "evidence_id": "x",
    }
    out = EMIAdapter().enrich_claim(claim)
    assert out["ontology_terms"]["object"].startswith("PO:")


def test_enrich_interaction_type_known():
    claim = {
        "subject": "honey bee",
        "qualifier": "mediates_interaction",
        "object": "pollinates",
        "ontology_terms": {},
        "evidence_id": "x",
    }
    out = EMIAdapter().enrich_claim(claim)
    # Should resolve "pollinates" to an RO or emi: CURIE
    assert out["ontology_terms"]["object"].startswith(("RO:", "emi:"))


def test_enrich_does_not_mutate_input(emi_interaction_claim):
    snap = copy.deepcopy(emi_interaction_claim)
    EMIAdapter().enrich_claim(emi_interaction_claim)
    assert emi_interaction_claim == snap


def test_shacl_shapes_returns_graph():
    g = EMIAdapter().shacl_shapes()
    assert isinstance(g, rdflib.Graph)
    assert len(g) > 0


def test_enrich_wd_organism_by_label():
    """A common organism name from the bundled WD list should resolve to WD:Qxxx."""
    import json
    from importlib.resources import files
    wd = json.loads(
        files("indicium_adapters_metabolomics.data").joinpath("_wd_organisms.json").read_text()
    )
    # Pick any known organism label from the bundled JSON
    sample_label = next(iter(wd.keys()))
    sample_qid = wd[sample_label]["qid"]
    claim = {
        "subject": sample_label,   # use the label as-is (lowercase)
        "qualifier": "found_in_species",
        "object": "",
        "ontology_terms": {},
        "evidence_id": "x",
    }
    out = EMIAdapter().enrich_claim(claim)
    assert out["ontology_terms"].get("subject") == f"WD:{sample_qid}"
