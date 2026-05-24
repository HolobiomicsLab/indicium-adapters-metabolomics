"""Tests for the CompoundIndex lookup engine."""
from __future__ import annotations

from indicium_adapters_metabolomics._enrichment import COMPOUND_INDEX, CompoundIndex


def test_lookup_by_name_returns_row():
    row = COMPOUND_INDEX.lookup("glucose")
    assert row is not None
    # v0.2.0: refmet_name is empty (deferred to v0.3.0); pin stable CHEBI CURIE instead
    assert row["chebi"] == "CHEBI:17234"
    assert row["wikidata"] == "WD:Q37525"


def test_lookup_is_case_insensitive():
    assert COMPOUND_INDEX.lookup("GLUCOSE") is not None
    assert COMPOUND_INDEX.lookup("Glucose") is not None


def test_lookup_unknown_returns_none():
    assert COMPOUND_INDEX.lookup("not-a-real-compound") is None


def test_lookup_empty_returns_none():
    assert COMPOUND_INDEX.lookup("") is None
    assert COMPOUND_INDEX.lookup("   ") is None


def test_lookup_by_full_inchikey():
    # WQZGKKKJIJFFOK-GASJEMHNSA-N is the InChIKey for d-glucopyranose (CHEBI:4167) in Wikidata
    row = COMPOUND_INDEX.lookup("WQZGKKKJIJFFOK-GASJEMHNSA-N")
    assert row is not None
    # v0.2.0: refmet_name empty; pin stable CHEBI CURIE instead
    assert row["chebi"] == "CHEBI:4167"


def test_lookup_by_inchikey2d():
    # InChIKey2D lookup returns the first matching compound with that 2D skeleton
    row = COMPOUND_INDEX.lookup("WQZGKKKJIJFFOK")
    assert row is not None
    # v0.2.0: refmet_name empty; verify chebi is present (multiple pyranose isomers share this 2D key)
    assert "chebi" in row


def test_lookup_is_pure():
    """Same input returns equal dicts on repeated calls."""
    r1 = COMPOUND_INDEX.lookup("glucose")
    r2 = COMPOUND_INDEX.lookup("glucose")
    assert r1 == r2


def test_index_size_substantial():
    """The v0.2.0 TSV ships ~156k rows from Wikidata; verify substantial coverage."""
    # Force a load
    COMPOUND_INDEX._load()
    assert len(COMPOUND_INDEX._by_name) >= 5000


def test_lazy_load_only_once():
    """Loading is idempotent."""
    fresh = CompoundIndex()
    assert fresh._loaded is False
    _ = fresh.lookup("glucose")
    assert fresh._loaded is True
    n = len(fresh._by_name)
    _ = fresh.lookup("glutamic acid")  # second call must not re-load (Wikidata label)
    assert len(fresh._by_name) == n
