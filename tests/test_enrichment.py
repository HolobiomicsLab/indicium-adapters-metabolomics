"""Tests for the CompoundIndex lookup engine."""
from __future__ import annotations

from indicium_adapters_metabolomics._enrichment import COMPOUND_INDEX, CompoundIndex


def test_lookup_by_name_returns_row():
    row = COMPOUND_INDEX.lookup("glucose")
    assert row is not None
    assert row["refmet_name"] == "D-Glucose"
    assert row["chebi"] == "CHEBI:17234"
    assert row["hmdb"] == "HMDB0000122"


def test_lookup_is_case_insensitive():
    assert COMPOUND_INDEX.lookup("GLUCOSE") is not None
    assert COMPOUND_INDEX.lookup("Glucose") is not None


def test_lookup_unknown_returns_none():
    assert COMPOUND_INDEX.lookup("not-a-real-compound") is None


def test_lookup_empty_returns_none():
    assert COMPOUND_INDEX.lookup("") is None
    assert COMPOUND_INDEX.lookup("   ") is None


def test_lookup_by_full_inchikey():
    row = COMPOUND_INDEX.lookup("WQZGKKKJIJFFOK-GASJEMHNSA-N")
    assert row is not None
    assert row["refmet_name"] == "D-Glucose"


def test_lookup_by_inchikey2d():
    row = COMPOUND_INDEX.lookup("WQZGKKKJIJFFOK")
    assert row is not None
    assert row["refmet_name"] == "D-Glucose"


def test_lookup_is_pure():
    """Same input returns equal dicts on repeated calls."""
    r1 = COMPOUND_INDEX.lookup("glucose")
    r2 = COMPOUND_INDEX.lookup("glucose")
    assert r1 == r2


def test_index_size_at_least_10():
    """The stub TSV ships 10 metabolites; production should be much larger."""
    # Force a load
    _ = COMPOUND_INDEX.lookup("glucose")
    assert len(COMPOUND_INDEX._by_name) >= 10


def test_lazy_load_only_once():
    """Loading is idempotent."""
    fresh = CompoundIndex()
    assert fresh._loaded is False
    _ = fresh.lookup("glucose")
    assert fresh._loaded is True
    n = len(fresh._by_name)
    _ = fresh.lookup("glutamate")  # second call must not re-load
    assert len(fresh._by_name) == n
