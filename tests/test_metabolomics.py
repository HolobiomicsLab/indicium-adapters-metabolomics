"""Unit tests for MetabolomicsAdapter (base, generic)."""
from __future__ import annotations

import copy

import rdflib
from indicium_adapters import CURRENT_API_VERSION, DomainAdapter, SHACLProvider

from indicium_adapters_metabolomics.metabolomics import MetabolomicsAdapter


def test_satisfies_protocols():
    a = MetabolomicsAdapter()
    assert isinstance(a, DomainAdapter)
    assert isinstance(a, SHACLProvider)


def test_domain_id():
    assert MetabolomicsAdapter().domain_id == "metabolomics"


def test_api_version_matches_core():
    assert MetabolomicsAdapter().api_version == CURRENT_API_VERSION == 1


def test_qualifiers_are_frozenset_with_expected_members():
    a = MetabolomicsAdapter()
    assert isinstance(a.qualifiers, frozenset)
    assert a.qualifiers == frozenset({
        # Claim-level
        "identifies", "quantifies", "is_biomarker_for",
        "discriminates_between", "metabolizes",
        "co_occurs_with", "found_in_organism", "found_in_environment",
        # Study-level (v0.4.0)
        "has_processing_software", "analyzed_with", "acquired_in_mode",
        "chromatographed_on", "uses_mass_analyzer",
        # Study/paper-level (v0.5.0)
        "uses_database", "acquired_from_matrix", "consolidates_dataset",
    })


def test_study_level_qualifiers_present():
    """v0.4.0+v0.5.0: study/paper-level qualifiers cover ASB heuristic
    metabolomics_metadata (processing_software, instrument, ionization_mode,
    chromatography_type, mass_analyzer) plus audit-2 follow-ups
    (uses_database, acquired_from_matrix, consolidates_dataset)."""
    a = MetabolomicsAdapter()
    for q in ("has_processing_software", "analyzed_with", "acquired_in_mode",
              "chromatographed_on", "uses_mass_analyzer",
              "uses_database", "acquired_from_matrix", "consolidates_dataset"):
        assert q in a.qualifiers


def test_ontology_prefixes_keys():
    keys = MetabolomicsAdapter().ontology_prefixes.keys()
    assert "CHEBI" in keys
    assert "HMDB" in keys
    assert "REFMET" in keys
    # v0.3.1: MSV (MassIVE) + MW (Metabolomics Workbench Study) added per audit;
    # ASB metabolomics_metadata.data_accessions are dominated by these prefixes.
    assert "MTBLS" in keys
    assert "MW" in keys
    assert "MSV" in keys
    assert len(keys) == 12


def test_extraction_context_mentions_domain():
    ctx = MetabolomicsAdapter().extraction_context()
    assert "metabolomics" in ctx.lower()
    # name a couple of qualifiers
    assert "identifies" in ctx
    assert "is_biomarker_for" in ctx


def test_enrich_claim_known_compound(base_claim):
    out = MetabolomicsAdapter().enrich_claim(base_claim)
    assert out["ontology_terms"]["subject"] == "CHEBI:17234"
    # cross-refs populated
    assert "xrefs" in out
    # v0.2.0: Wikidata's glucose entry lacks HMDB; pin stable wikidata QID instead
    assert out["xrefs"]["subject"]["wikidata"] == "WD:Q37525"


def test_enrich_claim_unknown_compound_unchanged(base_claim):
    base_claim["subject"] = "not-a-compound"
    out = MetabolomicsAdapter().enrich_claim(base_claim)
    # ontology_terms unchanged for subject; object also unknown
    assert out["ontology_terms"] == {}
    assert "xrefs" not in out or out["xrefs"] == {}


def test_enrich_claim_does_not_mutate_input(base_claim):
    snapshot = copy.deepcopy(base_claim)
    MetabolomicsAdapter().enrich_claim(base_claim)
    assert base_claim == snapshot


def test_enrich_claim_priority_chebi_then_hmdb():
    """When CHEBI is present, it must be picked over HMDB."""
    claim = {
        "subject": "glucose", "qualifier": "identifies", "object": "",
        "ontology_terms": {}, "evidence_id": "x",
    }
    out = MetabolomicsAdapter().enrich_claim(claim)
    assert out["ontology_terms"]["subject"] == "CHEBI:17234"


def test_enrich_claim_preserves_existing_xrefs():
    """Pre-existing xrefs in input are preserved (shallow copy, line 67 branch)."""
    claim = {
        "subject": "glucose", "qualifier": "identifies", "object": "",
        "ontology_terms": {}, "evidence_id": "x",
        "xrefs": {"prior": {"some_id": "ABC123"}},
    }
    out = MetabolomicsAdapter().enrich_claim(claim)
    assert "prior" in out["xrefs"]


def test_shacl_shapes_returns_non_empty_graph():
    g = MetabolomicsAdapter().shacl_shapes()
    assert isinstance(g, rdflib.Graph)
    assert len(g) > 0


def test_enrich_claim_accepts_curie_subject():
    """v0.3.1: subjects that are already CURIEs (e.g. CHEBI:17234) must enrich.

    Audit finding #3: LLM extractors and mzTab SML rows often emit subjects
    directly as CURIEs. The compound TSV ships full cross-references; the
    adapter must serve them on CURIE input, not only on bare names.
    """
    claim = {
        "subject": "CHEBI:17234", "qualifier": "identifies", "object": "",
        "ontology_terms": {}, "evidence_id": "x",
    }
    out = MetabolomicsAdapter().enrich_claim(claim)
    assert out["ontology_terms"]["subject"] == "CHEBI:17234"
    # Cross-refs populated from the same row.
    assert out["xrefs"]["subject"]["wikidata"] == "WD:Q37525"


def test_enrich_claim_accepts_wd_curie_subject():
    """Wikidata QIDs as subjects should also resolve to the cross-ref row."""
    claim = {
        "subject": "WD:Q37525", "qualifier": "identifies", "object": "",
        "ontology_terms": {}, "evidence_id": "x",
    }
    out = MetabolomicsAdapter().enrich_claim(claim)
    # Principal CURIE order picks CHEBI when present.
    assert out["ontology_terms"]["subject"] == "CHEBI:17234"


# --- ontology_term_justifications (SEMAPV) -----------------------------------

def test_enrich_claim_sets_ontology_term_justification_for_subject(base_claim):
    """enrich_claim must populate ontology_term_justifications for every resolved slot."""
    out = MetabolomicsAdapter().enrich_claim(base_claim)
    # base_claim subject="glucose" resolves to CHEBI:17234
    assert "subject" in out.get("ontology_terms", {})
    assert out.get("ontology_term_justifications", {}).get("subject") == "semapv:CompositeMatching"


def test_enrich_claim_justification_only_for_resolved_slots():
    """Slots that do NOT resolve must not appear in ontology_term_justifications."""
    claim = {
        "subject": "glucose", "qualifier": "identifies", "object": "not-a-compound",
        "ontology_terms": {}, "evidence_id": "x",
    }
    out = MetabolomicsAdapter().enrich_claim(claim)
    j = out.get("ontology_term_justifications", {})
    assert "subject" in j          # glucose resolves
    assert "object" not in j       # not-a-compound does not resolve


def test_enrich_claim_justification_does_not_mutate_input(base_claim):
    snapshot = copy.deepcopy(base_claim)
    MetabolomicsAdapter().enrich_claim(base_claim)
    # purity check: the new justifications dict must also be on the output only
    assert "ontology_term_justifications" not in base_claim
    assert base_claim == snapshot
