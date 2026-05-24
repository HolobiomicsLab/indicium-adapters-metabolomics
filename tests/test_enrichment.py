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


def test_lookup_by_curie_chebi():
    """v0.3.1: subjects already in CURIE form must resolve to the full row.

    Audit finding: enrich_claim() previously only keyed on name_lower so a
    CURIE-shaped subject like 'CHEBI:17234' returned an empty enrichment even
    though the bundled TSV contains the full cross-reference row. Indexing by
    CURIE lets downstream consumers (LLM extractors that emit CURIEs directly,
    mzTab SML rows whose database_identifier is a CURIE) get the same xref
    expansion as name-keyed lookups.
    """
    row = COMPOUND_INDEX.lookup("CHEBI:17234")
    assert row is not None
    assert row["name_lower"] == "glucose"


def test_lookup_by_curie_is_case_insensitive_on_prefix():
    """CURIE prefix matching tolerates the lowercase form ('chebi:17234')."""
    assert COMPOUND_INDEX.lookup("chebi:17234") is not None


def test_lookup_by_curie_hmdb_bare_id():
    """HMDB IDs are stored bare in the TSV ('HMDB0000122'); the by-CURIE
    index normalises them so 'HMDB:HMDB0000122' resolves."""
    row = COMPOUND_INDEX.lookup("HMDB:HMDB0000122")
    assert row is not None
    assert (row.get("hmdb") or "").endswith("HMDB0000122")


def test_lookup_by_curie_wikidata():
    """WD CURIEs are stored prefixed in the TSV; lookup must resolve them."""
    row = COMPOUND_INDEX.lookup("WD:Q37525")
    assert row is not None
    assert row["chebi"] == "CHEBI:17234"


def test_lookup_by_curie_unknown_returns_none():
    """Garbage CURIE (well-formed prefix, non-existent ID) returns None."""
    assert COMPOUND_INDEX.lookup("CHEBI:99999999999") is None


def test_synonym_layer_resolves_iaa():
    """v0.4.0: synonym layer resolves 'indole-3-acetic acid' to indoleacetic
    acid (CHEBI:16411). Closes the IAA gap surfaced by the 2026-05-24 audit
    where Wikidata's English label is 'indoleacetic acid' but papers / LLMs
    typically write 'indole-3-acetic acid'.
    """
    row = COMPOUND_INDEX.lookup("indole-3-acetic acid")
    assert row is not None
    assert row["chebi"] == "CHEBI:16411"
    # Acronym form too
    assert (COMPOUND_INDEX.lookup("IAA") or {}).get("chebi") == "CHEBI:16411"


def test_synonym_layer_resolves_well_known_vitamins_and_acronyms():
    """A handful of high-confidence synonyms verified at TSV-load time."""
    cases = {
        "ATP":                 "adenosine triphosphate",
        "vitamin b12":         "cobalamin",
        "EGCG":                "epigallocatechin gallate",
        "ascorbic acid":       "vitamin c",
        "acetylsalicylic acid":"aspirin",
        "DHA":                 "docosahexaenoic acid",
    }
    for alias, target in cases.items():
        row = COMPOUND_INDEX.lookup(alias)
        assert row is not None, f"alias {alias!r} did not resolve"
        # Both must point at the same row.
        assert row is COMPOUND_INDEX.lookup(target)


def test_synonym_layer_unknown_alias_still_misses():
    """A bare gibberish string still returns None — synonyms shouldn't
    accidentally widen the lookup surface."""
    assert COMPOUND_INDEX.lookup("zzz-not-a-real-thing") is None


def test_synonym_layer_v0_5_0_domain_specific_aliases():
    """v0.5.0: 9+ extra synonyms added per the 2026-05-24 audit-2 misses.

    These cover gut metabolites (TMAO, p-cresol), natural-product drug name
    variants (rapamycin → sirolimus, compactin → mevastatin), plant phenolic
    spellings (catechin, p-coumaric acid), and UK/typo variants.
    """
    cases = {
        "TMAO":                       "trimethylamine oxide",
        "trimethylamine n-oxide":     "trimethylamine oxide",
        "rapamycin":                  "sirolimus",
        "p-cresol":                   "para-cresol",
        "4-methylphenol":             "para-cresol",
        "p-coumaric acid":            "4-coumaric acid",
        "compactin":                  "mevastatin",
        "indoxyl sulphate":           "indoxyl sulfate",
        "tetracyclin":                "tetracycline",
        "kanamycin":                  "kanamycin a",
        "catechin":                   "(+)-catechin",
        "indole-3-propionic acid":    "3-indolepropionic acid",
    }
    for alias, target in cases.items():
        a, t = COMPOUND_INDEX.lookup(alias), COMPOUND_INDEX.lookup(target)
        assert a is not None, f"alias {alias!r} did not resolve"
        assert t is not None, f"canonical target {target!r} missing from TSV"
        assert a is t, f"{alias!r} resolved to a different row than {target!r}"


def test_lazy_load_only_once():
    """Loading is idempotent."""
    fresh = CompoundIndex()
    assert fresh._loaded is False
    _ = fresh.lookup("glucose")
    assert fresh._loaded is True
    n = len(fresh._by_name)
    _ = fresh.lookup("glutamic acid")  # second call must not re-load (Wikidata label)
    assert len(fresh._by_name) == n
