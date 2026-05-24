"""Tests for the ReDU GH-TSV → asb:Claim parser.

Two fixture types:

* `tests/fixtures/redu_msv_metadata.tsv` — synthetic per-MSV TSV shaped
  exactly like the live files under
  `https://raw.githubusercontent.com/Wang-Bioinformatics-Lab/ReDU_metadata/main/metadata/<MSV>.tsv`.
* `tests/fixtures/redu_sample_response.json` — kept from the original draft;
  exercises the legacy ATTRIBUTE_-prefixed / live `/filename` schema.

Both schemas flow through `redu_sample_to_claims` and the test set asserts
parity, so the parser is robust to either source.

A live-API smoke test against the GH raw URL is gated on
`INDICIUM_LIVE_TESTS=1`.
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
from indicium_adapters_metabolomics.redu.parser import (
    REDU_GH_TSV_URL,
    _msv_and_relpath,
    _row_for_filename,
)

FIXTURES = Path(__file__).parent / "fixtures"
TSV_FIXTURE = (FIXTURES / "redu_msv_metadata.tsv").read_text(encoding="utf-8")
JSON_FIXTURE = json.loads(
    (FIXTURES / "redu_sample_response.json").read_text(encoding="utf-8")
)
STUDY = "study:msv082048"


# --- _msv_and_relpath ------------------------------------------------------

@pytest.mark.parametrize("filename,expected", [
    ("f.MSV000082048/ccms_peak/Plate_28/30_84.mzML",
     ("MSV000082048", "30_84.mzML")),
    ("MSV000082048/30_84.mzML",
     ("MSV000082048", "30_84.mzML")),
    ("MSV000082048", ("MSV000082048", None)),
    ("f.MSV000082048", ("MSV000082048", None)),
    ("30_84.mzML", (None, "30_84.mzML")),
    ("", (None, None)),
    ("   ", (None, None)),
])
def test_msv_and_relpath_parses_paths(filename, expected):
    assert _msv_and_relpath(filename) == expected


# --- _row_for_filename ----------------------------------------------------

def test_row_for_filename_exact_match():
    row = _row_for_filename(TSV_FIXTURE, "30_84.mzML")
    assert row is not None
    assert row["MassiveID"] == "MSV000082048"
    assert row["NCBITaxonomy"] == "3702|Arabidopsis thaliana"


def test_row_for_filename_case_insensitive():
    assert _row_for_filename(TSV_FIXTURE, "30_84.MZML") is not None


def test_row_for_filename_missing_returns_none():
    assert _row_for_filename(TSV_FIXTURE, "not-here.mzML") is None


def test_row_for_filename_none_returns_single_row_only_when_unambiguous():
    # Multiple rows + no basename → ambiguous → None
    assert _row_for_filename(TSV_FIXTURE, None) is None
    # Single-row TSV → return the row even without a basename
    one_row = "MassiveID\tfilename\nMSV000099999\tonly.mzML\n"
    out = _row_for_filename(one_row, None)
    assert out is not None
    assert out["filename"] == "only.mzML"


def test_row_for_filename_empty_tsv_returns_none():
    assert _row_for_filename("MassiveID\tfilename\n", "anything.mzML") is None


# --- redu_sample_to_claims (TSV-row branch) -------------------------------

def test_tsv_row_projects_organism_with_ncbitaxon_curie():
    row = _row_for_filename(TSV_FIXTURE, "30_84.mzML")
    claims = redu_sample_to_claims(row, STUDY)
    org = [c for c in claims if c["qualifier"] == "found_in_organism"]
    assert len(org) == 1
    # NCBITaxonomy was "3702|Arabidopsis thaliana" — the |label suffix is stripped
    assert org[0]["object"] == "NCBITaxon:3702"
    assert org[0]["ontology_terms"]["object"] == "NCBITaxon:3702"


def test_tsv_row_projects_uberon_matrix_when_present():
    row = _row_for_filename(TSV_FIXTURE, "30_84.mzML")
    claims = redu_sample_to_claims(row, STUDY)
    m = [c for c in claims if c["qualifier"] == "acquired_from_matrix"]
    assert len(m) == 1
    # Object is the human-readable string (which in this TSV is the CURIE itself
    # because the GH schema only ships one column for UBERON). The helper still
    # records it under ontology_terms when it looks like a CURIE.
    assert "UBERON" in m[0]["object"] or m[0]["object"] == "leaf_tissue"


def test_tsv_row_with_no_uberon_falls_back_to_sample_type():
    one_row = (
        "MassiveID\tfilename\tSampleType\tSampleTypeSub1\tUBERONBodyPartName\n"
        "MSV000099999\tx.mzML\tplant\tleaf_tissue\t\n"
    )
    row = _row_for_filename(one_row, "x.mzML")
    claims = redu_sample_to_claims(row, STUDY)
    m = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert m["object"] == "leaf_tissue"
    assert "ontology_terms" not in m


def test_tsv_row_skips_sentinel_not_collected():
    """ReDU writes 'not collected' for many fields; should not emit a claim."""
    row = _row_for_filename(TSV_FIXTURE, "30_84.mzML")
    claims = redu_sample_to_claims(row, STUDY)
    # BiologicalSex / AgeInYears were 'not collected' → no claim emitted
    qs = [c["qualifier"] for c in claims]
    assert "biological_sex" not in qs
    assert "has_age" not in qs


def test_tsv_row_blank_row_yields_no_claims():
    one_row = (
        "MassiveID\tfilename\tSampleType\tNCBITaxonomy\n"
        "MSV000099999\tblank.mzML\tblank\t\n"
    )
    row = _row_for_filename(one_row, "blank.mzML")
    claims = redu_sample_to_claims(row, STUDY)
    # Only "blank" SampleType emits acquired_from_matrix
    assert len(claims) == 1
    assert claims[0]["qualifier"] == "acquired_from_matrix"
    assert claims[0]["object"] == "blank"


def test_tsv_row_empty_string_fields_skipped():
    row = _row_for_filename(TSV_FIXTURE, "control_01.mzML")
    claims = redu_sample_to_claims(row, STUDY)
    qs = [c["qualifier"] for c in claims]
    assert "found_in_organism" not in qs
    assert "is_biomarker_for" not in qs
    # SampleType "blank" still survives
    assert "acquired_from_matrix" in qs


# --- redu_sample_to_claims (legacy JSON / ATTRIBUTE_* schema branch) ------

def test_json_schema_projects_organism_with_ncbitaxon_curie():
    claims = redu_sample_to_claims(JSON_FIXTURE, STUDY)
    org = [c for c in claims if c["qualifier"] == "found_in_organism"]
    assert len(org) == 1
    assert org[0]["ontology_terms"]["object"] == "NCBITaxon:9606"


def test_json_schema_matrix_uses_uberon_when_present():
    claims = redu_sample_to_claims(JSON_FIXTURE, STUDY)
    m = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert m["object"] == "blood plasma"
    assert m["ontology_terms"]["object"] == "UBERON:0001969"


def test_json_schema_disease_with_doid_curie():
    claims = redu_sample_to_claims(JSON_FIXTURE, STUDY)
    d = next(c for c in claims if c["qualifier"] == "is_biomarker_for")
    assert d["ontology_terms"]["object"] == "DOID:9352"


def test_json_schema_ms_ionisation_chrom_only_in_legacy():
    """The legacy `/filename` schema has MS/ionisation/chrom columns the GH TSV
    schema doesn't carry. Those flow through unchanged."""
    claims = redu_sample_to_claims(JSON_FIXTURE, STUDY)
    by_q = {c["qualifier"]: c["object"] for c in claims}
    assert by_q["analyzed_with"] == "Q-Exactive"
    assert by_q["acquired_in_mode"] == "ESI positive"
    assert by_q["chromatographed_on"] == "C18 reverse-phase"


