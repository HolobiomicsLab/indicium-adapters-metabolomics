"""Tests for the mzTab-M → asb:Claim projection."""
from __future__ import annotations

from pathlib import Path

import pytest

from indicium_adapters_metabolomics.mztab import parse_mztab_to_claims

FIXTURE = Path(__file__).parent / "fixtures" / "sample.mztab"


def test_parses_fixture_without_error():
    claims = parse_mztab_to_claims(FIXTURE)
    assert isinstance(claims, list)
    assert len(claims) >= 1


def test_sml_row_yields_identifies_claim():
    """An SML row produces an 'identifies' claim with the database identifier as object."""
    claims = parse_mztab_to_claims(FIXTURE)
    sml_claims = [c for c in claims if c.get("qualifier") == "identifies"]
    assert len(sml_claims) == 1
    c = sml_claims[0]
    assert c["object"] == "CHEBI:17234"
    assert "D-Glucose" in (c.get("subject") or "")
    assert c["evidence_id"].startswith("mztab:")


def test_smf_row_yields_has_feature_claim():
    """An SMF row produces a 'has_feature' claim."""
    claims = parse_mztab_to_claims(FIXTURE)
    smf_claims = [c for c in claims if c.get("qualifier") == "has_feature"]
    assert len(smf_claims) == 1
    c = smf_claims[0]
    assert "smf:" in c["object"]


def test_claims_dont_mutate_when_called_twice():
    a = parse_mztab_to_claims(FIXTURE)
    b = parse_mztab_to_claims(FIXTURE)
    assert a == b


def test_missing_file_raises_filenotfound():
    with pytest.raises(FileNotFoundError):
        parse_mztab_to_claims(Path("/nonexistent/sample.mztab"))
