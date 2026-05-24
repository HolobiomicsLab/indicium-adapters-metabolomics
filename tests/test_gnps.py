"""Tests for the GNPS result_json + ManageParameters parsers.

Offline tests run against `tests/fixtures/gnps_annotations_response.json`
and `gnps_parameters_response.xml` — the XML was captured verbatim from a
live probe on 2026-05-24 against task 1ad7bc366aef45ce81d2dfcca0a9a5e7.

Live tests gated on INDICIUM_LIVE_TESTS=1.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from indicium_adapters_metabolomics.gnps import (
    fetch_gnps_annotations,
    fetch_gnps_parameters,
    gnps_task_to_claims,
    parse_gnps_annotations,
    parse_gnps_parameters,
)

FIXTURES = Path(__file__).parent / "fixtures"
ANNOT = json.loads((FIXTURES / "gnps_annotations_response.json").read_text())
XML = (FIXTURES / "gnps_parameters_response.xml").read_text()
TASK = "1ad7bc366aef45ce81d2dfcca0a9a5e7"


# --- parse_gnps_annotations ------------------------------------------------

def test_annotations_emits_one_claim_per_named_row():
    """3 rows in fixture; 1 has empty Compound_Name → 2 claims."""
    claims = parse_gnps_annotations(ANNOT["blockData"], TASK)
    assert len(claims) == 2


def test_annotation_subject_includes_task_and_scan():
    claims = parse_gnps_annotations(ANNOT["blockData"], TASK)
    assert all(c["subject"].startswith(f"gnps_task:{TASK}:scan:") for c in claims)
    assert claims[0]["subject"] == f"gnps_task:{TASK}:scan:1099"


def test_annotation_qualifier_is_spectral_match():
    claims = parse_gnps_annotations(ANNOT["blockData"], TASK)
    assert all(c["qualifier"] == "spectral_match" for c in claims)


def test_annotation_object_is_compound_name_verbatim():
    claims = parse_gnps_annotations(ANNOT["blockData"], TASK)
    assert claims[0]["object"].startswith("Spectral Match to 1,2-Dipentadecanoyl")


def test_annotation_usi_in_ontology_terms():
    claims = parse_gnps_annotations(ANNOT["blockData"], TASK)
    assert claims[0]["ontology_terms"]["object"] == \
        "mzspec:GNPS:GNPS-LIBRARY:accession:CCMSLIB00003136425"


def test_annotation_evidence_has_typed_floats():
    c = parse_gnps_annotations(ANNOT["blockData"], TASK)[0]
    ev = c["evidence"]
    assert ev["mq_score"] == pytest.approx(0.976676)
    assert ev["shared_peaks"] == 31.0
    assert ev["precursor_mz"] == pytest.approx(664.506)
    assert ev["library"] == "lib-00031.mgf"
    assert ev["spectrum_id"] == "CCMSLIB00003136425"


def test_annotation_skips_row_without_compound_name():
    claims = parse_gnps_annotations(ANNOT["blockData"], TASK)
    assert all("scan:9999" not in c["subject"] for c in claims)


def test_annotation_handles_empty_blockdata():
    assert parse_gnps_annotations([], TASK) == []
    assert parse_gnps_annotations(None, TASK) == []  # type: ignore[arg-type]


def test_annotation_source_doi_passthrough():
    claims = parse_gnps_annotations(ANNOT["blockData"], TASK, source_doi="10.5/x")
    assert all(c["source_doi"] == "10.5/x" for c in claims)


# --- parse_gnps_parameters -------------------------------------------------

def test_parameters_emits_workflow_tolerances_and_ion_mode():
    claims = parse_gnps_parameters(XML, TASK)
    by_q = {c["qualifier"]: c for c in claims}
    assert "has_processing_software" in by_q
    assert "analyzed_with" in by_q
    assert "acquired_in_mode" in by_q


def test_parameters_workflow_maps_to_canonical_label():
    """METABOLOMICS-SNETS-V2 → 'GNPS Classical Molecular Networking'."""
    claims = parse_gnps_parameters(XML, TASK)
    sw = next(c for c in claims if c["qualifier"] == "has_processing_software")
    assert sw["object"] == "GNPS Classical Molecular Networking"
    assert sw["evidence"]["gnps_workflow"] == "METABOLOMICS-SNETS-V2"


def test_parameters_tolerances_concatenated_into_analyzed_with():
    claims = parse_gnps_parameters(XML, TASK)
    a = next(c for c in claims if c["qualifier"] == "analyzed_with")
    assert "tolerance.PM_tolerance=2.0" in a["object"]
    assert "tolerance.Ion_tolerance=0.5" in a["object"]
    assert "MIN_MATCHED_PEAKS=6" in a["object"]


def test_parameters_ion_mode_lowercased():
    claims = parse_gnps_parameters(XML, TASK)
    ion = next(c for c in claims if c["qualifier"] == "acquired_in_mode")
    assert ion["object"] == "positive"


def test_parameters_subject_is_gnps_task():
    claims = parse_gnps_parameters(XML, TASK)
    assert all(c["subject"] == f"gnps_task:{TASK}" for c in claims)


def test_parameters_malformed_xml_returns_empty_list():
    assert parse_gnps_parameters("<not><valid>xml", TASK) == []


def test_parameters_unknown_workflow_falls_back_to_gnps_label():
    xml = '<parameters><parameter name="workflow">SOME-CUSTOM-FLOW</parameter></parameters>'
    claims = parse_gnps_parameters(xml, TASK)
    sw = next(c for c in claims if c["qualifier"] == "has_processing_software")
    assert sw["object"] == "GNPS"  # canonical_software_name("GNPS")
    assert sw["evidence"]["gnps_workflow"] == "SOME-CUSTOM-FLOW"


def test_parameters_missing_workflow_yields_no_software_claim():
    xml = '<parameters><parameter name="ion_mode">Negative</parameter></parameters>'
    claims = parse_gnps_parameters(xml, TASK)
    assert not any(c["qualifier"] == "has_processing_software" for c in claims)
    ion = next(c for c in claims if c["qualifier"] == "acquired_in_mode")
    assert ion["object"] == "negative"


def test_parameters_no_useful_fields_yields_empty():
    xml = '<parameters><parameter name="email">x@y.org</parameter></parameters>'
    assert parse_gnps_parameters(xml, TASK) == []


# --- fetch_* offline-mock branches -----------------------------------------

def test_fetch_annotations_empty_task_returns_none():
    assert fetch_gnps_annotations("") is None
    assert fetch_gnps_annotations("   ") is None


def test_fetch_parameters_empty_task_returns_none():
    assert fetch_gnps_parameters("") is None


def test_fetch_annotations_caches_response(tmp_path):
    from indicium_adapters_metabolomics.gnps.parser import _cache_path

    path = _cache_path((TASK, "view_all_annotations_DB"), tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"blockData": []}), encoding="utf-8")
    out = fetch_gnps_annotations(TASK, cache_dir=tmp_path)
    assert out == {"blockData": []}


def test_fetch_parameters_caches_response(tmp_path):
    from indicium_adapters_metabolomics.gnps.parser import _cache_path

    path = _cache_path((TASK, "parameters"), tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"xml": XML}), encoding="utf-8")
    out = fetch_gnps_parameters(TASK, cache_dir=tmp_path)
    assert out == XML


def test_fetch_annotations_handles_network_error():
    class _Err:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            raise __import__("requests").RequestException("boom")
    assert fetch_gnps_annotations(TASK, session=_Err(), cache_dir=None) is None


def test_fetch_parameters_handles_network_error():
    class _Err:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            raise __import__("requests").RequestException("boom")
    assert fetch_gnps_parameters(TASK, session=_Err(), cache_dir=None) is None


def test_fetch_annotations_rejects_non_200():
    class _S:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            class R:
                status_code = 500
                text = "oops"
            return R()
    assert fetch_gnps_annotations(TASK, session=_S(), cache_dir=None) is None


def test_fetch_annotations_rejects_invalid_json():
    class _S:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            class R:
                status_code = 200
                text = "not json"
            return R()
    assert fetch_gnps_annotations(TASK, session=_S(), cache_dir=None) is None


def test_fetch_parameters_rejects_non_200():
    class _S:
        headers: dict = {}
        def get(self, *a, **k):  # noqa: ANN001
            class R:
                status_code = 503
                text = ""
            return R()
    assert fetch_gnps_parameters(TASK, session=_S(), cache_dir=None) is None


# --- gnps_task_to_claims (high-level combiner) -----------------------------

def test_high_level_combines_annotations_and_parameters():
    out = gnps_task_to_claims(TASK, annotations_data=ANNOT, parameters_xml=XML,
                              cache_dir=None)
    qs = {c["qualifier"] for c in out}
    assert qs == {"spectral_match", "has_processing_software",
                  "analyzed_with", "acquired_in_mode"}


def test_high_level_skips_parameters_when_xml_empty():
    out = gnps_task_to_claims(TASK, annotations_data=ANNOT, parameters_xml="",
                              cache_dir=None)
    qs = {c["qualifier"] for c in out}
    assert qs == {"spectral_match"}


# --- Live smoke (gated) ----------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("INDICIUM_LIVE_TESTS") != "1",
    reason="set INDICIUM_LIVE_TESTS=1 to enable live GNPS smoke test",
)
def test_live_gnps_annotations_returns_dict_or_none():
    out = fetch_gnps_annotations(TASK, cache_dir=None)
    assert out is None or (isinstance(out, dict) and "blockData" in out)


@pytest.mark.skipif(
    os.environ.get("INDICIUM_LIVE_TESTS") != "1",
    reason="set INDICIUM_LIVE_TESTS=1 to enable live GNPS smoke test",
)
def test_live_gnps_parameters_returns_str_or_none():
    out = fetch_gnps_parameters(TASK, cache_dir=None)
    assert out is None or isinstance(out, str)