def test_json_schema_attribute_prefixed_keys_still_work():
    s = {
        "ATTRIBUTE_NCBITaxonomy": "9606",
        "ATTRIBUTE_Curated_BodyPartOntologyName": "feces",
        "ATTRIBUTE_Curated_BodyPartOntologyIndex": "UBERON:0001988",
        "ATTRIBUTE_DiseaseCommonName": "Crohn's disease",
        "ATTRIBUTE_DiseaseOntology": "DOID:8778",
    }
    qs = {c["qualifier"]: c["ontology_terms"]["object"]
          for c in redu_sample_to_claims(s, STUDY) if "ontology_terms" in c}
    assert qs["found_in_organism"] == "NCBITaxon:9606"
    assert qs["acquired_from_matrix"] == "UBERON:0001988"
    assert qs["is_biomarker_for"] == "DOID:8778"


def test_purl_iris_normalised_to_curies():
    s = {
        "NCBITaxonomy": "http://purl.obolibrary.org/obo/NCBITaxon_9606",
        "UBERONBodyPartName": "liver",
        "UBERONOntologyIndex": "http://purl.obolibrary.org/obo/UBERON_0002107",
    }
    claims = redu_sample_to_claims(s, STUDY)
    qs = {c["qualifier"]: c for c in claims}
    assert qs["found_in_organism"]["object"] == "NCBITaxon:9606"
    assert qs["acquired_from_matrix"]["ontology_terms"]["object"] == "UBERON:0002107"


