"""Tests for the CompoundIndex lookup engine."""
from __future__ import annotations

from indicium_adapters_metabolomics._enrichment import COMPOUND_INDEX, CompoundIndex


def test_lookup_by_name_returns_row():
    row = COMPOUND_INDEX.lookup("glucose")
    assert row is not None
    # Pin stable identifiers that should never change.
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
    # Pin stable CHEBI CURIE.
    assert row["chebi"] == "CHEBI:4167"


def test_lookup_by_inchikey2d():
    # InChIKey2D lookup returns the first matching compound with that 2D skeleton
    row = COMPOUND_INDEX.lookup("WQZGKKKJIJFFOK")
    assert row is not None
    # Multiple pyranose isomers share this 2D key; just verify the CHEBI column is present.
    assert "chebi" in row


def test_lookup_is_pure():
    """Same input returns equal dicts on repeated calls."""
    r1 = COMPOUND_INDEX.lookup("glucose")
    r2 = COMPOUND_INDEX.lookup("glucose")
    assert r1 == r2


def test_index_size_substantial():
    """The bundled TSV ships ~156k metabolites.

    Bump the threshold here whenever build_data.py is re-run and the
    bundled TSV grows significantly, so this acts as a real regression
    guard. Current target: ≥100,000 rows.
    """
    _ = COMPOUND_INDEX.lookup("water")
    assert len(COMPOUND_INDEX._by_name) >= 100_000


def test_refmet_name_populated_for_well_known_metabolites():
    """v0.3.0: refmet_name column is populated for HMDB+InChIKey+KEGG-mapped metabolites.

    The enrichment covers the subset with InChIKey + HMDB + KEGG/PubChem (~5k rows).
    L-lactic acid is a well-known metabolite with all four cross-references; its
    RefMet canonical name should be 'Lactic acid'.
    """
    row = COMPOUND_INDEX.lookup("l-lactic acid")
    assert row is not None, "Expected 'l-lactic acid' in CompoundIndex"
    # L-Lactic acid has InChIKey + HMDB + KEGG + PubChem, so RefMet should be populated.
    assert row.get("refmet_name"), (
        "Expected non-empty refmet_name for L-lactic acid after v0.3.0 enrichment; "
        f"got {row.get('refmet_name')!r}"
    )


def test_lazy_load_only_once():
    """Loading is idempotent."""
    fresh = CompoundIndex()
    assert fresh._loaded is False
    _ = fresh.lookup("glucose")
    assert fresh._loaded is True
    n = len(fresh._by_name)
    _ = fresh.lookup("glutamic acid")  # second call must not re-load (Wikidata label)
    assert len(fresh._by_name) == n
