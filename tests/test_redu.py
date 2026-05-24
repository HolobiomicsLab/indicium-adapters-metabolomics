"""Tests for the ReDU /filename → asb:Claim parser.

Offline tests run against `tests/fixtures/redu_sample_response.json`, a
synthetic response shaped after ReDU's documented sample-metadata schema.

A live-smoke test is gated on `INDICIUM_LIVE_TESTS=1` so CI doesn't depend on
the ReDU endpoint being up — at the time this module was written ReDU was
returning 503 for the canonical query the user supplied.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from indicium_adapters_metabolomics.redu import (
    redu_lookup,
    redu_sample_to_claims,
    redu_to_claims,
)

FIXTURE = Path(__file__).parent / "fixtures" / "redu_sample_response.json"
SAMPLE = json.loads(FIXTURE.read_text(encoding="utf-8"))
STUDY = "study:msv082048"


# --- redu_sample_to_claims (pure projection) -------------------------------

def test_projects_organism_with_ncbitaxon_curie():
    claims = redu_sample_to_claims(SAMPLE, STUDY)
    org = [c for c in claims if c["qualifier"] == "found_in_organism"]
    assert len(org) == 1
    assert org[0]["object"] == "NCBITaxon:9606"
    assert org[0]["ontology_terms"]["object"] == "NCBITaxon:9606"


def test_projects_matrix_prefers_uberon_when_present():
    claims = redu_sample_to_claims(SAMPLE, STUDY)
    m = [c for c in claims if c["qualifier"] == "acquired_from_matrix"]
    assert len(m) == 1
    # Object is the human-readable label; ontology_term carries the CURIE.
    assert m[0]["object"] == "blood plasma"
    assert m[0]["ontology_terms"]["object"] == "UBERON:0001969"


def test_projects_disease_with_doid_curie():
    claims = redu_sample_to_claims(SAMPLE, STUDY)
    d = [c for c in claims if c["qualifier"] == "is_biomarker_for"]
    assert len(d) == 1
    assert d[0]["object"] == "type 2 diabetes mellitus"
    assert d[0]["ontology_terms"]["object"] == "DOID:9352"


def test_projects_mass_spectrometer_and_ionisation_and_chromatography():
    claims = redu_sample_to_claims(SAMPLE, STUDY)
    by_q = {c["qualifier"]: c for c in claims}
    assert by_q["analyzed_with"]["object"] == "Q-Exactive"
    assert by_q["acquired_in_mode"]["object"] == "ESI positive"
    assert by_q["chromatographed_on"]["object"] == "C18 reverse-phase"


def test_every_claim_uses_the_provided_subject():
    claims = redu_sample_to_claims(SAMPLE, STUDY)
    assert claims, "expected at least one claim"
    for c in claims:
        assert c["subject"] == STUDY


def test_every_claim_is_sourced_to_redu():
    claims = redu_sample_to_claims(SAMPLE, STUDY)
    for c in claims:
        assert c["source"] == "redu"


def test_source_doi_passthrough():
    claims = redu_sample_to_claims(SAMPLE, STUDY, source_doi="10.1234/x")
    for c in claims:
        assert c.get("source_doi") == "10.1234/x"


# --- Empty / sentinel / missing-field handling -----------------------------

def test_missing_fields_produce_no_claims():
    assert redu_sample_to_claims({}, STUDY) == []


def test_sentinel_values_produce_no_claims():
    weak = {
        "NCBITaxonomy": "N/A",
        "UBERONBodyPartName": "missing",
        "SampleType": "ml.nofile",
        "DOIDCommonName": "Not Collected",
        "MassSpectrometer": "",
        "IonizationSourceAndPolarity": "   ",
        "ChromatographyAndPhase": None,
    }
    assert redu_sample_to_claims(weak, STUDY) == []


def test_falls_back_to_sample_type_when_no_uberon_label():
    weak = {"SampleTypeSub1": "leaf_tissue"}
    claims = redu_sample_to_claims(weak, STUDY)
    assert len(claims) == 1
    assert claims[0]["qualifier"] == "acquired_from_matrix"
    assert claims[0]["object"] == "leaf_tissue"
    assert "ontology_terms" not in claims[0]


def test_attribute_prefixed_field_names_also_work():
    """ReDU sometimes prefixes columns ATTRIBUTE_*. Helper tolerates both."""
    s = {
        "ATTRIBUTE_NCBITaxonomy": "9606",
        "ATTRIBUTE_Curated_BodyPartOntologyName": "feces",
        "ATTRIBUTE_Curated_BodyPartOntologyIndex": "UBERON:0001988",
        "ATTRIBUTE_DiseaseCommonName": "Crohn's disease",
        "ATTRIBUTE_DiseaseOntology": "DOID:8778",
    }
    claims = redu_sample_to_claims(s, STUDY)
    qs = {c["qualifier"]: c["ontology_terms"]["object"] for c in claims
          if "ontology_terms" in c}
    assert qs["found_in_organism"] == "NCBITaxon:9606"
    assert qs["acquired_from_matrix"] == "UBERON:0001988"
    assert qs["is_biomarker_for"] == "DOID:8778"


def test_purl_iris_are_normalised_to_curies():
    s = {
        "NCBITaxonomy": "http://purl.obolibrary.org/obo/NCBITaxon_9606",
        "UBERONBodyPartName": "liver",
        "UBERONOntologyIndex": "http://purl.obolibrary.org/obo/UBERON_0002107",
    }
    claims = redu_sample_to_claims(s, STUDY)
    qs = {c["qualifier"]: c for c in claims}
    assert qs["found_in_organism"]["object"] == "NCBITaxon:9606"
    assert qs["acquired_from_matrix"]["ontology_terms"]["object"] == "UBERON:0002107"


def test_stable_ordering_of_emitted_claims():
    """Diffing two ReDU dumps should be easy; the helper must emit claims in
    a stable order (organism → matrix → disease → ms → ionisation → chrom)."""
    qs = [c["qualifier"] for c in redu_sample_to_claims(SAMPLE, STUDY)]
    assert qs == ["found_in_organism", "acquired_from_matrix",
                  "is_biomarker_for", "analyzed_with", "acquired_in_mode",
                  "chromatographed_on"]


# --- redu_to_claims (offline branch) ---------------------------------------

def test_redu_to_claims_with_preloaded_sample_info():
    claims = redu_to_claims(SAMPLE["FileName"], STUDY, sample_info=SAMPLE,
                            cache_dir=None)
    assert len(claims) == 6


def test_redu_to_claims_returns_empty_on_empty_lookup():
    # When sample_info is explicitly None AND no cache hit, fetcher returns
    # None; helper returns []. We force a cache miss by passing cache_dir=None
    # and a session that always 404s.
    class _Sess:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001 — duck-typing
            class R:
                status_code = 404
            return R()
    assert redu_to_claims("bogus", STUDY, session=_Sess(), cache_dir=None) == []


def test_redu_lookup_empty_query_returns_none():
    assert redu_lookup("") is None
    assert redu_lookup("   ") is None


def test_redu_lookup_caches_response(tmp_path):
    # Hand-build a cache hit; verify lookup returns it without hitting network.
    from indicium_adapters_metabolomics.redu.parser import _cache_path

    filename = "f.MSV000082048/ccms_peak/Plate_28/30_84.mzML"
    cache_path = _cache_path(filename, tmp_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps({"NCBITaxonomy": "9606"}), encoding="utf-8")
    # No session — would fail if it tried to hit network without one.
    result = redu_lookup(filename, cache_dir=tmp_path)
    assert result == {"NCBITaxonomy": "9606"}


def test_redu_lookup_handles_network_error_gracefully():
    class _ErrSess:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            import requests as _r
            raise _r.RequestException("boom")
    assert redu_lookup("f.x/y.mzML", session=_ErrSess(), cache_dir=None) is None


def test_redu_lookup_rejects_non_dict_response():
    class _ListSess:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            class R:
                status_code = 200
                def json(self_):  # noqa: N805
                    return ["not", "a", "dict"]
            return R()
    assert redu_lookup("f.x/y.mzML", session=_ListSess(), cache_dir=None) is None


def test_redu_lookup_handles_invalid_json():
    class _BadJsonSess:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            class R:
                status_code = 200
                def json(self_):  # noqa: N805
                    raise ValueError("not json")
            return R()
    assert redu_lookup("f.x/y.mzML", session=_BadJsonSess(), cache_dir=None) is None


def test_redu_lookup_falls_through_on_corrupt_cache(tmp_path):
    from indicium_adapters_metabolomics.redu.parser import _cache_path

    filename = "f.x/corrupt.mzML"
    cache_path = _cache_path(filename, tmp_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{not valid json", encoding="utf-8")

    class _OkSess:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            class R:
                status_code = 200
                def json(self_):  # noqa: N805
                    return {"NCBITaxonomy": "9606"}
            return R()
    result = redu_lookup(filename, session=_OkSess(), cache_dir=tmp_path)
    assert result == {"NCBITaxonomy": "9606"}


# --- Live smoke (skipped unless INDICIUM_LIVE_TESTS=1) ---------------------

@pytest.mark.skipif(
    os.environ.get("INDICIUM_LIVE_TESTS") != "1",
    reason="set INDICIUM_LIVE_TESTS=1 to enable live ReDU smoke test",
)
def test_live_redu_returns_dict_or_none():
    """Sanity: live ReDU returns either a dict or (currently) 503 → None.

    Pinned to the exact query the user supplied. NOT an assertion about
    field content — ReDU's schema may evolve."""
    out = redu_lookup(
        "f.MSV000082048/ccms_peak/Plate_28/30_84.mzML",
        cache_dir=None,
    )
    assert out is None or isinstance(out, dict)