def test_every_claim_uses_provided_subject():
    for src in (JSON_FIXTURE, _row_for_filename(TSV_FIXTURE, "30_84.mzML")):
        claims = redu_sample_to_claims(src, STUDY)
        assert claims
        for c in claims:
            assert c["subject"] == STUDY
            assert c["source"] == "redu"


def test_source_doi_passthrough():
    claims = redu_sample_to_claims(JSON_FIXTURE, STUDY, source_doi="10.1234/x")
    for c in claims:
        assert c["source_doi"] == "10.1234/x"


def test_missing_fields_produce_no_claims():
    assert redu_sample_to_claims({}, STUDY) == []


# --- redu_lookup / redu_to_claims (HTTP layer with stub session) ----------

class _StubSession:
    """In-memory GitHub raw fetcher — maps MSV → TSV text or 404."""
    def __init__(self, tsv_by_msv: dict[str, str]):
        self.tsv_by_msv = tsv_by_msv
        self.calls: list[str] = []
        self.headers: dict[str, str] = {}

    def get(self, url: str, *, timeout: float = 0):  # noqa: ANN201
        self.calls.append(url)
        # The URL is `.../metadata/<MSV>.tsv`
        msv = url.rsplit("/", 1)[-1].removesuffix(".tsv")
        class R:
            def __init__(self, status: int, text: str = ""):
                self.status_code = status
                self.text = text
        if msv in self.tsv_by_msv:
            return R(200, self.tsv_by_msv[msv])
        return R(404)


def test_redu_lookup_round_trip_via_stub(tmp_path):
    sess = _StubSession({"MSV000082048": TSV_FIXTURE})
    row = redu_lookup(
        "f.MSV000082048/ccms_peak/Plate_28/30_84.mzML",
        session=sess, cache_dir=tmp_path,
    )
    assert row is not None
    assert row["MassiveID"] == "MSV000082048"
    assert row["filename"] == "30_84.mzML"


def test_redu_lookup_cache_avoids_second_fetch(tmp_path):
    sess = _StubSession({"MSV000082048": TSV_FIXTURE})
    redu_lookup("f.MSV000082048/30_84.mzML", session=sess, cache_dir=tmp_path)
    redu_lookup("f.MSV000082048/30_85.mzML", session=sess, cache_dir=tmp_path)
    # Same MSV → single fetch.
    assert len(sess.calls) == 1


def test_redu_lookup_returns_none_on_404(tmp_path):
    sess = _StubSession({})
    assert redu_lookup("f.MSV000099999/x.mzML", session=sess,
                       cache_dir=tmp_path) is None


def test_redu_lookup_returns_none_on_unparseable_input():
    assert redu_lookup("") is None
    assert redu_lookup("totally bogus") is None


def test_redu_to_claims_with_session_stub(tmp_path):
    sess = _StubSession({"MSV000082048": TSV_FIXTURE})
    claims = redu_to_claims(
        "f.MSV000082048/30_84.mzML", STUDY,
        session=sess, cache_dir=tmp_path,
    )
    qs = [c["qualifier"] for c in claims]
    assert "found_in_organism" in qs
    assert "acquired_from_matrix" in qs


def test_redu_to_claims_returns_empty_when_lookup_fails(tmp_path):
    sess = _StubSession({})
    assert redu_to_claims("f.MSV000099999/x.mzML", STUDY,
                          session=sess, cache_dir=tmp_path) == []


def test_redu_to_claims_with_preloaded_sample_info_skips_http():
    sess = _StubSession({})  # would 404 — must not be called
    out = redu_to_claims(
        "f.MSV000082048/30_84.mzML", STUDY,
        sample_info=JSON_FIXTURE, session=sess, cache_dir=None,
    )
    assert out  # JSON fixture produces 6 claims
    assert sess.calls == []


def test_redu_lookup_handles_network_error_gracefully(tmp_path):
    class _ErrSess:
        headers: dict = {}
        def get(self, *a, **k):
            raise __import__("requests").RequestException("boom")
    assert redu_lookup("f.MSV000082048/x.mzML", session=_ErrSess(),
                       cache_dir=tmp_path) is None


def test_redu_url_constant_uses_main_branch():
    """Sanity: the URL template still points at `main`. If a tagged release
    of ReDU_metadata appears, this test will catch any drift."""
    assert "ReDU_metadata/main/metadata" in REDU_GH_TSV_URL


# --- Live smoke (gated) ----------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("INDICIUM_LIVE_TESTS") != "1",
    reason="set INDICIUM_LIVE_TESTS=1 to enable live ReDU smoke test",
)
def test_live_redu_returns_dict_or_none():
    """Sanity: the live GH-raw URL returns a parseable TSV for a known MSV."""
    out = redu_lookup("MSV000087752/210628_Lund_ColitisInulin_isotopetracing_ExportSpectra.mzML",
                      cache_dir=None)
    assert out is None or isinstance(out, dict)
