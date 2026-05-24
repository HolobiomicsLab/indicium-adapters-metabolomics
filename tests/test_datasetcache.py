"""Tests for the GNPS2 datasetcache datasette parser.

Fixture: `tests/fixtures/gnps2_datasetcache_uniquemri.json` — verbatim from
a live probe on 2026-05-24 against `dataset=MSV000082048`.

Live smoke gated on `INDICIUM_LIVE_TESTS=1`.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from indicium_adapters_metabolomics.gnps import (
    datasetcache_row_to_claims,
    datasetcache_to_claims,
    fetch_datasetcache_row,
)

FIXTURES = Path(__file__).parent / "fixtures"
RESPONSE = json.loads(
    (FIXTURES / "gnps2_datasetcache_uniquemri.json").read_text(encoding="utf-8")
)
ROW = RESPONSE["rows"][0]
STUDY = "study:msv082048"


# --- datasetcache_row_to_claims (pure projection) -------------------------

def test_projects_instrument_model_to_analyzed_with():
    claims = datasetcache_row_to_claims(ROW, STUDY)
    a = next(c for c in claims if c["qualifier"] == "analyzed_with")
    assert a["object"] == "Q Exactive Plus"
    # Vendor folded into evidence.
    assert a["evidence"]["instrument_vendor"] == "Thermo Fisher Scientific"


def test_projects_mass_analyzer_split_on_semicolon():
    """v0.6.1: 'orbitrap;quadrupole' yields TWO claims, not one literal."""
    claims = datasetcache_row_to_claims(ROW, STUDY)
    analyzers = [c["object"] for c in claims if c["qualifier"] == "uses_mass_analyzer"]
    assert analyzers == ["orbitrap", "quadrupole"]


def test_projects_ionisation_split_on_semicolon():
    """v0.6.1: 'electrospray inlet;electrospray ionization' yields TWO claims."""
    claims = datasetcache_row_to_claims(ROW, STUDY)
    ions = [c["object"] for c in claims if c["qualifier"] == "acquired_in_mode"]
    assert ions == ["electrospray inlet", "electrospray ionization"]


def test_single_valued_mass_analyzer_yields_one_claim():
    row = dict(ROW)
    row["MassAnalyzer"] = "orbitrap"
    row["Ionization"] = ""
    claims = datasetcache_row_to_claims(row, STUDY)
    analyzers = [c for c in claims if c["qualifier"] == "uses_mass_analyzer"]
    assert len(analyzers) == 1
    assert analyzers[0]["object"] == "orbitrap"


def test_semicolon_split_dedups_and_drops_empty_parts():
    """Tolerates accidental ';;', whitespace, and case-duplicates."""
    row = dict(ROW)
    row["MassAnalyzer"] = " orbitrap ; ; Orbitrap;quadrupole "
    row["Ionization"] = ""
    claims = datasetcache_row_to_claims(row, STUDY)
    analyzers = [c["object"] for c in claims if c["qualifier"] == "uses_mass_analyzer"]
    assert analyzers == ["orbitrap", "quadrupole"]  # case-insensitive dedup, first wins


def test_operational_sample_type_gnps_is_not_a_matrix():
    """`sample_type='GNPS'` is an operational tag, not a biological matrix —
    must NOT emit acquired_from_matrix."""
    claims = datasetcache_row_to_claims(ROW, STUDY)
    qs = [c["qualifier"] for c in claims]
    assert "acquired_from_matrix" not in qs


def test_real_matrix_in_sample_type_does_emit_matrix_claim():
    row = dict(ROW)
    row["sample_type"] = "plant"
    claims = datasetcache_row_to_claims(row, STUDY)
    m = next(c for c in claims if c["qualifier"] == "acquired_from_matrix")
    assert m["object"] == "plant"


def test_every_claim_uses_subject_and_source():
    claims = datasetcache_row_to_claims(ROW, STUDY)
    assert claims
    for c in claims:
        assert c["subject"] == STUDY
        assert c["source"] == "gnps2-datasetcache"


def test_source_doi_passthrough():
    claims = datasetcache_row_to_claims(ROW, STUDY, source_doi="10.5/x")
    for c in claims:
        assert c["source_doi"] == "10.5/x"


def test_empty_row_yields_no_claims():
    assert datasetcache_row_to_claims({}, STUDY) == []
    assert datasetcache_row_to_claims(None, STUDY) == []  # type: ignore[arg-type]


def test_sentinel_nan_skipped():
    row = {"instrument_model": "nan", "MassAnalyzer": "NaN",
           "Ionization": "unknown", "sample_type": ""}
    assert datasetcache_row_to_claims(row, STUDY) == []


def test_instrument_model_only_emits_one_claim_even_without_vendor():
    row = {"instrument_model": "Maxis"}
    claims = datasetcache_row_to_claims(row, STUDY)
    assert len(claims) == 1
    assert "evidence" not in claims[0]


# --- fetch_datasetcache_row (HTTP layer with stub session) ----------------

class _StubSession:
    def __init__(self, response_body: dict | None, status: int = 200):
        self.body = response_body
        self.status = status
        self.calls: list[tuple[str, dict]] = []
        self.headers: dict[str, str] = {}

    def get(self, url, *, params=None, timeout=0):  # noqa: ANN001, ANN201
        self.calls.append((url, params or {}))
        outer = self
        class R:
            status_code = outer.status
            def json(self):  # noqa: D401, ANN201
                return outer.body
        return R()


def test_fetch_returns_first_row_object(tmp_path):
    sess = _StubSession(RESPONSE)
    row = fetch_datasetcache_row("ccms_peak/Plate_22/11_12.mzML",
                                  session=sess, cache_dir=tmp_path)
    assert row is not None
    assert row["MassAnalyzer"] == "orbitrap;quadrupole"
    # Datasette filter params + objects shape.
    _, params = sess.calls[0]
    assert params["filepath__exact"] == "ccms_peak/Plate_22/11_12.mzML"
    assert params["_shape"] == "objects"


def test_fetch_caches_response(tmp_path):
    sess = _StubSession(RESPONSE)
    a = fetch_datasetcache_row("ccms_peak/x.mzML", session=sess,
                                cache_dir=tmp_path)
    b = fetch_datasetcache_row("ccms_peak/x.mzML", session=sess,
                                cache_dir=tmp_path)
    assert a == b
    assert len(sess.calls) == 1


def test_fetch_caches_misses(tmp_path):
    """A no-rows response should also be cached so we don't re-fetch the
    miss path."""
    sess = _StubSession({"rows": []})
    a = fetch_datasetcache_row("ccms_peak/missing.mzML", session=sess,
                                cache_dir=tmp_path)
    b = fetch_datasetcache_row("ccms_peak/missing.mzML", session=sess,
                                cache_dir=tmp_path)
    assert a is None and b is None
    assert len(sess.calls) == 1


def test_fetch_returns_none_on_empty_rows(tmp_path):
    sess = _StubSession({"rows": []})
    assert fetch_datasetcache_row("x", session=sess,
                                   cache_dir=tmp_path) is None


def test_fetch_returns_none_on_non_200(tmp_path):
    sess = _StubSession(None, status=500)
    assert fetch_datasetcache_row("x", session=sess,
                                   cache_dir=tmp_path) is None


def test_fetch_returns_none_on_invalid_json(tmp_path):
    class _BadJson:
        status_code = 200
        def json(self):  # noqa: ANN201
            raise ValueError("no")
    class _S:
        headers: dict = {}
        calls: list = []
        def get(self, *a, **k):  # noqa: ANN201
            return _BadJson()
    assert fetch_datasetcache_row("x", session=_S(), cache_dir=tmp_path) is None


def test_fetch_returns_none_on_network_error():
    class _ErrSess:
        headers: dict = {}
        def get(self, *a, **k):
            raise __import__("requests").RequestException("boom")
    assert fetch_datasetcache_row("x", session=_ErrSess(),
                                   cache_dir=None) is None


def test_fetch_rejects_unknown_table():
    assert fetch_datasetcache_row("x", table="not_a_table") is None


def test_fetch_rejects_empty_filepath():
    assert fetch_datasetcache_row("") is None
    assert fetch_datasetcache_row("   ") is None


# --- datasetcache_to_claims (combiner) ------------------------------------

def test_to_claims_via_row_kwarg_skips_http():
    sess = _StubSession({"rows": []})  # would yield empty if called
    out = datasetcache_to_claims("anything", STUDY, row=ROW,
                                  session=sess, cache_dir=None)
    assert {c["qualifier"] for c in out} == {"analyzed_with",
                                              "uses_mass_analyzer",
                                              "acquired_in_mode"}
    # v0.6.1: post-split, MSV000082048 fixture yields exactly 5 claims:
    # 1 analyzed_with + 2 uses_mass_analyzer + 2 acquired_in_mode.
    assert len(out) == 5
    assert sess.calls == []


def test_to_claims_returns_empty_when_lookup_fails(tmp_path):
    sess = _StubSession({"rows": []})
    assert datasetcache_to_claims("x", STUDY, session=sess,
                                    cache_dir=tmp_path) == []


# --- Live smoke (gated) ---------------------------------------------------

@pytest.mark.skipif(
    os.environ.get("INDICIUM_LIVE_TESTS") != "1",
    reason="set INDICIUM_LIVE_TESTS=1 to enable live datasette smoke",
)
def test_live_datasetcache_returns_dict_or_none():
    out = fetch_datasetcache_row("ccms_peak/Plate_22/11_12.mzML",
                                  cache_dir=None)
    assert out is None or isinstance(out, dict)
