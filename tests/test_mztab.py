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


# --- ontology_term_justifications (SEMAPV) ------------------------------------

def test_mztab_sml_sets_composite_matching_justification():
    """SML rows with a CURIE database_identifier must get semapv:CompositeMatching.

    The database_identifier is taken verbatim from the mzTab file — it is
    a curated identifier provided by the upstream tool, so CompositeMatching
    is the appropriate SEMAPV term.
    """
    claims = parse_mztab_to_claims(FIXTURE)
    sml_claims = [c for c in claims if c.get("qualifier") == "identifies"]
    assert sml_claims, "fixture must produce at least one identifies claim"
    for c in sml_claims:
        if c.get("ontology_terms", {}).get("object"):
            j = c.get("ontology_term_justifications", {})
            assert j.get("object") == "semapv:CompositeMatching", (
                f"expected semapv:CompositeMatching, got {j.get('object')!r}"
            )


def test_mztab_sml_no_justification_when_no_curie(tmp_path):
    """SML rows without a CURIE-shaped database_identifier emit no justification."""
    mztab = tmp_path / "no_curie.mztab"
    mztab.write_text(
        "SMH\tSML_ID\tchemical_name\tdatabase_identifier\n"
        "SML\t1\tMy Compound\tplain-string-no-colon\n",
        encoding="utf-8",
    )
    claims = parse_mztab_to_claims(mztab)
    sml = [c for c in claims if c.get("qualifier") == "identifies"]
    assert sml
    # No CURIE → no ontology_terms["object"] → no justification
    assert not sml[0].get("ontology_terms", {}).get("object")
    assert not sml[0].get("ontology_term_justifications", {}).get("object")
